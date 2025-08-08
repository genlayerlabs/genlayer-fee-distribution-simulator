"""Invariant 13: Leader timeout earnings <= leader timeout amount (except for special rounds)"""

from typing import List
from src.fee_simulator.protocol.models import FeeEvent, TransactionBudget
from src.fee_simulator.protocol.types import RoundLabel
from .common import InvariantViolation


def check_leader_timeout_earning(
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],
) -> None:
    """Invariant 13: Leader timeout earnings <= leader timeout amount (except for special rounds)"""
    for i, label in enumerate(round_labels):
        if "LEADER_TIMEOUT" in label:
            leader_events = [
                e
                for e in fee_events
                if e.round_index == i and e.role == "LEADER" and e.earned
            ]
            for event in leader_events:
                # Special case: LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND allows 150% earning
                if label == "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND":
                    if event.earned > transaction_budget.leaderTimeout * 1.5:
                        raise InvariantViolation(
                            "leader_timeout_earning",
                            f"Leader earned {event.earned} > 150% of timeout ({transaction_budget.leaderTimeout * 1.5}) "
                            f"in round {i}",
                        )
                elif event.earned > transaction_budget.leaderTimeout:
                    raise InvariantViolation(
                        "leader_timeout_earning",
                        f"Leader earned {event.earned} > timeout {transaction_budget.leaderTimeout} "
                        f"in round {i}",
                    )
