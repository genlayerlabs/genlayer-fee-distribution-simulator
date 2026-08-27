from dataclasses import dataclass
from src.fee_simulator.utils import is_appeal_round
from src.fee_simulator.utils_round_sizes import (
    get_round_size,
    get_round_size_for_bond,
    get_appeal_index,
    get_normal_round_size,
)
from src.fee_simulator.protocol.types import RoundLabel
from typing import List, Optional


@dataclass(frozen=True)
class AppealBondQuote:
    """Auditable component breakdown for one minimum appeal-bond quote."""

    source_round_index: int
    appeal_round_index: int
    appeal_label: RoundLabel
    committee_basis: str
    committee_size: int
    attempts: int
    leader_unit: int
    validator_unit: int
    leader_component: int
    validator_component: int
    total: int


# Leader appeals from UNDETERMINED. Their bond covers the full cost of the
# next normal round the appeal triggers (round + 2 schedule), matching
# FeeManager.calculateMinAppealBond (Undetermined branch).
LEADER_APPEAL_LABELS = frozenset(
    [
        "APPEAL_LEADER_SUCCESSFUL",
        "APPEAL_LEADER_UNSUCCESSFUL",
    ]
)

# Leader appeals from LEADER_TIMEOUT. The bond prices the configured source
# round. The induced round later drops the timed-out leader, but that participant
# removal does not rewrite the round-cost basis quoted at appeal admission.
LEADER_TIMEOUT_APPEAL_LABELS = frozenset(
    [
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

    - Leader appeal (Undetermined):
        bond = (rotations_next + 1) * (leader_timeout + next_normal_round_size * validators_timeout)
      The appeal triggers a full new normal round (round + 2 on-chain),
      so the bond covers that round's complete cost, including its allowed
      leader rotations.

    - Leader timeout appeal (LeaderTimeout):
        bond = (rotations_next + 1) * (leader_timeout + configured_source_round_size * validators_timeout)
      The induced round later drops the timed-out leader, but participant
      removal does not rewrite the configured round-cost basis quoted at
      appeal admission.

    `rotations` is the per-normal-round rotations list from the transaction
    budget; when omitted, 0 extra rotations are assumed.
    """

    return compute_appeal_bond_quote(
        normal_round_index=normal_round_index,
        leader_timeout=leader_timeout,
        validators_timeout=validators_timeout,
        round_labels=round_labels,
        appeal_round_index=appeal_round_index,
        rotations=rotations,
    ).total


def compute_appeal_bond_quote(
    normal_round_index: int,
    leader_timeout: int,
    validators_timeout: int,
    round_labels: List[RoundLabel],
    appeal_round_index: int = None,
    rotations: Optional[List[int]] = None,
) -> AppealBondQuote:
    """Return the minimum bond together with every pricing input.

    Consensus conformance tests consume this breakdown at the appeal boundary.
    Keeping it beside :func:`compute_appeal_bond` prevents vector exporters from
    reimplementing the formula or inferring the committee basis from final
    payouts after the fact.
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

    label = round_labels[appeal_round_index]
    if label in LEADER_APPEAL_LABELS or label in LEADER_TIMEOUT_APPEAL_LABELS:
        appeal_index = get_appeal_index(appeal_round_index, round_labels)
        if label in LEADER_TIMEOUT_APPEAL_LABELS:
            # Timeout appeal: price the configured source round. The later
            # induced round drops the timed-out leader, but participant removal
            # does not rewrite the configured round-cost basis.
            committee_size = get_round_size(normal_round_index, round_labels)
            committee_basis = "configured_source_round"
        else:
            # Undetermined appeal: full next normal round (round + 2 schedule)
            committee_size = get_normal_round_size(appeal_index + 1)
            committee_basis = "configured_next_normal_round"
        rotations_next = 0
        if rotations is not None and (appeal_index + 1) < len(rotations):
            rotations_next = rotations[appeal_index + 1]
        attempts = rotations_next + 1
        leader_component = attempts * leader_timeout
        validator_component = attempts * committee_size * validators_timeout
        return AppealBondQuote(
            source_round_index=normal_round_index,
            appeal_round_index=appeal_round_index,
            appeal_label=label,
            committee_basis=committee_basis,
            committee_size=committee_size,
            attempts=attempts,
            leader_unit=leader_timeout,
            validator_unit=validators_timeout,
            leader_component=leader_component,
            validator_component=validator_component,
            total=max(leader_component + validator_component, 0),
        )

    # Validator appeal: bond covers only the N+2 appeal validators voting
    # on the existing proposal (no leader fee component)
    appeal_round_size = get_round_size_for_bond(appeal_round_index, round_labels)
    validator_component = appeal_round_size * validators_timeout
    return AppealBondQuote(
        source_round_index=normal_round_index,
        appeal_round_index=appeal_round_index,
        appeal_label=label,
        committee_basis="configured_appeal_round",
        committee_size=appeal_round_size,
        attempts=1,
        leader_unit=leader_timeout,
        validator_unit=validators_timeout,
        leader_component=0,
        validator_component=validator_component,
        total=max(validator_component, 0),
    )
