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
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.protocol.constants import PENALTY_REWARD_COEFFICIENT
from src.fee_simulator.utils import split_amount


def apply_leader_timeout_150_previous_normal_round(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    events = []
    round = transaction_results.rounds[round_index]
    if not round.rotations:
        return events

    votes = round.rotations[-1].votes
    majority = compute_majority(votes)
    majority_addresses, minority_addresses = who_is_in_vote_majority(votes, majority)
    sender_address = budget.senderAddress

    # Compute appeal bond for the previous normal round (normal_round_index = round_index - 2)
    appeal_bond = compute_appeal_bond(
        normal_round_index=round_index - 2,
        leader_timeout=budget.leaderTimeout,
        validators_timeout=budget.validatorsTimeout,
        round_labels=round_labels,
        rotations=budget.rotations,
        rotations_used=budget.rotationsUsed,
    )

    # Award the leader 150% of leaderTimeout
    first_addr = next(iter(votes.keys()), None)
    if first_addr:
        events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=first_addr,
                round_index=round_index,
                round_label="LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
                role="LEADER",
                vote=normalize_vote(votes[first_addr]),
                hash="0xdefault",
                cost=0,
                staked=0,
                earned=budget.leaderTimeout * 1.5,
                slashed=0,
                burned=0,
            )
        )

    # Award the sender 50% of leaderTimeout
    events.append(
        FeeEvent(
            sequence_id=event_sequence.next_id(),
            address=sender_address,
            round_index=round_index,
            round_label="LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
            role="SENDER",
            vote="NA",
            hash="0xdefault",
            cost=0,
            staked=0,
            earned=budget.leaderTimeout * 0.5,
            slashed=0,
            burned=0,
        )
    )

    if majority == "UNDETERMINED":
        for addr in votes.keys():
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
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
    else:
        # Distribute to majority validators
        for addr in majority_addresses:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
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

        # Penalize minority validators
        for addr in minority_addresses:
            events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    round_index=round_index,
                    round_label="LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
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

    return events
