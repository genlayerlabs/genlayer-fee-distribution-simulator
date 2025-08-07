"""Invariant 8: All burns must be non-negative"""

from typing import List
from fee_simulator.models import FeeEvent
from .common import InvariantViolation


def check_burn_non_negativity(fee_events: List[FeeEvent]) -> None:
    """Invariant 8: All burns must be non-negative"""
    for event in fee_events:
        if event.burned is not None and event.burned < 0:
            raise InvariantViolation(
                "burn_non_negativity",
                f"Negative burn amount {event.burned} for address {event.address} "
                f"in round {event.round_index}",
            )
