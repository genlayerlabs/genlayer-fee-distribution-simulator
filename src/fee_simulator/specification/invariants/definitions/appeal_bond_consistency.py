"""Additional invariant: Appeal bonds should be calculated correctly"""

from typing import List
from src.fee_simulator.protocol.models import FeeEvent, TransactionBudget
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.protocol.constants import APPEAL_ROUND_SIZES
from src.fee_simulator.utils import is_appeal_round
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
    # Committee-expanding appeals only: leader-timeout appeals do not
    # consume a slot in the appeal size schedule.
    expanding_appeal_count = 0
    for i, label in enumerate(round_labels):
        if is_appeal_round(label):
            # Find the appealant cost event
            appealant_events = [
                e
                for e in fee_events
                if e.round_index == i and e.role == "APPEALANT" and e.cost
            ]

            is_timeout_appeal = label.startswith("APPEAL_LEADER_TIMEOUT")

            if appealant_events:
                actual_bond = appealant_events[0].cost

                if is_timeout_appeal:
                    # Leader-timeout appeal: the bond is quoted from the
                    # round-size table at the appealed round's index, not
                    # from the appeal size schedule
                    # (FeeManagerHelpers._leaderTimeoutAppealBond); mirror
                    # the canonical formula.
                    from src.fee_simulator.core.bond_computing import (
                        compute_appeal_bond,
                    )
                    from src.fee_simulator.utils_round_sizes import (
                        find_previous_normal_round,
                    )

                    normal_round_index = find_previous_normal_round(i, round_labels)
                    if normal_round_index is None:
                        normal_round_index = i - 1
                    expected_bond = compute_appeal_bond(
                        normal_round_index=normal_round_index,
                        leader_timeout=transaction_budget.leaderTimeout,
                        validators_timeout=transaction_budget.validatorsTimeout,
                        round_labels=round_labels,
                        appeal_round_index=i,
                        rotations=transaction_budget.rotations,
                    )
                    expected_size = None
                else:
                    # Get expected size using the committee-expanding appeal count
                    expected_size = (
                        APPEAL_ROUND_SIZES[expanding_appeal_count]
                        if expanding_appeal_count < len(APPEAL_ROUND_SIZES)
                        else APPEAL_ROUND_SIZES[-1]
                    )
                    expected_bond = (
                        expected_size * transaction_budget.validatorsTimeout
                        + transaction_budget.leaderTimeout
                    )

                if actual_bond != expected_bond:
                    raise InvariantViolation(
                        "appeal_bond_consistency",
                        f"Appeal at round {i} ({label}): Expected bond {expected_bond} "
                        f"(size {expected_size}), but got {actual_bond}",
                    )

            if not is_timeout_appeal:
                expanding_appeal_count += 1
