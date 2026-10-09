"""Policy settlement with independently supplied corrective outcomes.

These fixtures exercise collection and provenance, not adversarial transaction
construction or live protocol consensus. Economic counterexamples use synthetic
output mutations below rather than production attack replays.
"""

from dataclasses import replace

import pytest
from hypothesis import given, settings, strategies as st

from src.fee_simulator.core.owner_liability import (
    OwnerCapital, TransactionCase, WorkCommitment, WorkKey, simulate_owner_funded_fees,
)
from src.fee_simulator.core.transaction_processing import (
    process_transaction, process_transaction_with_provenance,
)
from src.fee_simulator.protocol.models import Appeal, Rotation, Round, TransactionBudget, TransactionRoundResults
from src.fee_simulator.specification.invariants.definitions.common import InvariantViolation
from src.fee_simulator.specification.invariants.owner_liability import check_owner_funded_settlement


ADDRESSES = tuple(f"0x{i:040x}" for i in range(1, 31))
LEADER, VOTER = ADDRESSES[:2]
APPELLANT, SENDER = ADDRESSES[-2:]


def normal_round(actors, *, minority=None):
    votes = {actor: "DISAGREE" if actor == minority else "AGREE" for actor in actors}
    votes[actors[0]] = ["LEADER_RECEIPT", votes[actors[0]]]
    return Round(rotations=[Rotation(votes=votes)])


def case_for(kind="leader", *, successful=True, source_rotation=False, name="service"):
    if kind == "normal":
        rounds = [normal_round(ADDRESSES[:5], minority=VOTER)]
        appeals, rotations = [], [0]
    elif kind == "validator":
        initial = normal_round(ADDRESSES[:5], minority=ADDRESSES[4])
        jury = {actor: "DISAGREE" for actor in ADDRESSES[5:12]}
        jury[ADDRESSES[5]] = "AGREE"
        rounds = [initial, Round(rotations=[Rotation(votes=jury)])]
        appeals, rotations = [Appeal(appealantAddress=APPELLANT)], [0, 0]
    else:
        if kind == "timeout":
            source_votes = {actor: "NA" for actor in ADDRESSES[:5]}
            source_votes[LEADER] = ["LEADER_TIMEOUT", "NA"]
            replacement_actors = ADDRESSES[1:5]
        else:
            source_votes = {actor: "DISAGREE" for actor in ADDRESSES[:5]}
            source_votes[LEADER] = ["LEADER_RECEIPT", "AGREE"]
            replacement_actors = ADDRESSES[5:16]
        source = Round(rotations=[Rotation(votes=source_votes)])
        if source_rotation:
            earlier = {ADDRESSES[16]: ["LEADER_TIMEOUT", "NA"]}
            source = Round(rotations=[Rotation(votes=earlier), *source.rotations])
        bookkeeping = Round(rotations=[Rotation(votes={actor: "NA" for actor in ADDRESSES[5:12]})])
        replacement = normal_round(replacement_actors)
        if not successful:
            votes = dict(replacement.rotations[0].votes)
            if kind == "timeout":
                votes = {actor: "NA" for actor in replacement_actors}
                votes[replacement_actors[0]] = ["LEADER_TIMEOUT", "NA"]
            else:
                votes = {actor: "DISAGREE" for actor in replacement_actors}
                votes[replacement_actors[0]] = ["LEADER_RECEIPT", "AGREE"]
            replacement = Round(rotations=[Rotation(votes=votes)])
        rounds = [source, bookkeeping, replacement]
        appeals, rotations = [Appeal(appealantAddress=APPELLANT)], [int(source_rotation), 0]
    return TransactionCase(
        name, ADDRESSES, TransactionRoundResults(rounds=rounds),
        TransactionBudget(leaderTimeout=100, validatorsTimeout=200,
                          appealRounds=len(appeals), rotations=rotations,
                          senderAddress=SENDER, appeals=appeals),
    )


