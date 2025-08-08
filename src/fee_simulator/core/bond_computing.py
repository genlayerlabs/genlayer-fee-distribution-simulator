from src.fee_simulator.utils import is_appeal_round
from src.fee_simulator.utils_round_sizes import get_round_size_for_bond
from src.fee_simulator.protocol.types import RoundLabel
from typing import List


def compute_appeal_bond(
    normal_round_index: int,
    leader_timeout: int,
    validators_timeout: int,
    round_labels: List[RoundLabel],
    appeal_round_index: int = None,
) -> int:

    # Validate this is actually a normal round index
    if normal_round_index < 0 or normal_round_index >= len(round_labels):
        raise ValueError(f"Invalid normal round index: {normal_round_index}")

    if is_appeal_round(round_labels[normal_round_index]):
        raise ValueError(f"Round {normal_round_index} is not a normal round")

    # If appeal round index is not provided, find the next appeal after the normal round
    if appeal_round_index is None:
        # Find the next appeal round after the normal round
        appeal_round_index = None
        for i in range(normal_round_index + 1, len(round_labels)):
            if is_appeal_round(round_labels[i]):
                appeal_round_index = i
                break

        if appeal_round_index is None:
            raise ValueError(
                f"No appeal round found after normal round {normal_round_index}"
            )

    # Validate the appeal round
    if appeal_round_index < 0 or appeal_round_index >= len(round_labels):
        raise ValueError(f"Invalid appeal round index: {appeal_round_index}")

    if not is_appeal_round(round_labels[appeal_round_index]):
        raise ValueError(f"Round {appeal_round_index} is not an appeal round")

    # Get the size of the appeal round using the new utility
    appeal_round_size = get_round_size_for_bond(appeal_round_index, round_labels)

    # Bond covers the cost of the appeal round
    appeal_cost = appeal_round_size * validators_timeout
    total_cost = appeal_cost + leader_timeout

    return max(total_cost, 0)
