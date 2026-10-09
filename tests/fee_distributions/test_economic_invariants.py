"""Defensive policy checks using synthetic ledgers, not protocol attack paths."""

from dataclasses import replace
from fractions import Fraction

import pytest
from hypothesis import given, strategies as st

from src.fee_simulator.protocol.appeal_economics import successful_appeal_reward
from src.fee_simulator.protocol.models import (
    FeeEvent, Rotation, Round, TransactionBudget, TransactionRoundResults,
)
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.specification.invariants.checker import check_all_invariants
from src.fee_simulator.specification.invariants.definitions.common import InvariantViolation
from src.fee_simulator.specification.invariants.economic import (
    EconomicComparison, appeal_expected_payoff, check_appeal_participation,
    check_economic_invariants, owner_net_payoffs,
)


def event(address, role, **amounts):
    return FeeEvent(sequence_id=1, address=address, role=role, **amounts)


def comparison():
    return EconomicComparison(
        baseline_events=[
            event("user", "SENDER", cost=1000, earned=900),
            event("leader", "LEADER", earned=60),
            event("validator", "VALIDATOR", earned=40),
        ],
        owners={"user": "u", "leader": "l", "alias": "l", "validator": "v"},
        coalition=frozenset({"l"}),
        protected_loss_limits={"u": 0, "v": 0},
        rationale="Synthetic same-work settlement: no extra coalition reward is justified.",
    )


def test_conserved_value_does_not_imply_no_profitable_deviation():
    case = comparison()
    changed = [
        event("user", "SENDER", cost=1000, earned=870),
        event("leader", "LEADER"),
        event("alias", "APPEALANT", cost=20, earned=110),
        event("validator", "VALIDATOR", earned=40),
    ]
    assert sum(e.cost for e in changed) == sum(e.earned for e in changed)
    ok, failures = check_economic_invariants(changed, case)
    assert not ok
    assert failures == [
        "no_profitable_deviation: Coalition gains 30 time units over baseline",
        "honest_liability: Owner u loses 30 extra time units; limit is 0",
    ]


@given(extra=st.integers(min_value=1, max_value=10**30))
def test_any_positive_increment_is_detected_without_round_filters(extra):
    case = comparison()
    changed = list(case.baseline_events) + [
        event("alias", "APPEALANT", earned=extra, round_label="SKIP_ROUND")
    ]
    ok, failures = check_economic_invariants(changed, case)
    assert not ok
    assert failures == [
        f"no_profitable_deviation: Coalition gains {extra} time units over baseline"
    ]


def test_absolute_honest_profit_is_not_a_deviation():
    case = comparison()
    assert owner_net_payoffs(case.baseline_events, case.owners)["l"] == 60
    assert check_economic_invariants(case.baseline_events, case) == (True, [])


def test_alias_and_role_split_preserve_owner_net():
    case = comparison()
    changed = [
        event("user", "SENDER", cost=1000, earned=900),
        event("leader", "LEADER", earned=20),
        event("alias", "APPEALANT", cost=20, earned=60),
        event("validator", "VALIDATOR", earned=40),
    ]
    assert owner_net_payoffs(changed, case.owners) == owner_net_payoffs(case.baseline_events, case.owners)
    assert check_economic_invariants(changed, case) == (True, [])


def test_user_paying_for_additional_work_is_allowed():
    case = replace(comparison(), coalition=frozenset({"u"}), protected_loss_limits={"l": 0, "v": 0})
    changed = list(case.baseline_events) + [
        event("user", "SENDER", cost=30),
        event("validator", "VALIDATOR", earned=30),
    ]
    assert check_economic_invariants(changed, case) == (True, [])


def test_self_refund_does_not_extract_value():
    case = replace(comparison(), coalition=frozenset({"u"}), protected_loss_limits={"v": 0})
    changed = list(case.baseline_events) + [
        event("user", "SENDER", cost=50, earned=50),
    ]
    assert check_economic_invariants(changed, case) == (True, [])


def test_honest_liability_is_checked_even_without_coalition_gain():
    case = replace(comparison(), coalition=frozenset({"u"}), protected_loss_limits={"v": 5})
    changed = list(case.baseline_events) + [event("validator", "VALIDATOR", burned=6)]
    ok, failures = check_economic_invariants(changed, case)
    assert not ok
    assert failures == ["honest_liability: Owner v loses 6 extra time units; limit is 5"]


@pytest.mark.parametrize("appellant_burn", [0, 40, 100])
def test_bond_disposal_is_not_a_second_debit(appellant_burn):
    events = [
        event("a", "APPEALANT", cost=100, round_index=1),
        event("a", "APPEALANT", burned=appellant_burn, round_index=1),
        event("b", "VALIDATOR", earned=20, burned=7, slashed=3, staked=1000),
    ]
    assert owner_net_payoffs(events, {"a": "a", "b": "b"}) == {"a": -100, "b": 10}


def test_incomplete_bond_ledger_is_rejected():
    with pytest.raises(InvariantViolation, match="burn.*exceeds recorded bond debit"):
        owner_net_payoffs([event("a", "APPEALANT", burned=1)], {"a": "a"})


