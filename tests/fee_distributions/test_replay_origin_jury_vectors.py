"""F-B01 parity sidecar retains exact jury and no-reveal accounting."""

from src.fee_simulator.core.replay_origin_jury_vectors import replay_origin_jury_vectors


def test_generated_jury_vectors_have_exact_route_and_seat_credits():
    corpus = replay_origin_jury_vectors()
    failed, normal, timeout, idle, true_timeout = corpus["cases"]
    assert corpus["validatorFixtureCount"] == 40
    assert [case["caseId"] for case in corpus["cases"]] == [
        "replay-origin-jury-failed",
        "replay-origin-jury-success-normal-remedy",
        "replay-origin-jury-success-timeout-remedy",
        "replay-origin-jury-all-idle-refund",
        "actual-leader-timeout-control",
    ]
    assert all(
        case["provenance"] == "round-engine-generated"
        for case in (failed, normal, timeout, true_timeout)
    )
    assert failed["sourceFeeColorAtAdmission"] == "LEADER_TIMEOUT_50_PERCENT"
    assert failed["sourceDecision"] == "ValidatorsTimeout"
    assert failed["route"] == "validator-jury"
    assert [item["sourceNode"] for item in failed["roundInputs"]] == failed[
        "sourcePath"
    ][1:-1]
    assert failed["roundInputs"][2]["leaderAction"] == "LEADER_RECEIPT"
    assert failed["roundInputs"][2]["leaderAddress"] == (
        "0x0000000000000000000000000000000000000002"
    )
    assert failed["roundInputs"][2]["majorityVote"] == "TIMEOUT"
    assert failed["roundInputs"][2]["seats"][0]["rawVote"] == [
        "LEADER_RECEIPT",
        "AGREE",
    ]
    assert failed["roundInputs"][2]["seats"][1]["rawVote"] == "TIMEOUT"
    assert failed["roundInputs"][1]["bookkeepingOnly"] is True
    assert failed["roundInputs"][3]["bookkeepingOnly"] is False
    assert failed["roundInputs"][3]["admittedRoute"] == "validator-jury"
    assert len(failed["roundInputs"][3]["seats"]) == 13
    assert failed["admittedAppeal"]["bond"] == "2600"
    assert [seat["earned"] for seat in failed["jurorAwards"]] == ["742"] * 7 + ["0"] * 6
    assert failed["divisionDust"] == "6"
    assert failed["appellant"]["totalPayout"] == "0"
    assert (
        failed["payers"]["earlierAppellant"]
        != failed["payers"]["admissionAppellant"]
    )

    for case, remedy in (
        (normal, "NORMAL_ROUND"),
        (timeout, "LEADER_TIMEOUT_50_PERCENT"),
    ):
        assert case["roundLabels"][2:4] == ["SKIP_ROUND", "APPEAL_VALIDATOR_SUCCESSFUL"]
        assert case["remedyLabel"] == remedy
        assert case["admittedAppeal"]["bond"] == "2600"
        assert [seat["earned"] for seat in case["jurorAwards"]] == [
            "200"
        ] * 7 + ["0"] * 6
        assert sorted(award["earned"] for award in case["vindicationAwards"]) == [
            "200",
            "200",
        ]
        assert case["appellant"] == {
            "principalDeposited": "2600",
            "principalReturned": "2600",
            "profit": "3900",
            "principalRefund": "0",
            "totalPayout": "6500",
        }
        assert case["divisionDust"] == "0"

    assert true_timeout["sourceDecision"] == "LeaderTimeout"
    assert true_timeout["route"] == "leader-timeout-appeal"
    assert true_timeout["admittedAppeal"]["bond"] == "1100"
    assert true_timeout["remedyLabel"] == "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND"


def test_all_idle_is_explicit_admission_refund_fixture():
    idle = replay_origin_jury_vectors()["cases"][3]
    assert idle["provenance"] == "manual-admission-refund-fixture"
    assert idle["sourcePath"][-2] == "VALIDATOR_APPEAL_ALL_IDLE_NO_REVEAL"
    assert idle["admittedAppeal"] == {
        "roundIndex": 3,
        "kind": "validator-jury",
        "bond": "2600",
    }
    assert all(
        seat["vote"] == "IDLE" and seat["earned"] == "0"
        for seat in idle["jurorAwards"]
    )
    assert idle["roundInputs"][:3] == replay_origin_jury_vectors()["cases"][0][
        "roundInputs"
    ][:3]
    assert idle["roundInputs"][3]["sourceClassification"] == (
        "VALIDATOR_APPEAL_ALL_IDLE_NO_REVEAL"
    )
    assert idle["roundInputs"][3]["majorityVote"] == "UNDETERMINED"
    assert all(
        seat["rawVote"] == "IDLE" and seat["normalizedVote"] == "IDLE"
        for seat in idle["roundInputs"][3]["seats"]
    )
    assert idle["appellant"]["principalRefund"] == "2600"
    assert idle["appellant"]["profit"] == "0"
    assert idle["senderRefund"] is None
    assert "generic IDLE prepass cannot settle" in idle["scope"]


def test_vector_builder_is_deterministic():
    assert replay_origin_jury_vectors() == replay_origin_jury_vectors()


def test_true_timeout_control_preserves_leader_action_and_route():
    control = replay_origin_jury_vectors()["cases"][-1]
    assert control["roundInputs"][0]["leaderAction"] == "LEADER_TIMEOUT"
    assert control["roundInputs"][0]["leaderAddress"] == (
        "0x0000000000000000000000000000000000000001"
    )
    assert control["roundInputs"][1]["admittedRoute"] == "leader-timeout-appeal"
    assert control["roundInputs"][1]["sourceClassification"] == (
        "LEADER_APPEAL_TIMEOUT_SUCCESSFUL"
    )
