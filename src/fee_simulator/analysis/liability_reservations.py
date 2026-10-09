"""Offline reference model for reserved, owner-attributed service liability.

This is deliberately separate from protocol settlement. Deposits stand for
segregated, collectible funds whose beneficial owner is established externally;
ordinary pooled stake and forecast rewards are not such deposits. Finality,
responsibility and completeness of payoff bounds are trusted model inputs.
"""

from dataclasses import dataclass
from typing import Hashable

from src.fee_simulator.analysis.appeal_liability_requirements import (
    _amounts,
    check_committed_liability,
    check_owned_liability,
)
from src.fee_simulator.protocol.appeal_economics import successful_appeal_profit
from src.fee_simulator.specification.invariants.definitions.common import (
    InvariantViolation,
)


@dataclass(frozen=True)
class ServiceIdentity:
    """Stable source contribution, independent of its later payout label."""

    transaction: str
    generation: int
    round: int
    attempt: int

    def __post_init__(self):
        if not self.transaction:
            raise ValueError("transaction identity is required")
        _amounts(generation=self.generation, round=self.round, attempt=self.attempt)


@dataclass(frozen=True)
class LiabilityCommitment:
    source: Hashable
    principal: str
    cap: int

    def __post_init__(self):
        hash(self.source)
        if not self.principal:
            raise ValueError("accountable principal is required")
        _amounts(cap=self.cap)


@dataclass(frozen=True)
class LiabilityResolution:
    """Final aggregate charge for all obligations assigned to one source."""

    evidence_id: str
    charge: int

    def __post_init__(self):
        if not self.evidence_id:
            raise ValueError("canonical resolution identity is required")
        _amounts(charge=self.charge)


def required_reserve(*, maximum_reward_bond: int, other_gain_bound: int | None) -> int:
    """Conservative R_max + G_max, using the existing rounded bonus formula.

    The bond is the maximum reward-bearing principal, not necessarily the
    minimum quote. The caller must bound every correction attributable to this
    source; this single-bonus helper does not bound multiple distinct rewards.
    """
    _amounts(maximum_reward_bond=maximum_reward_bond)
    bonus = successful_appeal_profit(maximum_reward_bond)
    check_owned_liability(
        appeal_bonus=bonus,
        other_gain_bound=other_gain_bound,
        owner_loss_floor=bonus + (other_gain_bound or 0),
    )
    return bonus + other_gain_bound


class LiabilityReservationBook:
    """Ideal custody contract for synthetic evaluation, with no chain adapter.

    One source's reservation is retained until all of its possible liability is
    final. Settlement atomically collects the charge, burns it and releases the
    unused cap. An asynchronous implementation must retain backing until actual
    collection. Every other claim on these funds must also respect reservations.
    """

    def __init__(self):
        self._balances: dict[str, int] = {}
        self._commitments: dict[Hashable, LiabilityCommitment] = {}
        self._resolutions: dict[Hashable, LiabilityResolution] = {}
        self._burned = 0

    @property
    def burned(self) -> int:
        return self._burned

    def balance(self, principal: str) -> int:
        return self._balances.get(principal, 0)

    def reserved(self, principal: str) -> int:
        return sum(
            item.cap for source, item in self._commitments.items()
            if item.principal == principal and source not in self._resolutions
        )

    def available(self, principal: str) -> int:
        return self.balance(principal) - self.reserved(principal)

    def deposit(self, principal: str, amount: int) -> None:
        if not principal:
            raise ValueError("accountable principal is required")
        _amounts(amount=amount)
        self._balances[principal] = self.balance(principal) + amount

    def withdraw(self, principal: str, amount: int) -> None:
        _amounts(amount=amount)
        if amount > self.available(principal):
            raise InvariantViolation("liability_backing", "Reserved funds cannot leave")
        self._balances[principal] = self.balance(principal) - amount

    def commit(self, commitment: LiabilityCommitment) -> None:
        if commitment.source in self._commitments:
            raise InvariantViolation("liability_identity", "Source already committed")
        if commitment.cap > self.available(commitment.principal):
            raise InvariantViolation("liability_backing", "Insufficient free owner funds")
        self._commitments[commitment.source] = commitment

    def resolve(
        self,
        source: Hashable,
        resolution: LiabilityResolution,
        *,
        all_liability_final: bool,
    ) -> None:
        if all_liability_final is not True:
            raise InvariantViolation("liability_finality", "Source liability remains open")
        commitment = self._commitments.get(source)
        if commitment is None:
            raise InvariantViolation("liability_identity", "Source has no commitment")
        prior = self._resolutions.get(source)
        if prior is not None:
            if prior != resolution:
                raise InvariantViolation("liability_identity", "Conflicting resolution")
            return  # Settlement retries have no additional economic effects.
        check_committed_liability(
            committed_cap=commitment.cap, settled_charge=resolution.charge,
        )
        self._balances[commitment.principal] -= resolution.charge
        self._burned += resolution.charge
        self._resolutions[source] = resolution
