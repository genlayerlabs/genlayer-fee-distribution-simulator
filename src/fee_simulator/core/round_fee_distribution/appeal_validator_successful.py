from typing import List
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
    RoundLabel,
)
from src.fee_simulator.core.majority import (
    compute_majority,
    who_is_in_vote_majority,
    normalize_vote,
)
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.protocol.constants import PENALTY_REWARD_COEFFICIENT
from src.fee_simulator.utils import is_appeal_round
from src.fee_simulator.utils_round_sizes import find_previous_normal_round


def apply_appeal_validator_successful(
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

    # Find the most recent normal round before this appeal
    normal_round_index = find_previous_normal_round(round_index, round_labels)
    if normal_round_index is None:
        normal_round_index = round_index - 1  # Default fallback

    appeal_bond = compute_appeal_bond(
        normal_round_index=normal_round_index,
        leader_timeout=budget.leaderTimeout,
        validators_timeout=budget.validatorsTimeout,
        round_labels=round_labels,
    )
    events.append(
        FeeEvent(
            sequence_id=event_sequence.next_id(),
            address=appealant_address,
            round_index=round_index,
            round_label="APPEAL_VALIDATOR_SUCCESSFUL",
            role="APPEALANT",
            vote="NA",
            hash="0xdefault",
            cost=0,
            staked=0,
            earned=int(appeal_bond * 1.5),  # 50% return on investment
            slashed=0,
            burned=0,
        )
    )

    if round.rotations:
        votes_this_round = round.rotations[-1].votes
        # votes_previous_round = (
        #     transaction_results.rounds[round_index - 1].rotations[-1].votes
        # )
        # total_votes = {**votes_this_round, **votes_previous_round}
        total_votes = votes_this_round
        majority = compute_majority(total_votes)
        if majority == "UNDETERMINED":
            for addr in total_votes:
                events.append(
                    FeeEvent(
                        sequence_id=event_sequence.next_id(),
                        address=addr,
                        round_index=round_index,
                        round_label="APPEAL_VALIDATOR_SUCCESSFUL",
                        role="VALIDATOR",
                        vote=normalize_vote(total_votes[addr]),
                        hash="0xdefault",
                        cost=0,
                        staked=0,
                        earned=budget.validatorsTimeout,
                        slashed=0,
                        burned=0,
                    )
                )

        else:
            majority_addresses, minority_addresses = who_is_in_vote_majority(
                total_votes, majority
            )
            for addr in majority_addresses:
                events.append(
                    FeeEvent(
                        sequence_id=event_sequence.next_id(),
                        address=addr,
                        round_index=round_index,
                        round_label="APPEAL_VALIDATOR_SUCCESSFUL",
                        role="VALIDATOR",
                        vote=normalize_vote(total_votes[addr]),
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
                        round_label="APPEAL_VALIDATOR_SUCCESSFUL",
                        role="VALIDATOR",
                        vote=normalize_vote(total_votes[addr]),
                        hash="0xdefault",
                        cost=0,
                        staked=0,
                        earned=0,
                        slashed=0,
                        burned=PENALTY_REWARD_COEFFICIENT * budget.validatorsTimeout,
                    )
                )
    return events
