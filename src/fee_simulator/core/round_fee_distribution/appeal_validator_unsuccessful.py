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
from src.fee_simulator.utils import is_appeal_round
from src.fee_simulator.utils_round_sizes import find_previous_normal_round


def apply_appeal_validator_unsuccessful(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    event_sequence: EventSequence,
    round_labels: List[RoundLabel],
) -> List[FeeEvent]:
    """
    Mirror the contract's APPEAL_VALIDATOR_UNSUCCESSFUL handler
    (FeesProcessor, redistributeNonAlignedFees=true):

    - The appellant loses the entire bond; it is pooled with ALL the round's
      validator fees: pool = validatorsTimeout * num_validators + appeal_bond.
    - Validators aligned with the round's own majority each earn
      pool // aligned_count (non-aligned validators' fees are redistributed
      to the aligned ones, not returned to the sender).
    - UNDETERMINED (NoMajority) counts every validator as aligned.
    - Non-aligned validators are additionally penalized.
    - Nothing is burned: the division remainder flows back to the sender.
    """
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

    if not round.rotations:
        return events

    votes = round.rotations[-1].votes
    majority = compute_majority(votes)

    if majority == "UNDETERMINED":
        aligned_addresses = list(votes.keys())
        minority_addresses = []
    else:
        aligned_addresses, minority_addresses = who_is_in_vote_majority(votes, majority)

    normal_round_index = find_previous_normal_round(round_index, round_labels)
    if normal_round_index is None:
        normal_round_index = round_index - 1

    appeal_bond = compute_appeal_bond(
        normal_round_index=normal_round_index,
        leader_timeout=budget.leaderTimeout,
        validators_timeout=budget.validatorsTimeout,
        round_labels=round_labels,
        appeal_round_index=round_index,
        rotations=budget.rotations,
        rotations_used=budget.rotationsUsed,
    )

    pool = budget.validatorsTimeout * len(votes) + appeal_bond
    per_aligned = pool // len(aligned_addresses) if aligned_addresses else 0

    for addr in aligned_addresses:
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
                earned=per_aligned,
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
    return events
