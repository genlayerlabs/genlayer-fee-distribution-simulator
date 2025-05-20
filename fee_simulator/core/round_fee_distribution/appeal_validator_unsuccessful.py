from typing import List
from math import floor
from fee_simulator.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
)
from fee_simulator.core.majority import (
    compute_majority,
    who_is_in_vote_majority,
    normalize_vote,
)
from fee_simulator.core.burns import compute_unsuccessful_validator_appeal_burn
from fee_simulator.constants import PENALTY_REWARD_COEFFICIENT


def apply_appeal_validator_unsuccessful(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
) -> List[FeeEvent]:
    events = []
    round = transaction_results.rounds[round_index]
    appeal = budget.appeals[floor(round_index / 2)]
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
        round_index, budget.leaderTimeout, budget.validatorsTimeout, events
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