def admission_for(cases, *, other=73, owner_for=None):
    """Declared broad admission ceilings; never sized from realized payouts."""
    owner_for = owner_for or {}
    plans = []
    for case in cases:
        for generation, history in enumerate((*case.discarded_generations, case.results)):
            for index, round_obj in enumerate(history.rounds):
                actors = set()
                for rotation in round_obj.rotations:
                    for actor, vote in rotation.votes.items():
                        if vote != "NA" and vote != "IDLE":
                            actors.add(actor)
                for actor in sorted(actors):
                    plans.append(WorkCommitment(
                        WorkKey(case.transaction, generation, index, actor),
                        owner_for.get(actor, actor), 1000, 50_000, other,
                    ))
    owners = sorted({plan.owner for plan in plans})
    capital = tuple(OwnerCapital(owner, 10**7, 10**9, 500) for owner in owners)
    return capital, tuple(plans)


def run_case(case=None, **admission_options):
    case = case or case_for()
    capital, plans = admission_for([case], **admission_options)
    return simulate_owner_funded_fees([case], capital=capital, commitments=plans)


@pytest.mark.parametrize("kind,bond,bonus", [("leader", 2300, 3450), ("timeout", 1100, 1650)])
def test_correction_collects_from_original_owner_and_preserves_all_existing_payments(kind, bond, bonus):
    result = run_case(case_for(kind))
    tx = result.transactions[0]
    assert len(tx.corrections) == 1
    assert (tx.corrections[0].bond, tx.corrections[0].bonus) == (bond, bonus)
    charge = next(item for item in result.charges if item.key.validator == LEADER and item.key.round_index == 0)
    assert charge.correction_bonus == bonus
    assert charge.other_gains == 73
    assert charge.collected == bonus + 73
    assert tx.fee_events[:-1] == tx.ordinary.fee_events
    assert tx.fee_events[-1].address == LEADER
    assert tx.fee_events[-1].burned == bonus + 73
    assert all(before.delegated_funds == after.delegated_funds
               for before, after in zip(result.opening_capital, result.closing_capital))
    # The independent caller paid a bond; none of the new owner penalty
    # increases that caller's reward or the sender's refund.
    for role in ("SENDER", "APPEALANT"):
        assert [e for e in tx.fee_events if e.role == role] == [e for e in tx.ordinary.fee_events if e.role == role]


@pytest.mark.parametrize("kind", ["leader", "timeout"])
def test_failed_correction_creates_no_success_surcharge(kind):
    result = run_case(case_for(kind, successful=False))
    tx = result.transactions[0]
    assert tx.corrections == ()
    assert tx.fee_events == tx.ordinary.fee_events
    assert all(charge.correction_bonus == charge.other_gains == 0 for charge in result.charges)
    # Failed bond principal disposal, if present, is not charged to self-stake again.
    assert result.collected_burn == sum(e.burned for e in tx.ordinary.fee_events if e.role in ("LEADER", "VALIDATOR"))


def test_validator_appeal_uses_owner_collection_without_new_original_committee_penalties():
    result = run_case(case_for("validator"))
    tx = result.transactions[0]
    assert tx.ordinary.labels == ("SKIP_ROUND", "APPEAL_VALIDATOR_SUCCESSFUL")
    assert tx.corrections == ()
    assert result.collected_burn == 200
    assert all(item.collected == 0 for item in result.charges if item.key.round_index == 0)
    assert sum(e.earned for e in tx.fee_events if e.address == ADDRESSES[4]) == 200
    juror = next(item for item in result.charges if item.key.validator == ADDRESSES[5])
    assert juror.negative_fees == juror.collected == 200
    before = next(item for item in result.opening_capital if item.owner == juror.owner)
    after = next(item for item in result.closing_capital if item.owner == juror.owner)
    assert before.self_funds - after.self_funds == 200
    assert before.delegated_funds == after.delegated_funds


def test_ordinary_voting_negative_fees_use_the_same_owner_collection():
    result = run_case(case_for("normal"))
    assert result.collected_burn == 200
    assert next(item for item in result.charges if item.key.validator == VOTER).negative_fees == 200
    assert result.transactions[0].fee_events == result.transactions[0].ordinary.fee_events


