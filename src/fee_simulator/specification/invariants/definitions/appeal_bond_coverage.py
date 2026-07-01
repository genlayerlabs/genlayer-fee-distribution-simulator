"""
Invariant 3: Appeal Bond Coverage
Appeal bonds must cover appeal round costs
"""

from typing import List
from src.fee_simulator.protocol.models import (
    FeeEvent,
    TransactionBudget,
    TransactionRoundResults,
)
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.utils import is_appeal_round
from src.fee_simulator.utils_round_sizes import find_previous_normal_round
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from .common import InvariantViolation


def check_appeal_bond_coverage(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    transaction_results: TransactionRoundResults,
    round_labels: List[RoundLabel],
) -> None:
    """Invariant 3: Appeal bonds must cover appeal round costs"""
    for i, label in enumerate(round_labels):
        if is_appeal_round(label) and i > 0:
            # Find the most recent normal round before this appeal
            normal_round_index = find_previous_normal_round(i, round_labels)

            if normal_round_index is None:
                raise InvariantViolation(
                    "appeal_bond_coverage",
                    f"No normal round found before appeal at index {i}",
                )

            # Calculate expected bond (per-type formula: validator appeals
            # cover the appeal validators; leader appeals cover the full
            # next normal round)
            expected_bond = compute_appeal_bond(
                normal_round_index=normal_round_index,
                leader_timeout=transaction_budget.leaderTimeout,
                validators_timeout=transaction_budget.validatorsTimeout,
                round_labels=round_labels,
                appeal_round_index=i,
                rotations=transaction_budget.rotations,
            )

            # Find actual bond paid
            appeal_events = [
                e
                for e in fee_events
                if e.round_index == i and e.role == "APPEALANT" and e.cost
            ]

            if appeal_events:
                actual_bond = appeal_events[0].cost

                if actual_bond < expected_bond:
                    raise InvariantViolation(
                        "appeal_bond_coverage",
                        f"Appeal bond ({actual_bond}) < expected bond ({expected_bond}) "
                        f"for round {i}",
                    )
