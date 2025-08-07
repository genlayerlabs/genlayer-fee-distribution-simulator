"""Invariant 24: Event ordering matches round progression"""

from typing import List
from fee_simulator.models import FeeEvent
from .common import InvariantViolation


def check_temporal_event_consistency(fee_events: List[FeeEvent]) -> None:
    """
    Invariant 24: Event ordering matches round progression.
    Events with earlier sequence IDs should not occur in later rounds than events with later sequence IDs.
    """
    # Sort events by sequence ID
    sorted_events = sorted(fee_events, key=lambda e: e.sequence_id)

    # Check round indices are non-decreasing
    for i in range(1, len(sorted_events)):
        curr_event = sorted_events[i]
        prev_event = sorted_events[i - 1]

        # Skip events without round indices
        if curr_event.round_index is None or prev_event.round_index is None:
            continue

        # Check temporal consistency
        if curr_event.round_index < prev_event.round_index:
            raise InvariantViolation(
                "temporal_event_consistency",
                f"Event {curr_event.sequence_id} (round {curr_event.round_index}) "
                f"occurs before event {prev_event.sequence_id} (round {prev_event.round_index}) "
                f"despite having a later sequence ID",
            )

    # Additional check: within same round, sequence IDs should be consistent
    events_by_round = {}
    for event in fee_events:
        if event.round_index is not None:
            if event.round_index not in events_by_round:
                events_by_round[event.round_index] = []
            events_by_round[event.round_index].append(event)

    # For each round, check sequence ID ordering
    for round_idx, round_events in events_by_round.items():
        # Sort by sequence ID
        round_events_sorted = sorted(round_events, key=lambda e: e.sequence_id)

        # Check for gaps or inconsistencies
        seq_ids = [e.sequence_id for e in round_events_sorted]
        if seq_ids:
            # Check that sequence IDs are consecutive within reasonable bounds
            # (small gaps are OK due to filtering, but large gaps might indicate issues)
            max_gap = (
                max(seq_ids[i] - seq_ids[i - 1] for i in range(1, len(seq_ids)))
                if len(seq_ids) > 1
                else 0
            )

            if max_gap > 1000:  # Arbitrary threshold for suspiciously large gaps
                raise InvariantViolation(
                    "temporal_event_consistency",
                    f"Round {round_idx} has suspiciously large sequence ID gap: {max_gap}",
                )
