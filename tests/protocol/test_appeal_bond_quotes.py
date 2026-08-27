from src.fee_simulator.core.bond_computing import (
    compute_appeal_bond,
    compute_appeal_bond_quote,
)


def test_validator_appeal_quote_exposes_the_appeal_committee_basis():
    labels = ["NORMAL_ROUND", "APPEAL_VALIDATOR_SUCCESSFUL"]

    quote = compute_appeal_bond_quote(0, 100, 200, labels)

    assert quote.committee_basis == "configured_appeal_round"
    assert quote.committee_size == 7
    assert quote.attempts == 1
    assert quote.leader_component == 0
    assert quote.validator_component == 1_400
    assert quote.total == 1_400
    assert compute_appeal_bond(0, 100, 200, labels) == quote.total


def test_undetermined_appeal_quote_exposes_next_round_and_rotation_components():
    labels = ["NORMAL_ROUND", "APPEAL_LEADER_SUCCESSFUL"]

    quote = compute_appeal_bond_quote(
        0,
        100,
        200,
        labels,
        rotations=[0, 2],
    )

    assert quote.committee_basis == "configured_next_normal_round"
    assert quote.committee_size == 11
    assert quote.attempts == 3
    assert quote.leader_component == 300
    assert quote.validator_component == 6_600
    assert quote.total == 6_900


def test_leader_timeout_quote_keeps_the_configured_source_round_basis():
    labels = ["NORMAL_ROUND", "APPEAL_LEADER_TIMEOUT_SUCCESSFUL"]

    quote = compute_appeal_bond_quote(0, 100, 200, labels, rotations=[0, 0])

    assert quote.committee_basis == "configured_source_round"
    assert quote.committee_size == 5
    assert quote.attempts == 1
    assert quote.leader_component == 100
    assert quote.validator_component == 1_000
    assert quote.total == 1_100
