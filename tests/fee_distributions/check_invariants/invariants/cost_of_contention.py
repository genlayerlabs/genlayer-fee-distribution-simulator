"""Invariant 18: Value destruction increases with failed appeals"""

from typing import List
from fee_simulator.models import FeeEvent
from fee_simulator.types import RoundLabel
from fee_simulator.utils import is_appeal_round
from .common import InvariantViolation


def check_cost_of_contention(
    fee_events: List[FeeEvent], round_labels: List[RoundLabel]
) -> None:
    """
    Invariant 18: Value destruction increases with failed appeals.
    The total cost of contention (appellant costs + burns) should be consistent
    with the number of failed appeals.
    """
    # Count failed appeals and their rounds
    failed_appeals = [
        i for i, label in enumerate(round_labels) if "UNSUCCESSFUL" in label
    ]
    failed_appeal_count = len(failed_appeals)

    # Calculate total cost for appellants in failed appeals
    appellant_costs = sum(
        e.cost
        for e in fee_events
        if e.role == "APPEALANT" and e.round_index in failed_appeals
    )

    # Calculate total burns from penalties (excluding appellant costs)
    total_burns = sum(e.burned for e in fee_events)

    # The total cost of contention is the sum of what appellants paid and what was burned
    total_contention_cost = appellant_costs + total_burns

    # Each failed appeal has an associated bond that the appellant pays.
    # This bond is the minimum cost of that contention.
    min_expected_cost = 0
    if failed_appeal_count > 0:
        for appeal_round_index in failed_appeals:
            bond_events = [
                e
                for e in fee_events
                if e.round_index == appeal_round_index
                and e.role == "APPEALANT"
                and e.cost > 0
            ]
            if bond_events:
                min_expected_cost += bond_events[0].cost

    # The total value lost to contention must be at least the sum of the bonds
    # posted by the appellants for the failed appeals.
    if total_contention_cost < min_expected_cost:
        raise InvariantViolation(
            "cost_of_contention",
            f"{failed_appeal_count} failed appeals should have a contention cost of at least "
            f"{min_expected_cost}, but the calculated cost was {total_contention_cost} "
            f"(Appellant Costs: {appellant_costs}, Burns: {total_burns})",
        )

    # If there are failed appeals, there should be some cost of contention.
    if failed_appeal_count > 0 and total_contention_cost == 0:
        raise InvariantViolation(
            "cost_of_contention",
            f"Found {failed_appeal_count} failed appeals but the total cost of contention was zero.",
        )
