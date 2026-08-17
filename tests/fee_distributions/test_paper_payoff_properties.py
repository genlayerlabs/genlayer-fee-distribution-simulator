"""Executable assurance for the endogenous-evaluator paper's fee premises."""

from pathlib import Path

import pytest

from src.fee_simulator.analysis.paper_fee_kernel_tla import (
    render_paper_fee_kernel_tla,
)
from src.fee_simulator.analysis.paper_payoff_kernel import (
    PaperPropertyViolation,
    certify_normal_round,
    certify_successful_validator_appeal,
)
from src.fee_simulator.analysis.paper_property_sweep import (
    VoteCounts,
    build_first_rung_case,
    verify_first_rung_paper_properties,
)
from src.fee_simulator.core.round_fee_distribution.appeal_validator_successful import (
    apply_appeal_validator_successful,
)
from src.fee_simulator.core.round_fee_distribution.normal_round import (
    apply_normal_round,
)
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.protocol.models import EventSequence, FeeEvent


def _successful_appeal_events(original_counts, appeal_counts):
    transaction_results, budget, round_labels = build_first_rung_case(
        original_counts, appeal_counts
    )
    addresses = (
        list(transaction_results.rounds[0].rotations[-1].votes)
        + list(transaction_results.rounds[1].rotations[-1].votes)
        + [budget.senderAddress, budget.appeals[0].appealantAddress]
    )
    events, round_labels = process_transaction(addresses, transaction_results, budget)
    return transaction_results, budget, round_labels, events


def test_exhaustive_first_rung_paper_payoff_kernel():
    report = verify_first_rung_paper_properties()

    assert report.normal_profiles_checked == 21
    assert report.successful_appeal_profiles_checked == 156
    assert report.end_to_end_appeal_profiles_checked == 150
    assert report.live_label_ambiguities_detected == 6
    assert report.clear_reversal_profiles_checked == 120
    assert report.no_majority_appeal_profiles_checked == 36
    assert report.maximum_vindicated_count_observed == 2
    assert report.maximum_added_sender_cost_observed == 400
    assert report.configured_rung_boundary_cases_checked == 18
    assert report.largest_configured_vindication_count == 499
    assert report.largest_configured_added_sender_cost == 99800
    assert report.appeal_reward_multiple == 2.5
    assert report.payoff_kernel == {
        "normal_clear_aligned": 200,
        "normal_clear_minority": -200,
        "normal_no_majority": 200,
        "appeal_clear_aligned": 200,
        "appeal_clear_minority": -200,
        "appeal_no_majority": 200,
        "original_vindicated": 200,
        "original_other": 0,
        "original_no_majority": 0,
    }
    assert report.paper_margins == {
        "clear_majority_preservation_spread": 400,
        "no_majority_preservation_spread": 0,
        "clear_reversal_correction_spread": 200,
        "no_majority_correction_spread": 0,
    }


def test_checked_in_tla_fee_kernel_matches_executable_report():
    report = verify_first_rung_paper_properties()
    repository_root = Path(__file__).resolve().parents[2]
    checked_in = repository_root / "formal" / "tla" / "PaperFeeKernel.tla"

    assert checked_in.read_text() == render_paper_fee_kernel_tla(report)


def test_clear_reversal_certificate_matches_paper_example():
    transaction_results, budget, round_labels, events = _successful_appeal_events(
        VoteCounts(agree=3, disagree=2, timeout=0),
        VoteCounts(agree=2, disagree=5, timeout=0),
    )

    certificate = certify_successful_validator_appeal(
        transaction_results, 1, budget, round_labels, events
    )

    assert certificate.original_majority == "AGREE"
    assert certificate.appeal_majority == "DISAGREE"
    assert certificate.vindicated_count == 2
    assert certificate.maximum_vindicated_count == 2
    assert certificate.vindication_payout == 400
    assert certificate.added_sender_cost == 400
    assert certificate.appellant_bond == 1400
    assert certificate.appellant_bond_debit == 1400
    assert certificate.appellant_gross_reward == 3500


def test_no_majority_success_has_zero_correction_payoff():
    transaction_results, budget, round_labels, events = _successful_appeal_events(
        VoteCounts(agree=3, disagree=2, timeout=0),
        VoteCounts(agree=3, disagree=3, timeout=1),
    )

    certificate = certify_successful_validator_appeal(
        transaction_results, 1, budget, round_labels, events
    )

    assert certificate.appeal_majority == "UNDETERMINED"
    assert certificate.vindicated_count == 0
    assert certificate.vindication_payout == 0
    assert certificate.added_sender_cost == 0


