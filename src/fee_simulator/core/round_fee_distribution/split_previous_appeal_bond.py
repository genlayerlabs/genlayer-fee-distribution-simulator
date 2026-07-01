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
from src.fee_simulator.utils import split_amount


def apply_split_previous_appeal_bond(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    """
    Distribute the previous appeal bond among validators in the current round.
    This happens after an unsuccessful appeal.

    The appeal bond (minus leader timeout) is split among:
    - All validators equally if there's no majority (UNDETERMINED)
    - Only majority validators if there's a clear majority
    """
    events = []
    round = transaction_results.rounds[round_index]

    if (
        not round.rotations
        or not budget.appeals
        or round_index < 2  # Need at least 2 previous rounds
    ):
        return events

    votes = round.rotations[-1].votes
    majority = compute_majority(votes)
    majority_addresses, minority_addresses = who_is_in_vote_majority(votes, majority)

    # Compute appeal bond for the previous appeal round (normal_round_index = round_index - 2)
    appeal_bond = compute_appeal_bond(
        normal_round_index=round_index - 2,
        leader_timeout=budget.leaderTimeout,
        validators_timeout=budget.validatorsTimeout,
        round_labels=round_labels,
        rotations=budget.rotations,
    )

    # Amount to split is appeal bond minus leader timeout
    amount_to_split = appeal_bond - budget.leaderTimeout

    # Distribute to validators
    if majority == "UNDETERMINED":
        # Split among all validators equally
        undet_split_amount = split_amount(amount_to_split, len(votes))
        for addr in votes.keys():
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="SPLIT_PREVIOUS_APPEAL_BOND",
                    role="VALIDATOR",
                    vote=normalize_vote(votes[addr]),
                    hash="0xdefault",
                    cost=0,
                    staked=0,
                    earned=undet_split_amount,  # Only the split, no timeout
                    slashed=0,
                    burned=0,
                )
            )
    else:
        # Split among majority validators only
        agree_split_amount = split_amount(amount_to_split, len(majority_addresses))

        for addr in majority_addresses:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="SPLIT_PREVIOUS_APPEAL_BOND",
                    role="VALIDATOR",
                    vote=normalize_vote(votes[addr]),
                    hash="0xdefault",
                    cost=0,
                    staked=0,
                    earned=agree_split_amount,  # Full appeal bond split among majority
                    slashed=0,
                    burned=0,
                )
            )

        # Penalize minority validators
        for addr in minority_addresses:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="SPLIT_PREVIOUS_APPEAL_BOND",
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

    # Award the leader their timeout
    first_addr = next(iter(votes.keys()), None)
    if first_addr:
        events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=first_addr,
                round_index=round_index,
                round_label="SPLIT_PREVIOUS_APPEAL_BOND",
                role="LEADER",
                vote=normalize_vote(votes[first_addr]),
                hash="0xdefault",
                cost=0,
                staked=0,
                earned=budget.leaderTimeout,
                slashed=0,
                burned=0,
            )
        )

    return events
