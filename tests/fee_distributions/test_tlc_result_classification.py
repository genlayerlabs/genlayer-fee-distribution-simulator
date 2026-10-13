"""Expected-red evidence must be a real counterexample of the selected property."""
import runpy
from pathlib import Path

import pytest

runner = runpy.run_path(str(
    Path(__file__).resolve().parents[2] / "scripts/11_check_paper_attraction_tla.py"
))
classify = runner["outcome_matches"]
SUMMARY = "\n205 states generated, 78 distinct states found"


@pytest.mark.parametrize("message", [
    "Temporal properties were violated.",
    "Temporal property EventuallyStableFullCompetence was violated.",
])
def test_temporal_wording_versions(message):
    assert classify(
        13, message + "\nState 12: Stuttering" + SUMMARY,
        "temporal", "EventuallyStableFullCompetence",
    )


@pytest.mark.parametrize("code,message", [
    (1, "Temporal properties were violated.\nStuttering"),
    (0, "Temporal properties were violated.\nStuttering"),
    (13, "Temporal property AnotherProperty was violated.\nStuttering"),
    (13, "Temporal properties were violated."),
    (13, "Semantic errors"),
    (13, "Temporal properties were violated.\nInvariant GoodBasin is violated.\nStuttering"),
])
def test_wrong_temporal_failures_are_rejected(code, message):
    assert not classify(code, message + SUMMARY, "temporal", "EventuallyStableFullCompetence")


def test_missing_or_empty_exploration_is_rejected():
    text = "Temporal properties were violated.\nStuttering"
    assert not classify(13, text, "temporal", "EventuallyStableFullCompetence")
    assert not classify(
        13, text + "\n0 distinct states found", "temporal", "EventuallyStableFullCompetence",
    )


def test_safety_requires_expected_invariant_and_exit():
    assert classify(12, "Invariant GoodBasin is violated." + SUMMARY, "invariant", "GoodBasin")
    assert not classify(12, "Invariant TypeOK is violated." + SUMMARY, "invariant", "GoodBasin")
    assert not classify(1, "Invariant GoodBasin is violated." + SUMMARY, "invariant", "GoodBasin")


def test_positive_requires_completion():
    assert classify(0, "Model checking completed. No error has been found." + SUMMARY, "pass", None)
    assert not classify(0, "Starting..." + SUMMARY, "pass", None)
