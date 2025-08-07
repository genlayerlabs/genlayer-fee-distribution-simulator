"""Invariant 9: Sender refund must be non-negative"""

from typing import List
from fee_simulator.models import FeeEvent, TransactionBudget
from fee_simulator.types import RoundLabel
from fee_simulator.core.refunds import compute_sender_refund
from .common import InvariantViolation


def check_refund_non_negativity(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],
) -> None:
    """Invariant 9: Sender refund must be non-negative"""
    refund = compute_sender_refund(
        transaction_budget.senderAddress, fee_events, transaction_budget, round_labels
    )

    if refund < 0:
        raise InvariantViolation(
            "refund_non_negativity", f"Negative refund amount: {refund}"
        )