def test_negative_control_missing_vindication_is_rejected():
    transaction_results, budget, round_labels, events = _successful_appeal_events(
        VoteCounts(agree=3, disagree=2, timeout=0),
        VoteCounts(agree=2, disagree=5, timeout=0),
    )
    original_dissenter = next(
        address
        for address, vote in transaction_results.rounds[0].rotations[-1].votes.items()
        if vote == "DISAGREE"
    )
    mutated = [
        event
        for event in events
        if not (event.role == "VALIDATOR" and event.address == original_dissenter)
    ]

    with pytest.raises(PaperPropertyViolation, match="original_round_vindication"):
        certify_successful_validator_appeal(
            transaction_results, 1, budget, round_labels, mutated
        )


def test_negative_control_retroactive_punishment_is_rejected():
    transaction_results, budget, round_labels, events = _successful_appeal_events(
        VoteCounts(agree=3, disagree=2, timeout=0),
        VoteCounts(agree=2, disagree=5, timeout=0),
    )
    original_majority_validator = next(
        iter(transaction_results.rounds[0].rotations[-1].votes)
    )
    mutated = events + [
        FeeEvent(
            sequence_id=max(event.sequence_id for event in events) + 1,
            address=original_majority_validator,
            round_index=1,
            round_label="APPEAL_VALIDATOR_SUCCESSFUL",
            role="VALIDATOR",
            vote="AGREE",
            burned=200,
        )
    ]

    with pytest.raises(PaperPropertyViolation, match="original_round_vindication"):
        certify_successful_validator_appeal(
            transaction_results, 1, budget, round_labels, mutated
        )


def test_negative_control_no_majority_vindication_is_rejected():
    transaction_results, budget, round_labels, events = _successful_appeal_events(
        VoteCounts(agree=3, disagree=2, timeout=0),
        VoteCounts(agree=3, disagree=3, timeout=1),
    )
    original_validator = next(iter(transaction_results.rounds[0].rotations[-1].votes))
    mutated = events + [
        FeeEvent(
            sequence_id=max(event.sequence_id for event in events) + 1,
            address=original_validator,
            round_index=1,
            round_label="APPEAL_VALIDATOR_SUCCESSFUL",
            role="VALIDATOR",
            vote="AGREE",
            earned=200,
        )
    ]

    with pytest.raises(PaperPropertyViolation, match="original_round_vindication"):
        certify_successful_validator_appeal(
            transaction_results, 1, budget, round_labels, mutated
        )


def test_negative_control_wrong_appellant_multiple_is_rejected():
    transaction_results, budget, round_labels, events = _successful_appeal_events(
        VoteCounts(agree=3, disagree=2, timeout=0),
        VoteCounts(agree=2, disagree=5, timeout=0),
    )
    mutated = [
        (
            event.model_copy(update={"earned": 2100})
            if event.role == "APPEALANT" and event.earned > 0
            else event
        )
        for event in events
    ]

    with pytest.raises(PaperPropertyViolation, match="appellant_reward"):
        certify_successful_validator_appeal(
            transaction_results, 1, budget, round_labels, mutated
        )


def test_negative_control_missing_appellant_bond_debit_is_rejected():
    transaction_results, budget, round_labels, events = _successful_appeal_events(
        VoteCounts(agree=3, disagree=2, timeout=0),
        VoteCounts(agree=2, disagree=5, timeout=0),
    )
    mutated = [
        event for event in events if not (event.role == "APPEALANT" and event.cost > 0)
    ]

    with pytest.raises(PaperPropertyViolation, match="appellant_reward"):
        certify_successful_validator_appeal(
            transaction_results, 1, budget, round_labels, mutated
        )


def test_negative_control_stale_sender_refund_is_rejected():
    transaction_results, budget, round_labels, events = _successful_appeal_events(
        VoteCounts(agree=3, disagree=2, timeout=0),
        VoteCounts(agree=2, disagree=5, timeout=0),
    )
    mutated = [
        (
            event.model_copy(update={"earned": event.earned + 400})
            if event.role == "SENDER" and event.earned > 0
            else event
        )
        for event in events
    ]

    with pytest.raises(PaperPropertyViolation, match="sender_refund"):
        certify_successful_validator_appeal(
            transaction_results, 1, budget, round_labels, mutated
        )


def test_negative_control_missing_normal_minority_penalty_is_rejected():
    transaction_results, budget, _ = build_first_rung_case(
        VoteCounts(agree=3, disagree=1, timeout=1),
        VoteCounts(agree=4, disagree=3, timeout=0),
    )
    events = apply_normal_round(
        transaction_results=transaction_results,
        round_index=0,
        budget=budget,
        event_sequence=EventSequence(),
        round_labels=["NORMAL_ROUND", "APPEAL_VALIDATOR_SUCCESSFUL"],
    )
    mutated = [
        (
            event.model_copy(update={"burned": 0})
            if event.role == "VALIDATOR" and event.burned
            else event
        )
        for event in events
    ]

    with pytest.raises(PaperPropertyViolation, match="normal_round_validator_payoff"):
        certify_normal_round(transaction_results, 0, budget, mutated)
