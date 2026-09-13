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
    Distribute the previous (unsuccessful leader) appeal bond among the
    current round's validators, mirroring the contract's
    SPLIT_PREV_APPEAL_BOND_ROUND handler (FeesProcessor.processFeesForTx):

    - Aligned validators (leader included in the pool, skipLeader=false)
      each earn validatorsTimeout + appeal_bond // aligned_count.
      The FULL bond is distributed — it is not reduced by leaderTimeout.
    - UNDETERMINED (NoMajority) counts every validator as aligned.
    - Non-aligned validators are penalized.
    - The leader additionally earns leaderTimeout (paid from the budget).
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

    # Compute appeal bond for the previous appeal round (normal_round_index = round_index - 2)
    appeal_bond = compute_appeal_bond(
        normal_round_index=round_index - 2,
        leader_timeout=budget.leaderTimeout,
        validators_timeout=budget.validatorsTimeout,
        round_labels=round_labels,
        rotations=budget.rotations,
        rotations_used=budget.rotationsUsed,
        appeal_round_index=round_index - 1,
    )

    # Contract: aligned validators earn V + full bond share; NoMajority → all aligned
    if majority == "UNDETERMINED":
        aligned_addresses = list(votes.keys())
        minority_addresses = []
    else:
        aligned_addresses, minority_addresses = who_is_in_vote_majority(votes, majority)

    bond_share = split_amount(appeal_bond, len(aligned_addresses))
    for addr in aligned_addresses:
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
                earned=budget.validatorsTimeout + bond_share,
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

    # Award the leader their timeout (from the budget, on top of any
    # validator share earned above)
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
