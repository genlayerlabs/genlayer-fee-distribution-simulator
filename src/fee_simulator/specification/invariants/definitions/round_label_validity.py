"""Invariant 10: All round labels must be from the predefined set"""

from typing import List
from src.fee_simulator.protocol.types import RoundLabel
from .common import InvariantViolation


def check_round_label_validity(round_labels: List[RoundLabel]) -> None:
    """
    Invariant 10: All round labels must be from the predefined set.
    """
    # Import the valid round labels from the types module
    VALID_LABELS = {
        "NORMAL_ROUND",
        "EMPTY_ROUND",
        "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
        "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
        "APPEAL_LEADER_SUCCESSFUL",
        "APPEAL_LEADER_UNSUCCESSFUL",
        "APPEAL_VALIDATOR_SUCCESSFUL",
        "APPEAL_VALIDATOR_UNSUCCESSFUL",
        "LEADER_TIMEOUT",
        "VALIDATORS_PENALTY_ONLY_ROUND",
        "SKIP_ROUND",
        "LEADER_TIMEOUT_50_PERCENT",
        "SPLIT_PREVIOUS_APPEAL_BOND",
        "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
        "EQUAL_SPLIT",
    }

    for i, label in enumerate(round_labels):
        if label not in VALID_LABELS:
            raise InvariantViolation(
                "round_label_validity",
                f"Round {i} has invalid label '{label}'. Must be one of: {sorted(VALID_LABELS)}",
            )
