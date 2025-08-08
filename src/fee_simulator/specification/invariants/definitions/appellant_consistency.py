"""Invariant 12: N appeals have exactly N bond cost events"""

from typing import List
from src.fee_simulator.protocol.models import FeeEvent, TransactionBudget
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.protocol.constants import APPEAL_ROUND_SIZES
from src.fee_simulator.utils import is_appeal_round
from .common import InvariantViolation


def check_appellant_consistency(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],
) -> None:
    """
    Invariant 12: N appeals have exactly N bond cost events.
    Each appeal round should have exactly one appealant paying a bond.
    """
    # Count appeal rounds
    appeal_rounds = []
    for i, label in enumerate(round_labels):
        if is_appeal_round(label):
            appeal_rounds.append(i)

    # Count bond cost events (appealant paying costs)
    bond_events = []
    for event in fee_events:
        if event.role == "APPEALANT" and event.cost and event.cost > 0:
            bond_events.append(event)

    # Check counts match
    if len(appeal_rounds) != len(bond_events):
        raise InvariantViolation(
            "appellant_consistency",
            f"Found {len(appeal_rounds)} appeal rounds but {len(bond_events)} bond cost events. "
            f"Appeal rounds: {appeal_rounds}",
        )

    # Verify each appeal round has exactly one bond event
    for appeal_round_idx in appeal_rounds:
        matching_events = [e for e in bond_events if e.round_index == appeal_round_idx]

        if len(matching_events) != 1:
            raise InvariantViolation(
                "appellant_consistency",
                f"Appeal round {appeal_round_idx} has {len(matching_events)} bond events, expected exactly 1",
            )

    # Verify bond amounts match expected values
    appeal_count = 0
    for i, event in enumerate(bond_events):
        # Find which appeal number this is
        round_idx = event.round_index
        appeal_idx = appeal_rounds.index(round_idx)

        # Calculate expected bond using the appeal count
        expected_size = (
            APPEAL_ROUND_SIZES[appeal_idx]
            if appeal_idx < len(APPEAL_ROUND_SIZES)
            else APPEAL_ROUND_SIZES[-1]
        )
        expected_bond = (
            expected_size * transaction_budget.validatorsTimeout
            + transaction_budget.leaderTimeout
        )

        if event.cost != expected_bond:
            raise InvariantViolation(
                "appellant_consistency",
                f"Appeal {appeal_idx} (round {round_idx}): Bond amount {event.cost} "
                f"doesn't match expected {expected_bond} (size {expected_size})",
            )
