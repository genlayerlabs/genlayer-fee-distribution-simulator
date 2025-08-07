"""Invariant 14: No participant should be penalized multiple times for the same offense"""

from typing import List
from collections import defaultdict
from fee_simulator.models import FeeEvent
from .common import InvariantViolation


def check_no_double_penalties(fee_events: List[FeeEvent]) -> None:
    """
    Invariant 14: No participant should be penalized multiple times for the same offense.
    In each round, a participant should receive at most one penalty (burn or slash).
    """
    # Group penalties by participant and round
    penalties_by_participant_round = defaultdict(list)

    for event in fee_events:
        # Check for penalty events (burns or slashes)
        if (event.burned and event.burned > 0) or (event.slashed and event.slashed > 0):
            key = (event.address, event.round_index)
            penalties_by_participant_round[key].append(event)

    # Check no more than one penalty per participant per round
    for (address, round_idx), penalty_events in penalties_by_participant_round.items():
        if len(penalty_events) > 1:
            # Describe the penalties
            penalty_descriptions = []
            for e in penalty_events:
                if e.burned and e.burned > 0:
                    penalty_descriptions.append(f"burn={e.burned}")
                if e.slashed and e.slashed > 0:
                    penalty_descriptions.append(f"slash={e.slashed}")

            raise InvariantViolation(
                "no_double_penalties",
                f"Participant {address} received {len(penalty_events)} penalties in round {round_idx}: "
                f"{', '.join(penalty_descriptions)}",
            )
