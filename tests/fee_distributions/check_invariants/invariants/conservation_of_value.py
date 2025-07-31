"""
Invariant 1: Conservation of Value
Total costs = total earnings (excluding sender) + sender refunds + appealant burns
"""

from typing import List
from fee_simulator.models import FeeEvent, TransactionBudget
from fee_simulator.types import RoundLabel
from fee_simulator.fee_aggregators.aggregated import (
    compute_agg_costs,
    compute_agg_earnings,
    compute_agg_appealant_burnt,
)
from fee_simulator.core.refunds import compute_sender_refund
from .common import InvariantViolation


def check_conservation_of_value(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],
    tolerance: int = 10,
) -> None:
    """Invariant 1: Total costs = total earnings (excluding sender) + sender refunds + appealant burns"""
    total_costs = compute_agg_costs(fee_events)
    total_earnings = compute_agg_earnings(fee_events)

    # Exclude sender's earnings from total_earnings to avoid double counting
    # since compute_sender_refund calculates what the sender should get back
    sender_earnings = sum(
        event.earned
        for event in fee_events
        if event.address == transaction_budget.senderAddress
    )
    earnings_without_sender = total_earnings - sender_earnings

    # Calculate refund
    sender_refund = compute_sender_refund(
        transaction_budget.senderAddress, fee_events, transaction_budget, round_labels
    )

    # Calculate appealant burns (value destroyed in unsuccessful appeals)
    appealant_burns = compute_agg_appealant_burnt(fee_events)

    expected = earnings_without_sender + sender_refund + appealant_burns

    if abs(total_costs - expected) > tolerance:
        raise InvariantViolation(
            "conservation_of_value",
            f"Total costs ({total_costs}) != earnings_without_sender ({earnings_without_sender}) + "
            f"refund ({sender_refund}) + appealant_burns ({appealant_burns}). "
            f"Difference: {total_costs - expected}",
        )