def test_bond_disposal_can_be_recorded_in_a_successor_round():
    events = [
        event("a", "APPEALANT", cost=100, round_index=1),
        event("a", "APPEALANT", burned=60, round_index=2),
    ]
    assert owner_net_payoffs(events, {"a": "owner"}) == {"owner": -100}
    assert owner_net_payoffs(list(reversed(events)), {"a": "owner"}) == {"owner": -100}


def test_aggregate_bond_check_does_not_use_another_appellants_deposit():
    events = [
        event("a", "APPEALANT", cost=100, round_index=1),
        event("b", "APPEALANT", burned=60, round_index=2),
    ]
    with pytest.raises(InvariantViolation, match="burn.*exceeds recorded bond debit"):
        owner_net_payoffs(events, {"a": "owner", "b": "owner"})


@pytest.mark.parametrize("change, expected", [
    ({"owners": {"user": "u", "leader": "l", "validator": "v"}}, "Missing owner"),
    ({"required_roles": frozenset({"DEVELOPER"})}, "DEVELOPER"),
    ({"required_components": frozenset({"receipt_reimbursements"})}, "receipt_reimbursements"),
    ({"rationale": ""}, "rationale"),
    ({"coalition": frozenset()}, "coalition"),
    ({"coalition": frozenset({"unknown"})}, "unmapped"),
    ({"protected_loss_limits": {"unknown": 0}}, "unmapped"),
    ({"protected_loss_limits": {"l": 0}}, "overlap"),
    ({"protected_loss_limits": {"v": -1}}, "nonnegative integer"),
    ({"protected_loss_limits": {"v": 0.5}}, "nonnegative integer"),
])
def test_missing_assumptions_or_accounting_fail_closed(change, expected):
    case = replace(comparison(), **change)
    ok, failures = check_economic_invariants(
        list(case.baseline_events) + [event("alias", "APPEALANT")], case
    )
    assert not ok
    assert expected.lower() in " ".join(failures).lower()


def test_unrepresented_coalition_cannot_pass_vacuously():
    case = replace(comparison(), owners={**comparison().owners, "absent": "absent"}, coalition=frozenset({"absent"}))
    ok, failures = check_economic_invariants(case.baseline_events, case)
    assert not ok
    assert "no events" in failures[0]


def test_normal_simulator_output_uses_optional_economic_check():
    addresses = [f"0x{i:040x}" for i in range(1, 7)]
    votes = {addresses[0]: ["LEADER_RECEIPT", "AGREE"]}
    votes.update({address: "AGREE" for address in addresses[1:5]})
    results = TransactionRoundResults(rounds=[Round(rotations=[Rotation(votes=votes)])])
    budget = TransactionBudget(leaderTimeout=100, validatorsTimeout=200, appealRounds=0,
                               rotations=[0], senderAddress=addresses[-1], appeals=[])
    events, labels = process_transaction(addresses, results, budget)
    case = EconomicComparison(
        baseline_events=events, owners={address: address for address in addresses},
        coalition=frozenset({addresses[0]}), rationale="Identical honest settlement",
    )
    assert check_all_invariants(events, budget, results, labels, economic_comparison=case) == (True, [])
    incomplete = replace(case, required_components=frozenset({"developer_payments"}))
    ok, failures = check_all_invariants(events, budget, results, labels, economic_comparison=incomplete)
    assert not ok
    assert "economic_coverage:" in failures[-1]


@pytest.mark.parametrize("gross_return, probability, cost, expected", [
    (150, Fraction(2, 3), 0, Fraction(0)),
    (200, Fraction(1, 2), 0, Fraction(0)),
    (250, Fraction(1, 2), 0, Fraction(25)),
    (250, Fraction(1, 2), 25, Fraction(0)),
    (250, Fraction(1, 2), 26, Fraction(-1)),
])
def test_paper_reward_participation_constraint(gross_return, probability, cost, expected):
    terms = dict(bond=100, gross_success_return=gross_return,
                 success_probability=probability, private_cost=cost)
    assert appeal_expected_payoff(**terms) == expected
    if expected > 0:
        check_appeal_participation(**terms)
    else:
        with pytest.raises(InvariantViolation, match="appeal_participation"):
            check_appeal_participation(**terms)


@given(bond=st.integers(min_value=1, max_value=10**30))
def test_reward_floor_uses_actual_integer_settlement(bond):
    reward = successful_appeal_reward(bond)
    result = appeal_expected_payoff(bond=bond, gross_success_return=reward,
                                    success_probability=Fraction(1, 2))
    assert result == Fraction(reward, 2) - bond
    assert result <= Fraction(bond, 4)


@pytest.mark.parametrize("change", [
    {"bond": 0}, {"bond": -1}, {"bond": 1.5}, {"private_cost": -1},
    {"gross_success_return": -1}, {"success_probability": 0.5},
    {"success_probability": Fraction(2)},
])
def test_invalid_paper_terms_are_rejected(change):
    terms = dict(bond=100, gross_success_return=250, success_probability=Fraction(1, 2))
    with pytest.raises(ValueError):
        appeal_expected_payoff(**{**terms, **change})
