"""Deterministic N-B02 funding vectors grounded in round FeeEvents."""

from copy import deepcopy

from src.fee_simulator.core.attribution import settle_attribution
from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.protocol.models import FeeEvent


ADDRESSES = [f"0x{i:040x}" for i in range(1, 201)]
COMPONENTS = ("taxableWork", "appellantProfit", "executionBacking", "overlay")


def _evidence(successful):
    outcome = "VALIDATOR_APPEAL_SUCCESSFUL" if successful else "VALIDATOR_APPEAL_UNSUCCESSFUL"
    path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", outcome, "END"]
    transaction, budget = path_to_transaction_results(
        path, ADDRESSES, ADDRESSES[-1], ADDRESSES[-2], 100, 200
    )
    events, labels = process_transaction(ADDRESSES, transaction, budget)
    assert labels[1] == f"APPEAL_{outcome.replace('APPEAL_', '')}"
    bond = next(event.cost for event in events if event.role == "APPEALANT" and event.cost)
    jury = set(transaction.rounds[1].rotations[-1].votes)
    original = set(transaction.rounds[0].rotations[-1].votes)
    jury_events = [event for event in events if event.round_index == 1
                   and event.role == "VALIDATOR" and event.address in jury]
    vindication = [event for event in events if event.round_index == 1
                   and event.role == "VALIDATOR" and event.address in original and event.earned]
    normal = [event for event in events if event.round_index == 0
              and event.role in ("LEADER", "VALIDATOR") and event.earned]
    payout = sum(event.earned for event in events if event.role == "APPEALANT")
    # FeeEvents are settlement entitlements, not a quote for all selected
    # seats. Failed validator appeals fold forfeited bond principal into the
    # committee payout, so strip it before attributing fee-funded wages.
    committee_paid = sum(event.earned for event in jury_events)
    fee_wages = committee_paid - (0 if successful else bond)
    if fee_wages < 0:
        raise ValueError("bond-funded committee payout exceeds earned committee value")
    return {
        "source": "round-engine-generated",
        "bond": bond, "juryWork": fee_wages,
        "juryGrossPayout": committee_paid,
        "juryEvidence": [event.sequence_id for event in jury_events],
        "vindication": sum(event.earned for event in vindication),
        "vindicationEvidence": [event.sequence_id for event in vindication],
        "normalWork": sum(event.earned for event in normal),
        "normalEvidence": [event.sequence_id for event in normal],
        "profit": max(0, payout - bond),
        "appellantEvidence": [event.sequence_id for event in events if event.role == "APPEALANT" and event.earned],
    }


def _replacement_events():
    """Fixture FeeEvents for completed duties absent from the round engine."""
    return [
        FeeEvent(sequence_id=9001, address=ADDRESSES[90], round_index=1,
                 role="LEADER", earned=100),
        FeeEvent(sequence_id=9002, address=ADDRESSES[91], round_index=1,
                 role="VALIDATOR", earned=200),
    ]


def _successive_evidence():
    path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL", "VALIDATOR_APPEAL_SUCCESSFUL", "END"]
    transaction, budget = path_to_transaction_results(
        path, ADDRESSES, ADDRESSES[-1], ADDRESSES[-2], 100, 200
    )
    events, _ = process_transaction(ADDRESSES, transaction, budget)
    jury = []
    for round_index in (1, 2):
        addresses = set(transaction.rounds[round_index].rotations[-1].votes)
        observed = [event for event in events if event.round_index == round_index
                    and event.role == "VALIDATOR" and event.address in addresses]
        bond = next(event.cost for event in events if event.round_index == round_index
                    and event.role == "APPEALANT" and event.cost)
        committee_paid = sum(event.earned for event in observed)
        work = committee_paid - (bond if round_index == 1 else 0)
        jury.append({"work": work, "juryGrossPayout": committee_paid,
                     "ids": [event.sequence_id for event in observed], "bond": bond})
    payout = sum(event.earned for event in events if event.round_index == 2
                 and event.role == "APPEALANT")
    normal = [event for event in events if event.round_index == 0
              and event.role in ("LEADER", "VALIDATOR") and event.earned]
    return {"source": "round-engine-generated", "jury": jury,
            "profit": max(0, payout - jury[1]["bond"]),
            "normalWork": sum(event.earned for event in normal),
            "normalIds": [event.sequence_id for event in normal]}


