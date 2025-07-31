"""Invariant 6: Rounds must be processed in sequential order"""

from typing import List
from fee_simulator.models import FeeEvent
from .common import InvariantViolation


def check_sequential_processing(fee_events: List[FeeEvent]) -> None:
    """Invariant 6: Rounds must be processed in sequential order"""
    round_indices = [e.round_index for e in fee_events if e.round_index is not None]

    if not round_indices:
        return

    # Check that round indices are in non-decreasing order
    for i in range(1, len(round_indices)):
        if round_indices[i] < round_indices[i - 1]:
            raise InvariantViolation(
                "sequential_processing",
                f"Round {round_indices[i]} processed before round {round_indices[i-1]}",
            )
