from copy import deepcopy

import pytest

from src.fee_simulator.analysis.consensus_vector_conformance import (
    ConsensusConformanceViolation,
    compare_case,
    upgrade_case_to_current_appeal_economics,
)


def vector_case(appellant_reward=2100, vindicate=False):
    rewards = [
        {
            "address": "appealant",
            "amount": str(appellant_reward),
            "round_index": 1,
            "role": "APPEALANT",
        },
        {
            "address": "validator6",
            "amount": "200",
            "round_index": 1,
            "role": "VALIDATOR",
        },
        {
            "address": "validator7",
            "amount": "200",
            "round_index": 1,
            "role": "VALIDATOR",
        },
        {
            "address": "validator8",
            "amount": "200",
            "round_index": 1,
            "role": "VALIDATOR",
        },
        {
            "address": "validator9",
            "amount": "200",
            "round_index": 1,
            "role": "VALIDATOR",
        },
    ]
    if vindicate:
        rewards.append(
            {
                "address": "validator4",
                "amount": "200",
                "round_index": 1,
                "role": "VALIDATOR",
            }
        )

    return {
        "initialState": {
            "rounds": [
                {
                    "round_index": 0,
                    "type": "SKIP",
                    "validators": [
                        {
                            "address": "validator1",
                            "vote": "LEADER_RECEIPT",
                            "is_leader": True,
                        },
                        {"address": "validator2", "vote": "AGREE"},
                        {"address": "validator3", "vote": "AGREE"},
                        {"address": "validator4", "vote": "DISAGREE"},
                        {"address": "validator5", "vote": "TIMEOUT"},
                    ],
                },
                {
                    "round_index": 1,
                    "type": "VALIDATOR_APPEAL_SUCCESSFUL",
                    "validators": [
                        {"address": "validator6", "vote": "DISAGREE"},
                        {"address": "validator7", "vote": "DISAGREE"},
                        {"address": "validator8", "vote": "DISAGREE"},
                        {"address": "validator9", "vote": "DISAGREE"},
                        {"address": "validator10", "vote": "AGREE"},
                        {"address": "validator11", "vote": "AGREE"},
                        {"address": "validator12", "vote": "AGREE"},
                    ],
                },
            ]
        },
        "expectedState": {
            "rewards": rewards,
            "penalties": [
                {
                    "address": "validator10",
                    "amount": "200",
                    "round_index": 1,
                    "role": "VALIDATOR",
                },
                {
                    "address": "validator11",
                    "amount": "200",
                    "round_index": 1,
                    "role": "VALIDATOR",
                },
                {
                    "address": "validator12",
                    "amount": "200",
                    "round_index": 1,
                    "role": "VALIDATOR",
                },
            ],
            "sender_outcome": {
                "address": "sender",
                "net_change": "1000" if not vindicate else "1700",
            },
        },
    }


def test_classifies_only_2_5x_and_vindication_as_expected_red():
    legacy = vector_case()
    future = vector_case(appellant_reward=3500, vindicate=True)

    delta = compare_case(legacy, future, source="fixture", pattern="canonical")

    assert delta.expected_red
    assert delta.appellant_payout_delta == 1400
    assert delta.vindicated_count == 1
    assert delta.vindication_payout == 200
    assert delta.upfront_reserve_delta == 2300
    assert delta.sender_refund_delta == 700


def test_future_economics_reaches_exact_parity_after_consensus_catches_up():
    future = vector_case(appellant_reward=3500, vindicate=True)

    delta = compare_case(
        future, deepcopy(future), source="fixture", pattern="future-parity"
    )

    assert not delta.expected_red
    assert delta.appellant_payout_delta == 0
    assert delta.vindicated_count == 0
    assert delta.upfront_reserve_delta == 0
    assert delta.sender_refund_delta == 0


def test_upgrades_legacy_case_without_regenerating_its_scenario():
    legacy = vector_case()
    future = upgrade_case_to_current_appeal_economics(
        legacy,
        source="fixture",
        pattern="stable-upgrade",
    )

    assert future["initialState"] == legacy["initialState"]
    assert future == vector_case(appellant_reward=3500, vindicate=True)
    assert legacy == vector_case()


def test_rejects_a_new_retroactive_penalty():
    legacy = vector_case()
    future = vector_case(appellant_reward=3500, vindicate=True)
    future["expectedState"]["penalties"].append(
        {
            "address": "validator2",
            "amount": "200",
            "round_index": 1,
            "role": "VALIDATOR",
        }
    )

    with pytest.raises(ConsensusConformanceViolation, match="penalty schedule changed"):
        compare_case(legacy, future, source="fixture", pattern="bad-punishment")


def test_rejects_vindicating_a_validator_not_aligned_with_the_new_majority():
    legacy = vector_case()
    future = vector_case(appellant_reward=3500, vindicate=True)
    bad_reward = future["expectedState"]["rewards"][-1]
    bad_reward["address"] = "validator2"

    with pytest.raises(ConsensusConformanceViolation, match="wrong original voters"):
        compare_case(legacy, future, source="fixture", pattern="bad-vindication")


def test_rejects_an_unrelated_reward_change():
    legacy = vector_case()
    future = vector_case(appellant_reward=3500, vindicate=True)
    future["expectedState"]["rewards"].append(
        {
            "address": "validator6",
            "amount": "100",
            "round_index": 1,
            "role": "LEADER",
        }
    )

    with pytest.raises(
        ConsensusConformanceViolation, match="unclassified reward delta"
    ):
        compare_case(legacy, future, source="fixture", pattern="bad-reward")


def test_rejects_a_changed_appeal_bond():
    legacy = vector_case()
    future = vector_case(appellant_reward=3750, vindicate=True)

    with pytest.raises(ConsensusConformanceViolation, match="appeal bond changed"):
        compare_case(legacy, future, source="fixture", pattern="bad-bond")


def test_rejects_an_unexplained_sender_refund_change():
    legacy = vector_case()
    future = vector_case(appellant_reward=3500, vindicate=True)
    future["expectedState"]["sender_outcome"]["net_change"] = "1701"

    with pytest.raises(ConsensusConformanceViolation, match="upfront reserve delta"):
        compare_case(legacy, future, source="fixture", pattern="bad-refund")


def test_rejects_a_vote_rule_change():
    legacy = vector_case()
    future = deepcopy(vector_case(appellant_reward=3500, vindicate=True))
    future["initialState"]["rounds"][1]["validators"][0]["vote"] = "AGREE"

    with pytest.raises(ConsensusConformanceViolation, match="vote outcomes changed"):
        compare_case(legacy, future, source="fixture", pattern="bad-rule")