def _ordinary(key, payer, primary, overlay):
    return {"id": key, "payer": payer, "reserve": {"primary": primary, "overlay": overlay}}


def _admission(key, payer, generation, book_round, kind, reserve, *, successful=False,
               base=0, bond=0, voided=False):
    return {
        "id": key, "payer": payer, "generation": generation,
        "bookRound": book_round, "quotaKind": kind,
        "result": "successful" if successful else "unsuccessful",
        "bondPrincipal": bond, "voided": voided,
        "prepaidScheduledBase": base,
        "reserve": dict(zip(COMPONENTS, reserve)),
    }


def _appeal_charge(kind, amount, admission, **extra):
    return {"kind": kind, "amount": amount, "sourceFundingId": admission["id"],
            "generation": admission["generation"], "bookRound": admission["bookRound"], **extra}


def _ordinary_charge(amount, origin, ids):
    return {"kind": "taxableWork", "amount": amount, "sourceFundingId": "ordinary",
            "origin": origin, "feeEventIds": ids}


def _case(name, ordinary, admissions, charges, evidence, developer, dao, rescue=None,
          overlay_bps=1000):
    source = {"name": name, "overlayBps": overlay_bps,
              "actualOverlayRouted": {"developer": developer, "dao": dao},
              "ordinaryFunding": ordinary, "rescueFunding": rescue or [],
              "admissions": admissions, "charges": charges,
              "observedRoundFees": evidence}
    source["expected"] = settle_attribution(source)
    return source


