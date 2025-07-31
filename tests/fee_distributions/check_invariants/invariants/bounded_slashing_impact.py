"""Invariant 15: Each participant can only be slashed once per transaction"""

from typing import List
from fee_simulator.models import FeeEvent
from .common import InvariantViolation


def check_bounded_slashing_impact(fee_events: List[FeeEvent]) -> None:
    """
    Invariant 15: Each participant can only be slashed once per transaction.
    After being slashed (idle or violation), they are removed from the active pool.
    """
    # Track slashing events per participant
    slash_events_by_participant = {}

    for event in fee_events:
        if event.slashed and event.slashed > 0:
            if event.address not in slash_events_by_participant:
                slash_events_by_participant[event.address] = []
            slash_events_by_participant[event.address].append(event)

    # Check each participant has at most one slash
    for participant, slash_events in slash_events_by_participant.items():
        if len(slash_events) > 1:
            # Describe all slashing events
            slash_descriptions = []
            for e in slash_events:
                slash_descriptions.append(
                    f"round {e.round_index}: {e.slashed} (vote: {e.vote})"
                )

            raise InvariantViolation(
                "bounded_slashing_impact",
                f"Participant {participant} was slashed {len(slash_events)} times: "
                f"{'; '.join(slash_descriptions)}. Should only be slashed once before removal.",
            )
