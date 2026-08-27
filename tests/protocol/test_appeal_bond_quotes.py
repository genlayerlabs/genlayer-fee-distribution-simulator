from src.fee_simulator.core.bond_computing import (
    compute_appeal_bond,
    compute_appeal_bond_quote,
)


def test_validator_appeal_quote_exposes_the_appeal_committee_basis():
    labels = ["NORMAL_ROUND", "APPEAL_VALIDATOR_SUCCESSFUL"]

    quote = compute_appeal_bond_quote(0, 100, 200, labels)

    assert quote.committee_basis == "configured_appeal_round"
    assert quote.committee_size == 7
    assert quote.attempt_basis == "single_appeal_jury"
    assert quote.rotations_value == 0
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
    assert quote.attempt_basis == "configured_next_normal_round"
    assert quote.rotations_value == 2
    assert quote.attempts == 3
    assert quote.leader_component == 300
    assert quote.validator_component == 6_600
    assert quote.total == 6_900


def test_later_undetermined_quote_uses_normal_round_ordinal():
    labels = [
        "NORMAL_ROUND",
        "APPEAL_LEADER_UNSUCCESSFUL",
        "NORMAL_ROUND",
        "APPEAL_LEADER_SUCCESSFUL",
    ]

    quote = compute_appeal_bond_quote(
        2,
        100,
        200,
        labels,
        appeal_round_index=3,
        rotations=[0, 1, 2],
        rotations_used=[0, 0, 0],
    )

    # Raw round 4 is normal-round ordinal 2, so rotations[2] prices three
    # attempts at the configured 23-seat committee.
    assert quote.source_round_index == 2
    assert quote.committee_size == 23
    assert quote.rotations_value == 2
    assert quote.attempts == 3
    assert quote.total == 3 * (100 + 23 * 200)


def test_leader_timeout_quote_keeps_the_configured_source_round_basis():
    labels = ["NORMAL_ROUND", "APPEAL_LEADER_TIMEOUT_SUCCESSFUL"]

    quote = compute_appeal_bond_quote(0, 100, 200, labels, rotations=[0, 0])

    assert quote.committee_basis == "configured_source_round"
    assert quote.committee_size == 5
    assert quote.attempt_basis == "configured_next_normal_round"
    assert quote.rotations_value == 0
    assert quote.attempts == 1
    assert quote.leader_component == 100
    assert quote.validator_component == 1_000
    assert quote.total == 1_100


def test_leader_timeout_quote_uses_next_funded_round_independently_of_prior_usage():
    labels = ["NORMAL_ROUND", "APPEAL_LEADER_TIMEOUT_SUCCESSFUL"]

    quote = compute_appeal_bond_quote(
        0,
        100,
        200,
        labels,
        rotations=[2, 2],
        rotations_used=[1, 0],
    )

    assert quote.rotations_value == 2
    assert quote.attempts == 3
    assert quote.total == 3_300


def test_chained_timeout_quote_uses_each_next_normal_round_schedule_entry():
    labels = [
        "NORMAL_ROUND",
        "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
        "NORMAL_ROUND",
        "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
    ]

    quote = compute_appeal_bond_quote(
        2,
        100,
        200,
        labels,
        appeal_round_index=3,
        rotations=[3, 2, 1],
        rotations_used=[1, 1],
    )

    assert quote.committee_size == 11
    assert quote.rotations_value == 1
    assert quote.attempts == 2
    assert quote.total == 4_600