def test_responsibility_follows_final_source_attempt_not_earlier_or_successor_leader():
    result = run_case(case_for(source_rotation=True))
    correction = result.transactions[0].corrections[0]
    assert correction.source_attempt == 1
    assert correction.source.validator == LEADER
    assert next(item for item in result.charges if item.key.validator == ADDRESSES[16]).collected == 0
    assert all(item.correction_bonus == 0 for item in result.charges if item.key.round_index == 2)


def test_generation_provenance_keeps_recomputed_voting_liabilities_distinct():
    case = case_for("normal")
    case = replace(case, budget=case.budget.model_copy(update={"rotations": [1]}),
                   discarded_generations=(case.results,))
    result = run_case(case)
    voter_charges = [item for item in result.charges if item.key.validator == VOTER]
    assert {item.key.generation for item in voter_charges} == {0, 1}
    assert [item.negative_fees for item in voter_charges] == [200, 200]
    assert result.collected_burn == 400
    assert len({event_id for item in voter_charges for event_id in item.negative_fee_event_ids}) == 2


def test_discarded_generation_does_not_create_a_fresh_leader_correction_charge():
    history = case_for().results
    live = case_for("normal")
    case = replace(live, discarded_generations=(history,),
                   budget=TransactionBudget(leaderTimeout=100, validatorsTimeout=200,
                                            appealRounds=1, rotations=[1, 1],
                                            senderAddress=SENDER, appeals=[Appeal(appealantAddress=APPELLANT)]))
    result = run_case(case)
    assert result.transactions[0].corrections == ()
    assert all(item.correction_bonus == 0 for item in result.charges)


def test_preexisting_api_and_serialization_remain_identical_to_provenance_view():
    case = case_for()
    events, labels = process_transaction(list(case.addresses), case.results, case.budget)
    traced = process_transaction_with_provenance(list(case.addresses), case.results, case.budget)
    assert [event.model_dump() for event in events] == [event.model_dump() for event in traced.fee_events]
    assert labels == list(traced.labels)


def test_aliases_share_one_capital_account_and_reserve_aggregate_exposure():
    case = case_for("normal")
    capital, plans = admission_for([case], owner_for={LEADER: "shared-owner", VOTER: "shared-owner"})
    required = sum(plan.cap for plan in plans if plan.owner == "shared-owner")
    capital = tuple(replace(a, self_funds=required + a.other_reserved - 1)
                    if a.owner == "shared-owner" else a for a in capital)
    with pytest.raises(InvariantViolation, match="liability_backing"):
        simulate_owner_funded_fees([case], capital=capital, commitments=plans)


def test_multiple_transactions_and_other_obligations_cannot_reuse_backing():
    cases = [case_for("normal", name="first"), case_for("normal", name="second")]
    capital, plans = admission_for(cases)
    single_cap = next(plan.cap for plan in plans if plan.key.validator == LEADER)
    capital = tuple(replace(a, self_funds=single_cap + a.other_reserved)
                    if a.owner == LEADER else a for a in capital)
    with pytest.raises(InvariantViolation, match="liability_backing"):
        simulate_owner_funded_fees(cases, capital=capital, commitments=plans)


def test_large_delegation_cannot_replace_missing_self_backing():
    case = case_for()
    capital, plans = admission_for([case])
    capital = tuple(replace(a, self_funds=a.other_reserved, delegated_funds=10**30)
                    if a.owner == LEADER else a for a in capital)
    with pytest.raises(InvariantViolation, match="liability_backing"):
        simulate_owner_funded_fees([case], capital=capital, commitments=plans)


@pytest.mark.parametrize("component", ["negative_fee_cap", "correction_bonus_cap"])
def test_component_caps_are_not_interchangeable_or_silently_increased(component):
    case = case_for("normal" if component == "negative_fee_cap" else "leader")
    capital, plans = admission_for([case])
    actor = VOTER if component == "negative_fee_cap" else LEADER
    plans = tuple(replace(p, **{component: 0}) if p.key.validator == actor else p for p in plans)
    with pytest.raises(InvariantViolation, match="committed_liability"):
        simulate_owner_funded_fees([case], capital=capital, commitments=plans)