def attribution_vectors(*, decimal_strings=False):
    success = _evidence(True)
    failure = _evidence(False)
    replacement = _replacement_events()
    replacement_work = sum(event.earned for event in replacement)
    replacement_ids = [event.sequence_id for event in replacement]
    cases = []

    beyond = _admission("a0", "appellantA", 0, 1, "beyondQuota",
                        (1100, 2200, 300, 100), successful=True, bond=success["bond"])
    cases.append(_case(
        "beyond_quota_success_complete_work",
        [_ordinary("ordinary0", "sender", 500, 50),
         _ordinary("ordinary1", "topper", 1000, 100)], [beyond],
        [_ordinary_charge(failure["normalWork"], "original-generation-work", failure["normalEvidence"]),
         _ordinary_charge(success["vindication"], "original-round-vindication", success["vindicationEvidence"]),
         _appeal_charge("taxableWork", success["juryWork"], beyond,
                        workKind="jury", feeEventIds=success["juryEvidence"]),
         _appeal_charge("taxableWork", replacement_work, beyond,
                        workKind="replacement", feeEventIds=replacement_ids),
         _appeal_charge("appellantProfit", success["profit"], beyond,
                        feeEventIds=success["appellantEvidence"]),
         _appeal_charge("executionBacking", 40, beyond, origin="supplied-execution-cost")],
        {"original": failure, "appeal": success,
         "replacementFixture": [{"sequenceId": event.sequence_id, "role": event.role,
                          "earned": event.earned} for event in replacement]},
        111, 111,
    ))

    failed = _admission("a1", "appellantB", 0, 1, "beyondQuota",
                        (1600, 2100, 100, 200), bond=failure["bond"])
    cases.append(_case(
        "beyond_quota_failure_overlay_route_failed",
        [_ordinary("ordinary0", "sender", 400, 80),
         _ordinary("ordinary1", "topper", 1000, 80)], [failed],
        [_ordinary_charge(failure["normalWork"], "original-normal-work", failure["normalEvidence"]),
         _appeal_charge("taxableWork", failure["juryWork"], failed,
                        workKind="jury", feeEventIds=failure["juryEvidence"])],
        failure, 0, 0,
    ))

    for replacement_events, name, actual_overlay in (
        (replacement[:1], "in_quota_below_prepaid_base", 120),
        (replacement, "in_quota_above_prepaid_base", 140),
    ):
        work = sum(event.earned for event in replacement_events)
        in_quota = _admission(f"iq{work}", "appellantA", 0, 1,
                              "inQuota", (300, 0, 50, 60), successful=True,
                              base=150, bond=success["bond"])
        cases.append(_case(
            name, [_ordinary("ordinary0", "sender", 1800, 250)], [in_quota],
            [_ordinary_charge(success["juryWork"], "prepaid-appeal-jury", success["juryEvidence"]),
             _ordinary_charge(success["vindication"], "original-round-vindication", success["vindicationEvidence"]),
             _appeal_charge("taxableWork", work, in_quota,
                            workKind="replacement", feeEventIds=[e.sequence_id for e in replacement_events])],
            {"appeal": success, "replacementFixture": [e.model_dump() for e in replacement_events]},
            actual_overlay // 2, actual_overlay // 2,
        ))

    old = _admission("g0-a0", "appellantA", 0, 1, "beyondQuota",
                     (1600, 2200, 0, 160), bond=success["bond"], voided=True)
    reused = _admission("g1-a0", "appellantB", 1, 1, "beyondQuota",
                        (1000, 2200, 0, 160), successful=True, bond=success["bond"])
    cases.append(_case(
        "void_reuse_recompute_keeps_old_earned_cost",
        [_ordinary("ordinary0", "sender", 100, 100)], [old, reused],
        [_appeal_charge("taxableWork", failure["juryWork"], old,
                        workKind="jury", feeEventIds=failure["juryEvidence"]),
         _appeal_charge("taxableWork", success["juryWork"], reused,
                        workKind="jury", feeEventIds=success["juryEvidence"]),
         _appeal_charge("appellantProfit", success["profit"], reused,
                        feeEventIds=success["appellantEvidence"])],
        {"generation0": failure, "generation1": success}, 120, 120,
    ))

    limited = _admission("limited", "appellantA", 0, 1, "beyondQuota",
                         (600, 2100, 0, 0), successful=True, bond=success["bond"])
    cases.append(_case(
        "typed_work_overrun_uses_ordinary_then_rescue",
        [_ordinary("ordinary0", "sender", 100, 0)], [limited],
        [_appeal_charge("taxableWork", success["juryWork"], limited,
                        workKind="jury", feeEventIds=success["juryEvidence"]),
         _appeal_charge("appellantProfit", success["profit"], limited,
                        feeEventIds=success["appellantEvidence"])],
        success, 0, 0, rescue=[_ordinary("rescue0", "rescuer", 300, 0)],
    ))

    successive = _successive_evidence()
    prior_vindication = FeeEvent(sequence_id=9100, address=ADDRESSES[92],
                                 round_index=2, role="VALIDATOR", earned=200)
    first = _admission("g0-a0", "appellantA", 0, 1, "beyondQuota",
                       (successive["jury"][0]["work"] + prior_vindication.earned, 0, 0, 0),
                       bond=successive["jury"][0]["bond"])
    second = _admission("g0-a1", "appellantB", 0, 3, "beyondQuota",
                        (successive["jury"][1]["work"], successive["profit"], 0, 0),
                        successful=True, bond=successive["jury"][1]["bond"])
    cases.append(_case(
        "successive_appeals_keep_distinct_book_round_ids",
        [_ordinary("ordinary0", "sender", 1000, 0)], [first, second],
        [_ordinary_charge(successive["normalWork"], "original-normal-work", successive["normalIds"]),
         _appeal_charge("taxableWork", successive["jury"][0]["work"], first,
                        workKind="jury", feeEventIds=successive["jury"][0]["ids"]),
         _appeal_charge("taxableWork", successive["jury"][1]["work"], second,
                        workKind="jury", feeEventIds=successive["jury"][1]["ids"]),
         _appeal_charge("taxableWork", prior_vindication.earned, first,
                        workKind="replacement", origin="vindicated-prior-appeal-funded-work",
                        feeEventIds=[prior_vindication.sequence_id]),
         _appeal_charge("appellantProfit", successive["profit"], second,
                        origin="observed-second-appellant-payout-minus-principal")],
        {"successive": successive, "priorAdmissionVindicationFixture": prior_vindication.model_dump()}, 0, 0,
    ))

    small_events = [FeeEvent(sequence_id=9900 + i, address=ADDRESSES[100 + i],
                             round_index=1, role="VALIDATOR", earned=value)
                    for i, value in enumerate((1, 4, 2, 3), start=1)]
    tiny_a = _admission("tiny-a", "appellantA", 0, 1, "beyondQuota", (3, 0, 0, 1))
    tiny_b = _admission("tiny-b", "appellantB", 0, 3, "beyondQuota", (4, 0, 0, 1))
    cases.append(_case(
        "tiny_overlay_rounding_ignores_interleaved_event_order",
        [_ordinary("ordinary0", "sender", 3, 1)], [tiny_a, tiny_b],
        [_ordinary_charge(1, "ordinary-work", [small_events[0].sequence_id]),
         _appeal_charge("taxableWork", 4, tiny_b, workKind="jury",
                        feeEventIds=[small_events[1].sequence_id]),
         _ordinary_charge(2, "ordinary-work", [small_events[2].sequence_id]),
         _appeal_charge("taxableWork", 3, tiny_a, workKind="jury",
                        feeEventIds=[small_events[3].sequence_id])],
        {"smallEventsFixture": [event.model_dump() for event in small_events]}, 1, 0,
    ))

    same_old = _admission("g0-old", "appellantA", 0, 1, "beyondQuota",
                          (failure["juryWork"], 0, 0, 0), voided=True,
                          bond=failure["bond"])
    same_new = _admission("g0-new", "appellantB", 0, 1, "beyondQuota",
                          (success["juryWork"], success["profit"], 0, 0),
                          successful=True, bond=success["bond"])
    cases.append(_case(
        "same_generation_void_reuse_keeps_distinct_ids",
        [], [same_old, same_new],
        [_appeal_charge("taxableWork", failure["juryWork"], same_old,
                        workKind="jury", feeEventIds=failure["juryEvidence"]),
         _appeal_charge("taxableWork", success["juryWork"], same_new,
                        workKind="jury", feeEventIds=success["juryEvidence"]),
         _appeal_charge("appellantProfit", success["profit"], same_new,
                        feeEventIds=success["appellantEvidence"])],
        {"voided": failure, "reused": success}, 0, 0,
    ))

    rounding = _admission("rounding-a", "appellantA", 0, 1, "beyondQuota",
                          (3900, 0, 0, 688), bond=0)
    cases.append(_case(
        "failed_appeal_overlay_floor_one_wei_shortfall",
        [_ordinary("ordinary0", "sender", 1100, 194)], [rounding],
        [_ordinary_charge(1100, "original-work", []),
         _appeal_charge("taxableWork", 1400, rounding, workKind="jury")],
        {"source": "CON-984 on-chain failed-appeal settlement witness",
         "totalTaxableWork": 2500, "capturedAppealWork": 1400,
         "ordinaryOverlayReserve": 194, "actualOverlayRouted": 441},
        441, 0, overlay_bps=1500,
    ))

    corpus = {"schemaVersion": 2, "model": "N-B02 fee-deposit attribution",
              "unitBoundary": "time-unit work plus explicitly supplied execution costs; no inferred receipt/storage/custody costs",
              "cases": deepcopy(cases)}
    if decimal_strings:
        def stringify_evidence(node):
            if isinstance(node, list):
                return [stringify_evidence(item) for item in node]
            if isinstance(node, dict):
                monetary = {"bond", "juryWork", "juryGrossPayout", "vindication", "normalWork", "profit", "work",
                            "earned", "cost", "staked", "slashed", "burned"}
                return {key: str(value) if key in monetary else stringify_evidence(value)
                        for key, value in node.items()}
            return node

        for case in corpus["cases"]:
            for lot in case["ordinaryFunding"] + case["rescueFunding"]:
                lot["reserve"] = {k: str(v) for k, v in lot["reserve"].items()}
            for admission in case["admissions"]:
                for field in ("bondPrincipal", "prepaidScheduledBase"):
                    admission[field] = str(admission[field])
                admission["reserve"] = {k: str(v) for k, v in admission["reserve"].items()}
            for charge in case["charges"]:
                charge["amount"] = str(charge["amount"])
            case["actualOverlayRouted"] = {k: str(v) for k, v in case["actualOverlayRouted"].items()}
            for row in case["expected"]["byPayer"] + case["expected"]["byFunding"]:
                for field in ("deposited", "consumed", "refunded"):
                    if field in row:
                        row[field] = {k: str(v) for k, v in row[field].items()}
            for field in ("totalDeposited", "totalConsumed", "totalRefunded", "overlayRouted", "taxableWork"):
                case["expected"][field] = str(case["expected"][field])
            case["observedRoundFees"] = stringify_evidence(case["observedRoundFees"])
    return corpus
