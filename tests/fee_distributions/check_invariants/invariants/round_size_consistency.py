"""Additional invariant: The number of participants in each round should match expected sizes"""

from typing import List
from fee_simulator.models import FeeEvent, TransactionRoundResults
from fee_simulator.types import RoundLabel
from fee_simulator.constants import NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES
from fee_simulator.utils import is_appeal_round
from .common import InvariantViolation


def check_round_size_consistency(
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults,
    round_labels: List[RoundLabel],
) -> None:
    """
    Additional invariant: The number of participants in each round should match
    the expected size from NORMAL_ROUND_SIZES or APPEAL_ROUND_SIZES.
    """
    normal_count = 0
    appeal_count = 0

    for i, (round_obj, label) in enumerate(
        zip(transaction_results.rounds, round_labels)
    ):
        if label == "EMPTY_ROUND":
            continue
        if round_obj.rotations:
            # Count unique participants in this round
            participants = set()
            for rotation in round_obj.rotations:
                participants.update(rotation.votes.keys())

            actual_size = len(participants)

            if is_appeal_round(label):
                # Check if previous round was an unsuccessful appeal
                prev_was_unsuccessful_appeal = (
                    i > 0
                    and is_appeal_round(round_labels[i - 1])
                    and "UNSUCCESSFUL" in round_labels[i - 1]
                )

                # Get base size for this appeal
                base_size = (
                    APPEAL_ROUND_SIZES[appeal_count]
                    if appeal_count < len(APPEAL_ROUND_SIZES)
                    else APPEAL_ROUND_SIZES[-1]
                )

                # Reduce by 2 if previous was unsuccessful appeal
                expected_size = (
                    base_size - 2 if prev_was_unsuccessful_appeal else base_size
                )
                appeal_count += 1
            else:
                # Normal rounds - calculate blockchain index properly
                if normal_count == 0:
                    blockchain_index = 0
                else:
                    # Count appeals before this normal round
                    appeals_before = sum(
                        1 for j in range(i) if is_appeal_round(round_labels[j])
                    )
                    blockchain_index = 2 * appeals_before

                size_index = blockchain_index // 2
                expected_size = (
                    NORMAL_ROUND_SIZES[size_index]
                    if size_index < len(NORMAL_ROUND_SIZES)
                    else NORMAL_ROUND_SIZES[-1]
                )
                normal_count += 1

            # Handle pool exhaustion - if actual is less than expected but positive, it might be OK
            if actual_size < expected_size and actual_size > 0:
                # Check if this could be due to pool exhaustion
                # Count total addresses used so far
                total_used = 0
                for j in range(i + 1):
                    if transaction_results.rounds[j].rotations:
                        round_participants = set()
                        for rotation in transaction_results.rounds[j].rotations:
                            round_participants.update(rotation.votes.keys())
                        total_used += len(round_participants)

                # If we're close to pool limit, allow the discrepancy
                if total_used >= 900:  # Within 100 of the 1000 limit
                    continue

            if actual_size != expected_size:
                raise InvariantViolation(
                    "round_size_consistency",
                    f"Round {i} ({label}): Expected {expected_size} participants, "
                    f"but found {actual_size}",
                )