def test_unknown_gain_bound_and_missing_work_are_coverage_failures():
    case = case_for()
    capital, plans = admission_for([case])
    with pytest.raises(InvariantViolation, match="liability_coverage"):
        replace(plans[0], other_gain_bound=None)
    with pytest.raises(InvariantViolation, match="liability_coverage"):
        simulate_owner_funded_fees([case], capital=capital, commitments=plans[1:])


def test_duplicate_commitment_and_changing_actor_owner_are_rejected():
    cases = [case_for("normal", name="first"), case_for("normal", name="second")]
    capital, plans = admission_for(cases)
    with pytest.raises(InvariantViolation, match="liability_identity"):
        simulate_owner_funded_fees(cases, capital=capital, commitments=(*plans, plans[0]))
    plans = tuple(replace(p, owner=VOTER) if p.key.transaction == "second" and p.key.validator == LEADER else p for p in plans)
    with pytest.raises(InvariantViolation, match="liability_identity"):
        simulate_owner_funded_fees(cases, capital=capital, commitments=plans)


def test_repeated_evaluation_is_deterministic_and_does_not_mutate_admission_inputs():
    case = case_for()
    capital, plans = admission_for([case])
    first = simulate_owner_funded_fees([case], capital=capital, commitments=plans)
    second = simulate_owner_funded_fees([case], capital=capital, commitments=plans)
    assert first == second
    assert all(account.self_funds == 10**7 for account in capital)


def mutate_new_debit(result, **changes):
    tx = result.transactions[0]
    changed = tx.fee_events[-1].model_copy(update=changes)
    return replace(result, transactions=(replace(tx, fee_events=(*tx.fee_events[:-1], changed)),))


@pytest.mark.parametrize("change", [
    {"burned": 1}, {"address": ADDRESSES[5]}, {"earned": 1}, {"role": "SENDER"},
])
def test_certificate_rejects_undercharge_wrong_leader_or_redirected_penalty(change):
    result = mutate_new_debit(run_case(), **change)
    with pytest.raises(InvariantViolation):
        check_owner_funded_settlement(result)


def test_certificate_rejects_nominal_debt_without_collection():
    result = run_case()
    with pytest.raises(InvariantViolation, match="owner_collection"):
        check_owner_funded_settlement(replace(result, closing_capital=result.opening_capital))


def test_certificate_rejects_delegator_payment_and_consumed_other_reserves():
    result = run_case()
    for field in ("delegated_funds", "other_reserved"):
        changed = tuple(replace(a, **{field: getattr(a, field) - 1}) if a.owner == LEADER else a
                        for a in result.closing_capital)
        with pytest.raises(InvariantViolation):
            check_owner_funded_settlement(replace(result, closing_capital=changed))


def test_certificate_rejects_missing_burn_missing_correction_and_wrong_source_attempt():
    result = run_case()
    tx = result.transactions[0]
    mutations = [
        replace(result, collected_burn=result.collected_burn - 1),
        replace(result, transactions=(replace(tx, corrections=()),)),
        replace(result, transactions=(replace(tx, corrections=(replace(tx.corrections[0], source_attempt=1),)),)),
    ]
    for changed in mutations:
        with pytest.raises(InvariantViolation):
            check_owner_funded_settlement(changed)


def test_certificate_rejects_one_voting_fee_counted_twice():
    result = run_case(case_for("normal"))
    charges = tuple(replace(c, negative_fee_event_ids=c.negative_fee_event_ids * 2)
                    if c.negative_fees else c for c in result.charges)
    with pytest.raises(InvariantViolation, match="liability_identity"):
        check_owner_funded_settlement(replace(result, charges=charges))


@given(extra=st.integers(0, 10**24), realized_fraction=st.integers(0, 100),
       delegated=st.integers(0, 10**30))
