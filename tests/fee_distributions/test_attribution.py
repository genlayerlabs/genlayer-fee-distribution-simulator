"""N-B02 fee ownership from observed work, apart from payout calculation."""

from copy import deepcopy

import pytest

from src.fee_simulator.core.attribution import settle_attribution
from src.fee_simulator.core.attribution_vectors import attribution_vectors


def payer(case, name):
    return next(row for row in case["expected"]["byPayer"] if row["payer"] == name)


def test_success_attributes_jury_replacement_profit_and_original_work():
    case = attribution_vectors()["cases"][0]
    assert case["observedRoundFees"]["original"]["normalWork"] == 700
    assert case["observedRoundFees"]["appeal"]["vindication"] == 200
    assert case["observedRoundFees"]["appeal"]["juryWork"] == 800
    assert case["observedRoundFees"]["appeal"]["juryGrossPayout"] == 800
    assert [x["earned"] for x in case["observedRoundFees"]["replacementFixture"]] == [100, 200]
    assert case["observedRoundFees"]["appeal"]["profit"] == 2100
    assert case["expected"]["totalConsumed"] == 700 + 200 + 800 + 300 + 2100 + 40 + 222
    assert payer(case, "appellantA")["consumed"] == {
        "primary": 0, "taxableWork": 1100, "appellantProfit": 2100,
        "executionBacking": 40, "overlay": 100,
    }
    assert payer(case, "sender")["consumed"]["primary"] == 500
    assert payer(case, "topper")["consumed"]["primary"] == 400
    assert payer(case, "sender")["consumed"]["overlay"] == 50
    assert payer(case, "topper")["consumed"]["overlay"] == 72


def test_failure_prepaid_split_void_reuse_and_rescue():
    _, failed, below, above, reused, overrun = attribution_vectors()["cases"][:6]
    assert failed["observedRoundFees"]["juryGrossPayout"] == 2800
    assert failed["observedRoundFees"]["juryWork"] == 1400
    assert payer(failed, "sender")["consumed"]["primary"] == 400
    assert payer(failed, "topper")["consumed"]["primary"] == 300
    assert payer(failed, "appellantB")["consumed"]["taxableWork"] == 1400
    assert payer(failed, "appellantB")["consumed"]["appellantProfit"] == 0
    assert payer(failed, "appellantB")["refunded"]["overlay"] == 200
    assert payer(below, "sender")["consumed"]["primary"] == 1100
    assert payer(below, "appellantA")["consumed"]["taxableWork"] == 0
    assert payer(above, "sender")["consumed"]["primary"] == 1150
    assert payer(above, "appellantA")["consumed"]["taxableWork"] == 150
    assert payer(above, "appellantA")["consumed"]["overlay"] == 16
    assert payer(reused, "appellantA")["consumed"]["taxableWork"] == 1400
    assert payer(reused, "appellantB")["consumed"]["taxableWork"] == 800
    assert payer(reused, "appellantA")["consumed"]["appellantProfit"] == 0
    assert payer(reused, "appellantB")["consumed"]["appellantProfit"] == 2100
    assert payer(overrun, "appellantA")["consumed"]["taxableWork"] == 600
    assert payer(overrun, "sender")["consumed"]["primary"] == 100
    assert payer(overrun, "rescuer")["consumed"]["primary"] == 100


def test_raw_cost_and_per_payer_conservation():
    for case in attribution_vectors()["cases"]:
        result = case["expected"]
        raw_cost = sum(charge["amount"] for charge in case["charges"])
        routed = sum(case["actualOverlayRouted"].values())
        assert result["totalConsumed"] == raw_cost + routed
        assert result["overlayRouted"] == routed
        assert result["totalDeposited"] == result["totalConsumed"] + result["totalRefunded"]
        for row in result["byPayer"]:
            for component, deposited in row["deposited"].items():
                assert deposited == row["consumed"][component] + row["refunded"][component]
        assert result["totalDeposited"] == sum(
            sum(lot["reserve"].values()) for lot in case["admissions"]
            + case["ordinaryFunding"] + case["rescueFunding"]
        )  # Bond principal is deliberately absent.


