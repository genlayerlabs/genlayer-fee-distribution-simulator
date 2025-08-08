from src.fee_simulator.protocol.models import FeeEvent
from typing import List
from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.utils import is_appeal_round


def compute_unsuccessful_leader_appeal_burn(
    appeal_bond: float, current_round_fee_events: List[FeeEvent]
) -> float:
    """
    Compute how much of the appeal bond should be burned.
    Takes the appeal bond amount and subtracts any earnings that were distributed in the current round.
    """
    earned_in_current_round = 0

    # Find how much was earned/distributed in the current round
    # (e.g., 50 wei to leader in LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND)
    for event in current_round_fee_events:
        earned_in_current_round += event.earned

    burn = appeal_bond - earned_in_current_round
    return burn if burn > 0 else 0


def compute_unsuccessful_validator_appeal_burn(
    current_round_index: int,
    leader_timeout: int,
    validator_timeout: int,
    fee_events: List[FeeEvent],
    round_labels: List[RoundLabel],  # New parameter
) -> float:

    burn = 0

    # Find the most recent normal round before this appeal
    normal_round_index = None
    for i in range(current_round_index - 1, -1, -1):
        if i < len(round_labels) and not is_appeal_round(round_labels[i]):
            normal_round_index = i
            break

    if normal_round_index is None:
        raise ValueError(
            f"No normal round found before appeal at index {current_round_index}"
        )

    cost = compute_appeal_bond(
        normal_round_index=normal_round_index,
        leader_timeout=leader_timeout,
        validators_timeout=validator_timeout,
        round_labels=round_labels,  # Pass round labels
        appeal_round_index=current_round_index,  # Pass the current appeal round
    )
    earned = 0

    for event in fee_events:
        if (
            event.round_index == current_round_index
            and event.round_label is not None
            and "UNSUCCESSFUL" in event.round_label
        ):
            earned += event.earned

    burn = cost - earned
    return burn
