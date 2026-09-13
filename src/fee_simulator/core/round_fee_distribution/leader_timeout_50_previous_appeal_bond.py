from typing import List
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    FeeEvent,
    EventSequence,
    RoundLabel,
)
from src.fee_simulator.core.majority import normalize_vote
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.utils_round_sizes import find_previous_normal_round


def apply_leader_timeout_50_previous_appeal_bond(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    """
    Mirror the contract's LEADER_TIMEOUT_50_PERCENT_PREV_APPEAL_BOND handler
    (FeesProcessor.processFeesForTx): the previous (failed) leader timeout
    appeal bond is split 50/50 between the new leader and the sender:

    - Leader earns appeal_bond // 2
    - Sender receives appeal_bond - appeal_bond // 2 (handles odd amounts)
    - Nothing is burned; the appellant's loss is the bond itself.
    """
    events = []
    round = transaction_results.rounds[round_index]
    if not round.rotations or not budget.appeals or round_index < 1:
        return events

    votes = round.rotations[-1].votes
    sender_address = budget.senderAddress

    # Find the most recent normal round before the previous round
    # This is used to compute the appeal bond from the previous appeal
    normal_round_index = find_previous_normal_round(round_index - 1, round_labels)
    if normal_round_index is None:
        normal_round_index = round_index - 2  # Default

    appeal_bond = compute_appeal_bond(
        normal_round_index,
        budget.leaderTimeout,
        budget.validatorsTimeout,
        round_labels=round_labels,
        appeal_round_index=round_index - 1,
        rotations=budget.rotations,
        rotations_used=budget.rotationsUsed,
    )

    leader_share = appeal_bond // 2

    # Award half the appeal bond to the leader
    first_addr = next(iter(votes.keys()), None)
    if first_addr:
        events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=first_addr,
                round_index=round_index,
                round_label="LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
                role="LEADER",
                vote=normalize_vote(votes[first_addr]),
                hash="0xdefault",
                cost=0,
                staked=0,
                earned=leader_share,
                slashed=0,
                burned=0,
            )
        )

    # The sender receives the remaining half of the bond
    events.append(
        FeeEvent(
            sequence_id=event_sequence.next_id(),
            address=sender_address,
            round_index=round_index,
            round_label="LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            role="SENDER",
            vote="NA",
            hash="0xdefault",
            cost=0,
            staked=0,
            earned=appeal_bond - leader_share,
            slashed=0,
            burned=0,
        )
    )

    return events
