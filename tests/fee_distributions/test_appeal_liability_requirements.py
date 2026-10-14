"""Synthetic controls for proposed requirements; no protocol behavior is changed."""

from fractions import Fraction

import pytest
from hypothesis import given, strategies as st

from src.fee_simulator.analysis.appeal_liability_requirements import (
    check_committed_liability,
    check_liability_backing,
    check_owned_liability,
    leader_expected_payoff,
)
from src.fee_simulator.specification.invariants.definitions.common import (
    InvariantViolation,
)


def test_full_collectible_owner_loss_covers_a_bounded_bonus():
    check_owned_liability(appeal_bonus=100, other_gain_bound=0, owner_loss_floor=100)


def test_unrelated_pool_losses_do_not_count_as_owner_losses():
    # A total pool debit of 100 is insufficient evidence when only 40 is borne
    # by the responsible owner. The external pool members' 60 is not a debit
    # against this owner's private reward.
    with pytest.raises(InvariantViolation, match="owned_liability"):
        check_owned_liability(appeal_bonus=100, other_gain_bound=0, owner_loss_floor=40)


def test_nominal_debt_does_not_replace_collectible_capital():
    with pytest.raises(InvariantViolation, match="owned_liability"):
        check_owned_liability(appeal_bonus=100, other_gain_bound=0, owner_loss_floor=99)


def test_even_one_uncovered_additional_unit_matters():
    with pytest.raises(InvariantViolation, match="owned_liability"):
        check_owned_liability(appeal_bonus=100, other_gain_bound=1, owner_loss_floor=100)


def test_unknown_other_payoff_changes_do_not_default_to_zero():
    with pytest.raises(InvariantViolation, match="liability_coverage"):
        check_owned_liability(appeal_bonus=100, other_gain_bound=None, owner_loss_floor=1000)


def test_forgone_income_can_be_counted_once_when_independently_bounded():
    check_owned_liability(
        appeal_bonus=100, other_gain_bound=5,
        forgone_income_floor=10, owner_loss_floor=95,
    )


@given(
    bonus=st.integers(0, 10**30),
    extra=st.integers(0, 10**30),
    forgone=st.integers(0, 10**30),
    margin=st.integers(0, 10**30),
)
def test_sufficient_bound_holds_for_every_smaller_realized_gain(bonus, extra, forgone, margin):
    loss = max(0, bonus + extra - forgone) + margin
    check_owned_liability(
        appeal_bonus=bonus, other_gain_bound=extra,
        forgone_income_floor=forgone, owner_loss_floor=loss,
    )
    # Boundary plus interior witnesses for the monotone sufficient inequality.
    for realized_extra in (0, extra // 2, extra):
        assert bonus + realized_extra - forgone - loss <= 0


def test_concurrent_obligations_cannot_reuse_the_same_backing():
    check_liability_backing(obligation_caps=[60, 40], collectible_owner_backing=100)
    with pytest.raises(InvariantViolation, match="liability_backing"):
        check_liability_backing(obligation_caps=[60, 41], collectible_owner_backing=100)


def test_later_funding_does_not_raise_an_existing_liability_commitment():
    check_committed_liability(committed_cap=100, settled_charge=100)
    with pytest.raises(InvariantViolation, match="committed_liability"):
        check_committed_liability(committed_cap=100, settled_charge=101)


@pytest.mark.parametrize("penalty_multiple", [1, 5, 10, 20])
def test_honest_participation_boundary_is_explicit(penalty_multiple):
    fee, cost = 100, 50
    penalty = penalty_multiple * fee
    boundary = Fraction(fee - cost, fee + penalty)
    assert leader_expected_payoff(
        service_fee=fee, execution_cost=cost, owner_penalty=penalty,
        invalidation_probability=boundary,
    ) == 0
    assert leader_expected_payoff(
        service_fee=fee, execution_cost=cost, owner_penalty=penalty,
        invalidation_probability=boundary / 2,
    ) > 0
    assert leader_expected_payoff(
        service_fee=fee, execution_cost=cost, owner_penalty=penalty,
        invalidation_probability=boundary + Fraction(1, 1000),
    ) < 0


@pytest.mark.parametrize("bad_amount", [-1, 0.5, True])
def test_financial_bounds_require_nonnegative_integer_units(bad_amount):
    with pytest.raises(ValueError):
        check_owned_liability(
            appeal_bonus=100, other_gain_bound=0, owner_loss_floor=bad_amount,
        )
    with pytest.raises(ValueError):
        check_liability_backing(obligation_caps=[bad_amount], collectible_owner_backing=100)
    with pytest.raises(ValueError):
        check_committed_liability(committed_cap=100, settled_charge=bad_amount)


@pytest.mark.parametrize("bad_probability", [0.5, Fraction(-1, 2), Fraction(3, 2)])
def test_participation_probability_must_be_exact_and_valid(bad_probability):
    with pytest.raises(ValueError):
        leader_expected_payoff(
            service_fee=100, execution_cost=50, owner_penalty=100,
            invalidation_probability=bad_probability,
        )
