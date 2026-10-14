"""F-B01: fee color on a leader replay does not change its next appeal route."""

import pytest

from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.core.transaction_processing import process_transaction


ADDRESSES = [f"0x{i:040x}" for i in range(1, 41)]
PREFIX = [
    "START",
    "LEADER_RECEIPT_UNDETERMINED",
    "LEADER_APPEAL_SUCCESSFUL",
    "LEADER_RECEIPT_MAJORITY_TIMEOUT",
]


def run_path(path):
    transaction, budget = path_to_transaction_results(
        path, ADDRESSES, ADDRESSES[-1], ADDRESSES[-2], 100, 200
    )
    events, labels = process_transaction(ADDRESSES, transaction, budget)
    return transaction, events, labels


def test_failed_replay_origin_jury_pays_aligned_jurors_and_bond():
    transaction, events, labels = run_path(
        PREFIX + ["VALIDATOR_APPEAL_UNSUCCESSFUL", "END"]
    )
    assert labels == [
        "SKIP_ROUND",
        "APPEAL_LEADER_SUCCESSFUL",
        "LEADER_TIMEOUT_50_PERCENT",
        "APPEAL_VALIDATOR_UNSUCCESSFUL",
    ]
    assert len(transaction.rounds[3].rotations[-1].votes) == 13
    assert [
        event.cost
        for event in events
        if event.round_index == 3 and event.role == "APPEALANT" and event.cost
    ] == [2600]
    jury = [
        event
        for event in events
        if event.round_index == 3 and event.role == "VALIDATOR"
    ]
    assert sorted(event.earned for event in jury) == [0] * 6 + [742] * 7
    assert sum(event.earned for event in jury) == 5194
    assert 13 * 200 + 2600 - sum(event.earned for event in jury) == 6
    assert sum(
        event.earned
        for event in events
        if event.round_index == 2 and event.role == "LEADER"
    ) == 50


@pytest.mark.parametrize(
    "remedy, expected_label, expected_leader_fee",
    [
        ("LEADER_RECEIPT_MAJORITY_AGREE", "NORMAL_ROUND", 100),
        ("LEADER_TIMEOUT", "LEADER_TIMEOUT_50_PERCENT", 50),
    ],
)
def test_winning_jury_uses_validator_return_and_actual_remedy_work(
    remedy, expected_label, expected_leader_fee
):
    transaction, events, labels = run_path(
        PREFIX + ["VALIDATOR_APPEAL_SUCCESSFUL", remedy, "END"]
    )
    assert labels[:4] == [
        "SKIP_ROUND",
        "APPEAL_LEADER_SUCCESSFUL",
        "SKIP_ROUND",
        "APPEAL_VALIDATOR_SUCCESSFUL",
    ]
    assert labels[4] == expected_label
    assert len(transaction.rounds[3].rotations[-1].votes) == 13
    assert [
        event.cost
        for event in events
        if event.round_index == 3 and event.role == "APPEALANT" and event.cost
    ] == [2600]
    assert [
        event.earned
        for event in events
        if event.round_index == 3 and event.role == "APPEALANT" and event.earned
    ] == [6500]
    jury_addresses = set(transaction.rounds[3].rotations[-1].votes)
    predecessor_addresses = set(transaction.rounds[2].rotations[-1].votes)
    jury_events = [
        event
        for event in events
        if event.round_index == 3
        and event.role == "VALIDATOR"
        and event.address in jury_addresses
    ]
    vindication_events = [
        event
        for event in events
        if event.round_index == 3
        and event.role == "VALIDATOR"
        and event.address in predecessor_addresses
    ]
    assert sorted(event.earned for event in jury_events) == [0] * 6 + [200] * 7
    assert sorted(event.earned for event in vindication_events) == [200] * 2
    assert sum(event.earned for event in jury_events + vindication_events) == 1800
    assert sum(
        event.earned
        for event in events
        if event.round_index == 4 and event.role == "LEADER"
    ) == expected_leader_fee


def test_actual_leader_timeout_appeal_keeps_its_existing_family():
    _, events, labels = run_path(
        [
            "START",
            "LEADER_TIMEOUT",
            "LEADER_APPEAL_TIMEOUT_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]
    )
    assert labels == [
        "SKIP_ROUND",
        "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
        "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
    ]
    assert [
        event.cost
        for event in events
        if event.round_index == 1 and event.role == "APPEALANT" and event.cost
    ] == [1100]
    assert [
        event.earned
        for event in events
        if event.round_index == 1 and event.role == "APPEALANT" and event.earned
    ] == [2750]
