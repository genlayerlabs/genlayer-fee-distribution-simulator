"""Invariant 11: Idle validators slashed exactly penalty coefficient"""

from typing import List
from src.fee_simulator.protocol.models import FeeEvent
from src.fee_simulator.protocol.constants import IDLE_PENALTY_COEFFICIENT
from .common import InvariantViolation


def check_idle_slashing(fee_events: List[FeeEvent]) -> None:
    """Invariant 11: Idle validators slashed exactly penalty coefficient"""
    for event in fee_events:
        if event.vote == "IDLE" and event.slashed:
            # Find the stake initialization event for this address
            stake_events = [
                e
                for e in fee_events
                if e.address == event.address and e.role == "TOPPER" and e.earned
            ]
            if stake_events:
                stake = stake_events[0].earned
                expected_slash = IDLE_PENALTY_COEFFICIENT * stake
                if abs(event.slashed - expected_slash) > 1:
                    raise InvariantViolation(
                        "idle_slashing",
                        f"Idle slash mismatch for {event.address}: "
                        f"expected {expected_slash}, got {event.slashed}",
                    )