def test_immutable_id_rejects_reassignment_after_void():
    case = deepcopy(attribution_vectors()["cases"][4])
    case["charges"][0]["sourceFundingId"] = "g1-a0"
    with pytest.raises(ValueError, match="immutable admission"):
        settle_attribution(case)
    case = deepcopy(attribution_vectors()["cases"][4])
    case["admissions"][1]["id"] = "g0-a0"
    with pytest.raises(ValueError, match="duplicate funding ID"):
        settle_attribution(case)


def test_cumulative_prepaid_boundary_and_global_overlay_rounding():
    case = deepcopy(attribution_vectors()["cases"][3])
    admission = case["admissions"][0]
    case["actualOverlayRouted"] = {"developer": 1, "dao": 0}
    case["charges"] = [
        {"kind": "taxableWork", "amount": amount, "sourceFundingId": admission["id"],
         "generation": 0, "bookRound": 1, "workKind": "replacement"}
        for amount in (100, 51, 9)
    ]
    output = settle_attribution(case)
    appellant = next(row for row in output["byPayer"] if row["payer"] == "appellantA")
    sender = next(row for row in output["byPayer"] if row["payer"] == "sender")
    assert appellant["consumed"]["taxableWork"] == 10
    assert appellant["consumed"]["overlay"] == 0
    assert sender["consumed"]["primary"] == 150
    assert sender["consumed"]["overlay"] == 1


def test_global_route_is_authoritative_and_gross_up_bounded():
    case = deepcopy(attribution_vectors()["cases"][0])
    case["actualOverlayRouted"] = {"developer": 112, "dao": 111}
    with pytest.raises(ValueError, match="gross-up"):
        settle_attribution(case)
    case = deepcopy(attribution_vectors()["cases"][0])
    case["actualOverlayRouted"] = {"developer": 0, "dao": 0}
    output = settle_attribution(case)
    assert output["overlayRouted"] == 0
    assert output["totalConsumed"] == sum(x["amount"] for x in case["charges"])


def test_typed_component_cap_spills_only_to_ordinary_primary():
    case = deepcopy(attribution_vectors()["cases"][5])
    case["admissions"][0]["reserve"]["taxableWork"] = 0
    with pytest.raises(ValueError, match="overall primary funding exhausted"):
        settle_attribution(case)
    # An untouched profit reserve cannot pay jury work.
    assert case["admissions"][0]["reserve"]["appellantProfit"] == 2100


def test_overlay_aggregates_by_immutable_admission_before_rounding():
    case = attribution_vectors()["cases"][7]
    assert [charge["sourceFundingId"] for charge in case["charges"]] == [
        "ordinary", "tiny-b", "ordinary", "tiny-a"
    ]
    assert payer(case, "appellantA")["consumed"]["overlay"] == 0
    assert payer(case, "appellantB")["consumed"]["overlay"] == 0
    assert payer(case, "sender")["consumed"]["overlay"] == 1


def test_vindication_uses_original_appeal_owner_and_same_slot_reuse_keeps_ids():
    successive = attribution_vectors()["cases"][6]
    vindication = next(charge for charge in successive["charges"]
                       if charge.get("origin") == "vindicated-prior-appeal-funded-work")
    assert vindication["sourceFundingId"] == "g0-a0"
    assert vindication["amount"] == 200
    assert payer(successive, "appellantA")["consumed"]["taxableWork"] == 1600
    assert payer(successive, "appellantB")["consumed"]["taxableWork"] == 1200
    reused = attribution_vectors()["cases"][8]
    assert [(admission["generation"], admission["bookRound"])
            for admission in reused["admissions"]] == [(0, 1), (0, 1)]
    assert [admission["id"] for admission in reused["admissions"]] == ["g0-old", "g0-new"]
    assert payer(reused, "appellantA")["consumed"]["taxableWork"] == 1400
    assert payer(reused, "appellantB")["consumed"]["taxableWork"] == 800


def test_decimal_string_corpus_replays_without_mutation():
    case = attribution_vectors(decimal_strings=True)["cases"][0]
    original = deepcopy(case)
    result = settle_attribution(case)
    assert result["totalConsumed"] == int(case["expected"]["totalConsumed"])
    assert case == original
