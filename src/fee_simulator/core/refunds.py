from typing import List
from src.fee_simulator.protocol.models import FeeEvent, TransactionBudget
from src.fee_simulator.display.fee_distribution import display_fee_distribution
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.utils import is_appeal_round


def compute_sender_refund(
    sender_address: str,
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],  # New parameter
) -> float:

    # TODO: when introducing toppers, we need to change this function
    sender_cost = 0
    total_paid_from_sender = 0

    for event in fee_events:
        # Skip unsuccessful appeal costs, if leader appeal we skip 2 rounds
        round_label = event.round_label if event.round_label is not None else ""

        if event.role == "APPEALANT":
            if event.earned > 0 and event.round_index is not None:
                # Find the most recent normal round before this appeal
                normal_round_index = event.round_index - 1  # Default
                for i in range(event.round_index - 1, -1, -1):
                    if i < len(round_labels) and not is_appeal_round(round_labels[i]):
                        normal_round_index = i
                        break

                appeal_bond = compute_appeal_bond(
                    normal_round_index=normal_round_index,
                    leader_timeout=transaction_budget.leaderTimeout,
                    validators_timeout=transaction_budget.validatorsTimeout,
                    round_labels=round_labels,  # Pass round labels
                    appeal_round_index=event.round_index,  # Pass the appeal round index
                )
                total_paid_from_sender += event.earned - appeal_bond
            continue

        if "UNSUCCESSFUL" in round_label:
            continue

        if round_label in [
            "SPLIT_PREVIOUS_APPEAL_BOND",
            "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        ]:
            continue

        if event.address == sender_address:
            sender_cost += event.cost
            # Don't count sender's earnings as they include the refund itself
            # which would create a circular dependency
            continue

        total_paid_from_sender += event.earned

    refund = sender_cost - total_paid_from_sender

    if refund < 0:
        display_fee_distribution(fee_events)
        raise ValueError(
            f"Total paid from sender is greater than sender cost: {total_paid_from_sender} > {sender_cost}"
        )

    return refund
