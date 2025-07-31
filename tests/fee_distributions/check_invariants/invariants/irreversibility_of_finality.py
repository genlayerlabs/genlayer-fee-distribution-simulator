"""Invariant 23: No events after END state"""

from typing import List
from fee_simulator.models import FeeEvent, TransactionRoundResults
from fee_simulator.types import RoundLabel
from .common import InvariantViolation


def check_irreversibility_of_finality(
    transaction_results: TransactionRoundResults,
    fee_events: List[FeeEvent],
    round_labels: List[RoundLabel],
) -> None:
    """
    Invariant 23: No events after END state.
    Once the transaction reaches a terminal state, no further fee events should occur.
    """
    # Find the END round index
    end_round_index = None

    # Check if we have an explicit END label or if it's the last round
    for i, label in enumerate(round_labels):
        if label == "END" or i == len(round_labels) - 1:
            end_round_index = i
            break

    if end_round_index is None:
        # No END state found, which might be OK for some test cases
        return

    # Check no fee events after the END round
    events_after_end = []
    for event in fee_events:
        if event.round_index is not None and event.round_index > end_round_index:
            events_after_end.append(event)

    if events_after_end:
        event_descriptions = []
        for e in events_after_end:
            desc = f"Round {e.round_index}: {e.role} {e.address}"
            if e.earned and e.earned > 0:
                desc += f" earned {e.earned}"
            if e.cost and e.cost > 0:
                desc += f" cost {e.cost}"
            if e.burned and e.burned > 0:
                desc += f" burned {e.burned}"
            if e.slashed and e.slashed > 0:
                desc += f" slashed {e.slashed}"
            event_descriptions.append(desc)

        raise InvariantViolation(
            "irreversibility_of_finality",
            f"Found {len(events_after_end)} events after END (round {end_round_index}): "
            f"{'; '.join(event_descriptions)}",
        )

    # Additional check: sequence IDs should respect the END boundary
    if end_round_index is not None:
        # Find max sequence ID for events up to END
        max_seq_before_end = max(
            (
                e.sequence_id
                for e in fee_events
                if e.round_index is not None and e.round_index <= end_round_index
            ),
            default=0,
        )

        # Check no events have sequence IDs after this
        for event in fee_events:
            if event.sequence_id > max_seq_before_end and event.round_index is not None:
                if event.round_index > end_round_index:
                    raise InvariantViolation(
                        "irreversibility_of_finality",
                        f"Event with sequence_id {event.sequence_id} occurs after END state "
                        f"(max allowed sequence_id: {max_seq_before_end})",
                    )
