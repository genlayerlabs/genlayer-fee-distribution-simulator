from typing import List
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.core.majority import (
    compute_majority,
    who_is_in_vote_majority,
    normalize_vote,
)
from src.fee_simulator.core.burns import compute_unsuccessful_validator_appeal_burn
from src.fee_simulator.protocol.constants import PENALTY_REWARD_COEFFICIENT
from src.fee_simulator.utils import is_appeal_round


def apply_appeal_validator_unsuccessful(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    events = []
    round = transaction_results.rounds[round_index]

    # Find which appeal this is by counting appeals up to this point
    appeal_count = sum(
        1 for i in range(round_index + 1) if is_appeal_round(round_labels[i])
    )
    appeal_index = appeal_count - 1

    if appeal_index < 0 or appeal_index >= len(budget.appeals):
        raise ValueError(
            f"Appeal index {appeal_index} out of bounds for round {round_index}"
        )

    appeal = budget.appeals[appeal_index]
    appealant_address = appeal.appealantAddress
    if round.rotations:
        votes = round.rotations[-1].votes
        majority = compute_majority(votes)
        majority_addresses, minority_addresses = who_is_in_vote_majority(
            votes, majority
        )
        for addr in majority_addresses:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="APPEAL_VALIDATOR_UNSUCCESSFUL",
                    role="VALIDATOR",
                    vote=normalize_vote(votes[addr]),
                    hash="0xdefault",
                    cost=0,
                    staked=0,
                    earned=budget.validatorsTimeout,
                    slashed=0,
                    burned=0,
                )
            )
        for addr in minority_addresses:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="APPEAL_VALIDATOR_UNSUCCESSFUL",
                    role="VALIDATOR",
                    vote=normalize_vote(votes[addr]),
                    hash="0xdefault",
                    cost=0,
                    staked=0,
                    earned=0,
                    slashed=0,
                    burned=PENALTY_REWARD_COEFFICIENT * budget.validatorsTimeout,
                )
            )
    total_to_burn = compute_unsuccessful_validator_appeal_burn(
        round_index,
        budget.leaderTimeout,
        budget.validatorsTimeout,
        events,
        round_labels=round_labels,
    )
    events.append(
        FeeEvent(
            sequence_id=event_sequence.next_id(),
            address=appealant_address,
            round_index=round_index,
            round_label="APPEAL_VALIDATOR_UNSUCCESSFUL",
            role="APPEALANT",
            vote="NA",
            hash="0xdefault",
            cost=0,
            staked=0,
            earned=0,
            slashed=0,
            burned=total_to_burn,
        )
    )
    return events
