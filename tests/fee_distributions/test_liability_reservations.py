"""Synthetic custody controls, not operational transaction/appeal replays."""

from itertools import permutations

import pytest

from src.fee_simulator.analysis.liability_reservations import (
    LiabilityCommitment,
    LiabilityReservationBook,
    LiabilityResolution,
    ServiceIdentity,
    required_reserve,
)
from src.fee_simulator.specification.invariants.definitions.common import (
    InvariantViolation,
)


def source(attempt=0, generation=0):
    return ServiceIdentity("synthetic-service", generation, 0, attempt)


@pytest.mark.parametrize("bond,extra,expected", [(100, 0, 150), (101, 0, 151), (101, 25, 176)])
def test_reserve_reuses_the_exact_rounded_bonus(bond, extra, expected):
    assert required_reserve(maximum_reward_bond=bond, other_gain_bound=extra) == expected


def test_unknown_payoff_bound_cannot_admit_work():
    with pytest.raises(InvariantViolation, match="liability_coverage"):
        required_reserve(maximum_reward_bond=100, other_gain_bound=None)


@pytest.mark.parametrize("correction", ["leader-correction", "timeout-correction"])
def test_both_corrections_use_identical_custody_and_preserve_other_owners(correction):
    book = LiabilityReservationBook()
    book.deposit("responsible-owner", 200)
    book.deposit("independent-delegator", 1000)
    book.commit(LiabilityCommitment(source(), "responsible-owner", 175))
    result = LiabilityResolution(correction, 160)
    book.resolve(source(), result, all_liability_final=True)
    book.resolve(source(), result, all_liability_final=True)
    assert book.balance("responsible-owner") == 40
    assert book.balance("independent-delegator") == 1000
    assert book.available("responsible-owner") == 40
    assert book.reserved("responsible-owner") == 0
    assert book.burned == 160
    # The surcharge has no recipient leg for user, developer or appellant.
    assert sum(book.balance(p) for p in ("user", "developer", "appellant")) == 0


def test_one_source_cannot_reassign_owner_or_increase_its_cap():
    book = LiabilityReservationBook()
    book.deposit("original", 300)
    book.deposit("successor", 300)
    book.commit(LiabilityCommitment(source(), "original", 100))
    for replacement in (
        LiabilityCommitment(source(), "successor", 100),
        LiabilityCommitment(source(), "original", 200),
    ):
        with pytest.raises(InvariantViolation, match="liability_identity"):
            book.commit(replacement)
    book.resolve(source(), LiabilityResolution("final", 100), all_liability_final=True)
    assert book.balance("original") == 200
    assert book.balance("successor") == 300


def test_concurrent_attempts_require_distinct_backing_including_across_generations():
    book = LiabilityReservationBook()
    book.deposit("owner", 100)
    book.commit(LiabilityCommitment(source(), "owner", 60))
    book.commit(LiabilityCommitment(source(generation=1), "owner", 40))
    with pytest.raises(InvariantViolation, match="liability_backing"):
        book.commit(LiabilityCommitment(source(attempt=1), "owner", 1))
    assert book.reserved("owner") == 100


def test_unrelated_delegator_balance_cannot_secure_owner_work():
    book = LiabilityReservationBook()
    book.deposit("owner", 99)
    book.deposit("delegator", 10000)
    with pytest.raises(InvariantViolation, match="liability_backing"):
        book.commit(LiabilityCommitment(source(), "owner", 100))


def test_withdrawal_and_early_release_cannot_consume_reserved_funds():
    book = LiabilityReservationBook()
    book.deposit("owner", 150)
    book.commit(LiabilityCommitment(source(), "owner", 100))
    book.withdraw("owner", 50)
    with pytest.raises(InvariantViolation, match="liability_backing"):
        book.withdraw("owner", 1)
    with pytest.raises(InvariantViolation, match="liability_finality"):
        book.resolve(source(), LiabilityResolution("provisional", 0), all_liability_final=False)
    assert book.available("owner") == 0
    book.resolve(source(), LiabilityResolution("final-no-charge", 0), all_liability_final=True)
    book.withdraw("owner", 100)
    assert book.balance("owner") == book.burned == 0


def test_unsupported_charge_is_rejected_atomically_without_releasing_the_cap():
    book = LiabilityReservationBook()
    book.deposit("owner", 200)
    book.commit(LiabilityCommitment(source(), "owner", 100))
    with pytest.raises(InvariantViolation, match="committed_liability"):
        book.resolve(source(), LiabilityResolution("final", 101), all_liability_final=True)
    assert (book.balance("owner"), book.reserved("owner"), book.burned) == (200, 100, 0)


def test_settled_identity_cannot_be_reopened_or_reinterpreted():
    book = LiabilityReservationBook()
    book.deposit("owner", 100)
    book.commit(LiabilityCommitment(source(), "owner", 100))
    book.resolve(source(), LiabilityResolution("final", 80), all_liability_final=True)
    for conflicting in (LiabilityResolution("different", 80), LiabilityResolution("final", 81)):
        with pytest.raises(InvariantViolation, match="liability_identity"):
            book.resolve(source(), conflicting, all_liability_final=True)
    with pytest.raises(InvariantViolation, match="liability_identity"):
        book.commit(LiabilityCommitment(source(), "owner", 20))
    assert (book.balance("owner"), book.burned) == (20, 80)


def test_resolution_needs_the_exact_precommitted_source():
    book = LiabilityReservationBook()
    book.deposit("owner", 100)
    book.commit(LiabilityCommitment(source(), "owner", 100))
    with pytest.raises(InvariantViolation, match="liability_identity"):
        book.resolve(source(generation=1), LiabilityResolution("final", 50), all_liability_final=True)
    assert book.reserved("owner") == 100


@pytest.mark.parametrize("order", list(permutations(range(3))))
def test_settlement_order_preserves_other_reservations_and_conservation(order):
    caps, charges = [40, 60, 100], [0, 50, 75]
    book = LiabilityReservationBook()
    book.deposit("owner", 200)
    for i, cap in enumerate(caps):
        book.commit(LiabilityCommitment(source(attempt=i), "owner", cap))
    withdrawn = 0
    for i in order:
        resolution = LiabilityResolution(f"final-{i}", charges[i])
        book.resolve(source(attempt=i), resolution, all_liability_final=True)
        book.resolve(source(attempt=i), resolution, all_liability_final=True)
        free = book.available("owner")
        book.withdraw("owner", free)
        withdrawn += free
        assert book.balance("owner") >= book.reserved("owner")
        assert book.balance("owner") + book.burned + withdrawn == 200
    assert withdrawn == 75
    assert book.burned == 125
    assert book.balance("owner") == book.reserved("owner") == 0


@pytest.mark.parametrize("bad", [-1, 1.5, True])
def test_custody_quantities_require_nonnegative_integer_units(bad):
    with pytest.raises(ValueError):
        LiabilityCommitment(source(), "owner", bad)
    with pytest.raises(ValueError):
        LiabilityResolution("final", bad)
    with pytest.raises(ValueError):
        LiabilityReservationBook().deposit("owner", bad)
    with pytest.raises(ValueError):
        required_reserve(maximum_reward_bond=bad, other_gain_bound=0)
