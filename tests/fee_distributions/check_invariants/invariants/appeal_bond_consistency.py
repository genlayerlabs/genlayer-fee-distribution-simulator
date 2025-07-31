"""Additional invariant: Appeal bonds should be calculated correctly"""

from typing import List
from fee_simulator.models import FeeEvent, TransactionBudget
from fee_simulator.types import RoundLabel
from fee_simulator.constants import APPEAL_ROUND_SIZES
from fee_simulator.utils import is_appeal_round
from .common import InvariantViolation


def check_appeal_bond_consistency(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],
) -> None:
    """
    Additional invariant: Appeal bonds should be calculated correctly based on
    the new APPEAL_ROUND_SIZES structure.
    """
    appeal_count = 0
    for i, label in enumerate(round_labels):
        if is_appeal_round(label):
            # Find the appealant cost event
            appealant_events = [
                e
                for e in fee_events
                if e.round_index == i and e.role == "APPEALANT" and e.cost
            ]

            if appealant_events:
                actual_bond = appealant_events[0].cost

                # Get expected size using the appeal count
                expected_size = (
                    APPEAL_ROUND_SIZES[appeal_count]
                    if appeal_count < len(APPEAL_ROUND_SIZES)
                    else APPEAL_ROUND_SIZES[-1]
                )
                expected_bond = (
                    expected_size * transaction_budget.validatorsTimeout
                    + transaction_budget.leaderTimeout
                )

                if actual_bond != expected_bond:
                    raise InvariantViolation(
                        "appeal_bond_consistency",
                        f"Appeal {appeal_count} (round {i}): Expected bond {expected_bond} "
                        f"(size {expected_size}), but got {actual_bond}",
                    )

            appeal_count += 1