@settings(max_examples=50)
def test_collected_policy_loss_covers_every_bounded_extra_gain(extra, realized_fraction, delegated):
    # Fixed independent corrective outcome; vary only the declared economic
    # envelope and capital. This is a conditional bound, not a path search.
    case = case_for()
    capital, plans = admission_for([case], other=extra)
    required = {}
    for plan in plans:
        required[plan.owner] = required.get(plan.owner, 0) + plan.cap
    capital = tuple(replace(a, self_funds=required[a.owner] + a.other_reserved,
                            delegated_funds=delegated) for a in capital)
    result = simulate_owner_funded_fees([case], capital=capital, commitments=plans)
    charge = next(c for c in result.charges if c.key.validator == LEADER and c.key.round_index == 0)
    owner_before = next(a.self_funds for a in result.opening_capital if a.owner == LEADER)
    owner_after = next(a.self_funds for a in result.closing_capital if a.owner == LEADER)
    realized_extra = extra * realized_fraction // 100
    assert charge.correction_bonus + realized_extra - (owner_before - owner_after) <= 0
    assert all(a.delegated_funds == delegated for a in result.closing_capital)


def test_insufficient_admission_capacity_fails_before_any_case_executes(monkeypatch):
    case = case_for()
    capital, plans = admission_for([case])
    capital = tuple(replace(a, self_funds=a.other_reserved) for a in capital)

    def must_not_execute(*args, **kwargs):
        pytest.fail("Work ran before its capital was reserved")

    monkeypatch.setattr("src.fee_simulator.core.owner_liability.process_transaction_with_provenance", must_not_execute)
    with pytest.raises(InvariantViolation, match="liability_backing"):
        simulate_owner_funded_fees([case], capital=capital, commitments=plans)


def test_certificate_rejects_a_mutated_appeal_reward_even_if_both_ledgers_match():
    result = run_case()
    tx = result.transactions[0]
    events = tuple(e.model_copy(update={"earned": e.earned - 1})
                   if e.role == "APPEALANT" and e.earned else e for e in tx.ordinary.fee_events)
    ordinary = replace(tx.ordinary, fee_events=events)
    changed = replace(tx, ordinary=ordinary, fee_events=(*events, *tx.fee_events[len(events):]))
    with pytest.raises(InvariantViolation, match="liability_reward"):
        check_owner_funded_settlement(replace(result, transactions=(changed,)))


def test_mutating_a_refund_to_fund_the_penalty_is_rejected():
    result = run_case()
    tx = result.transactions[0]
    events = tuple(e.model_copy(update={"earned": e.earned + 1})
                   if e.role == "SENDER" and e.earned else e for e in tx.fee_events)
    with pytest.raises(InvariantViolation, match="liability_funding_separation"):
        check_owner_funded_settlement(replace(result, transactions=(replace(tx, fee_events=events),)))


def test_hashed_voting_inputs_retain_owner_collection():
    case = case_for("normal")
    votes = case.results.rounds[0].rotations[0].votes
    hashed = {actor: [*vote, "0xab"] if isinstance(vote, list) else [vote, "0xab"]
              for actor, vote in votes.items()}
    case = replace(case, results=TransactionRoundResults(rounds=[Round(rotations=[Rotation(votes=hashed)])]))
    result = run_case(case)
    assert result.collected_burn == 200


def test_successful_batch_collects_independent_work_and_keeps_other_reservations():
    cases = [case_for("normal", name="first"), case_for("normal", name="second")]
    capital, plans = admission_for(cases)
    result = simulate_owner_funded_fees(cases, capital=capital, commitments=plans)
    assert result.collected_burn == 400
    before = next(a for a in capital if a.owner == VOTER)
    after = next(a for a in result.closing_capital if a.owner == VOTER)
    assert before.self_funds - after.self_funds == 400
    assert before.other_reserved == after.other_reserved == 500


def test_bounded_arithmetic_certificate_and_weak_loss_controls():
    # Exhaust the declared finite domain, independent of the settlement code.
    # This checks the integer theorem and that weakening its premise is caught.
    witnesses = 0
    for bond in range(1, 33):
        bonus = bond * 5 // 2 - bond
        for bound in range(9):
            debit = bonus + bound
            for actual in range(bound + 1):
                assert bonus + actual - debit <= 0
                witnesses += 1
            assert bonus + bound - (debit - 1) == 1
    assert witnesses == 1440
