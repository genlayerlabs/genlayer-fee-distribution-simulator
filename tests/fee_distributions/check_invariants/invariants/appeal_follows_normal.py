"""Invariant 7: Appeal rounds must follow normal rounds (not other appeals)"""

from typing import List
from fee_simulator.types import RoundLabel
from fee_simulator.utils import is_appeal_round
from .common import InvariantViolation


def check_appeal_follows_normal(round_labels: List[RoundLabel]) -> None:
    """
    Invariant 7: Appeal rounds must follow normal rounds (not other appeals).
    With the new refactor, appeals can be at any index, but they must follow
    a normal round in the transaction path.
    """
    for i, label in enumerate(round_labels):
        if is_appeal_round(label) and i > 0:
            # Check that the previous round is not an appeal
            # (except for special cases like chained unsuccessful appeals)
            prev_label = round_labels[i - 1]

            # Allow chained appeals only if they are unsuccessful appeals
            if is_appeal_round(prev_label):
                # Check if this is a valid chain
                valid_chain = (
                    # Unsuccessful appeals can chain
                    ("UNSUCCESSFUL" in prev_label and "UNSUCCESSFUL" in label)
                    or
                    # Split previous appeal bond can follow unsuccessful appeals
                    (
                        "UNSUCCESSFUL" in prev_label
                        and label == "SPLIT_PREVIOUS_APPEAL_BOND"
                    )
                    or
                    # Successful appeals can follow unsuccessful appeals (outcome change)
                    ("UNSUCCESSFUL" in prev_label and "SUCCESSFUL" in label)
                )

                if not valid_chain:
                    raise InvariantViolation(
                        "appeal_follows_normal",
                        f"Appeal round '{label}' at index {i} follows another appeal '{prev_label}' "
                        f"(this is not a valid appeal chain)",
                    )
