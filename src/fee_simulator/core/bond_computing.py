from src.fee_simulator.utils import is_appeal_round
from src.fee_simulator.utils_round_sizes import (
    get_round_size_for_bond,
    get_appeal_index,
    get_normal_round_size,
)
from src.fee_simulator.protocol.types import RoundLabel
from typing import List, Optional

# Leader-type appeals (UNDETERMINED and LEADER_TIMEOUT appeals). Their bond
# covers the full cost of the next normal round the appeal triggers, matching
# FeeManager.calculateMinAppealBond (LeaderTimeout/Undetermined branch).
LEADER_APPEAL_LABELS = frozenset(
    [
        "APPEAL_LEADER_SUCCESSFUL",
        "APPEAL_LEADER_UNSUCCESSFUL",
        "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
        "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
    ]
)


def compute_appeal_bond(
    normal_round_index: int,
    leader_timeout: int,
    validators_timeout: int,
    round_labels: List[RoundLabel],
    appeal_round_index: int = None,
    rotations: Optional[List[int]] = None,
) -> int:
    """
    Compute the minimum appeal bond, mirroring the on-chain formulas
    (FeeManager.calculateMinAppealBond):

    - Validator appeal (Accepted / ValidatorsTimeout):
        bond = appeal_round_size * validators_timeout
      The N+2 appeal validators re-evaluate the existing proposal; no new
      leader executes, so there is no leader fee component.

    - Leader appeal (Undetermined / LeaderTimeout):
        bond = (rotations_next + 1) * (leader_timeout + next_normal_round_size * validators_timeout)
      The appeal triggers a full new normal round (round + 2 on-chain),
      so the bond covers that round's complete cost, including its allowed
      leader rotations. `rotations` is the per-normal-round rotations list
      from the transaction budget; when omitted, 0 extra rotations are assumed.
    """

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

    if round_labels[appeal_round_index] in LEADER_APPEAL_LABELS:
        # Leader appeal: bond covers the full next normal round
        appeal_index = get_appeal_index(appeal_round_index, round_labels)
        next_normal_size = get_normal_round_size(appeal_index + 1)
        rotations_next = 0
        if rotations is not None and (appeal_index + 1) < len(rotations):
            rotations_next = rotations[appeal_index + 1]
        attempts = rotations_next + 1
        total_cost = attempts * (
            leader_timeout + next_normal_size * validators_timeout
        )
        return max(total_cost, 0)

    # Validator appeal: bond covers only the N+2 appeal validators voting
    # on the existing proposal (no leader fee component)
    appeal_round_size = get_round_size_for_bond(appeal_round_index, round_labels)
    return max(appeal_round_size * validators_timeout, 0)
