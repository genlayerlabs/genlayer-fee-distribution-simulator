"""Conditional economic requirements, not a new fee-settlement policy.

All quantities are in the same monetary unit. Bounds are supplied by a reviewed
economic model; this module cannot establish ownership, causation, collection,
or completeness of the modeled income. It never generates transaction paths.
"""

from fractions import Fraction
from typing import Sequence

from src.fee_simulator.specification.invariants.definitions.common import (
    InvariantViolation,
)


def _amounts(**values: int) -> None:
    for name, value in values.items():
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")


def check_owned_liability(
    *,
    appeal_bonus: int,
    other_gain_bound: int | None,
    owner_loss_floor: int,
    forgone_income_floor: int = 0,
) -> None:
    """Require F + D >= R + G for a specified deviation and its owner group.

    R excludes bond principal. G bounds every other improvement, including
    additional compensation and saved costs. F is a conservative lower bound
    on income forgone relative to the honest baseline. D is an additional NET
    loss borne by this owner group, collectible after caps, not nominal debt or
    losses assigned to unrelated delegators. F and D must not overlap.

    An unspecified G is a coverage gap, never an assumed zero. Passing this
    inequality is conditional on those bounds; it does not validate them.
    """
    if other_gain_bound is None:
        raise InvariantViolation(
            "liability_coverage", "Other payoff changes have no established upper bound"
        )
    _amounts(
        appeal_bonus=appeal_bonus,
        other_gain_bound=other_gain_bound,
        owner_loss_floor=owner_loss_floor,
        forgone_income_floor=forgone_income_floor,
    )
    if forgone_income_floor + owner_loss_floor < appeal_bonus + other_gain_bound:
        raise InvariantViolation(
            "owned_liability",
            "Collectible owner loss plus forgone income does not cover the "
            "appeal bonus and bounded additional payoff",
        )


def check_liability_backing(
    *, obligation_caps: Sequence[int], collectible_owner_backing: int
) -> None:
    """Each simultaneously outstanding obligation needs distinct backing.

    Backing excludes unrelated delegated stake, amounts already reserved for
    other liabilities, and funds that can leave before the obligation settles.
    The caller must supply the complete set of outstanding obligations.
    """
    _amounts(collectible_owner_backing=collectible_owner_backing)
    for cap in obligation_caps:
        _amounts(obligation_cap=cap)
    if sum(obligation_caps) > collectible_owner_backing:
        raise InvariantViolation(
            "liability_backing", "Outstanding liability exceeds collectible owner backing"
        )


def check_committed_liability(*, committed_cap: int, settled_charge: int) -> None:
    """Later changes in funding must not increase an accepted liability cap."""
    _amounts(committed_cap=committed_cap, settled_charge=settled_charge)
    if settled_charge > committed_cap:
        raise InvariantViolation(
            "committed_liability", "Settlement charge exceeds the pre-work commitment"
        )


def leader_expected_payoff(
    *,
    service_fee: int,
    execution_cost: int,
    owner_penalty: int,
    invalidation_probability: Fraction,
) -> Fraction:
    """Illustrative two-outcome participation model: (1-e)F - eP - c.

    F is this owner's fee if the contribution survives; the fee is zero if
    invalidated. P is an additional loss of this owner's funds. Cost c is paid
    in both outcomes. This is not a claim about measured network error rates or
    about every current timeout-compensation branch.
    """
    _amounts(
        service_fee=service_fee,
        execution_cost=execution_cost,
        owner_penalty=owner_penalty,
    )
    if (
        not isinstance(invalidation_probability, Fraction)
        or not 0 <= invalidation_probability <= 1
    ):
        raise ValueError("Invalidation probability must be an exact Fraction in [0, 1]")
    return (
        (1 - invalidation_probability) * service_fee
        - invalidation_probability * owner_penalty
        - execution_cost
    )
