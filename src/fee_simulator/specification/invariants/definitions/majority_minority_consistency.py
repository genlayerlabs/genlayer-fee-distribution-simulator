"""Invariant 4: Minority burns = penalty coefficient * count * timeout"""

from typing import List
from src.fee_simulator.protocol.models import (
    FeeEvent,
    TransactionRoundResults,
    TransactionBudget,
)
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.protocol.constants import PENALTY_REWARD_COEFFICIENT
from src.fee_simulator.core.majority import compute_majority
from .common import InvariantViolation


def check_majority_minority_consistency(
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults,
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],
) -> None:
    """Invariant 4: Minority burns = penalty coefficient * count * timeout"""
    for round_idx, round_obj in enumerate(transaction_results.rounds):
        # Skip if no rotations
        if not round_obj.rotations:
            continue

        # Get the round label to check if it's an appeal that combines votes
        round_label = round_labels[round_idx] if round_idx < len(round_labels) else ""

        # For APPEAL_VALIDATOR_SUCCESSFUL, votes are combined from previous and current rounds
        if round_label == "APPEAL_VALIDATOR_SUCCESSFUL" and round_idx > 0:
            # Combine votes from previous and current rounds
            votes_current = round_obj.rotations[-1].votes
            votes_previous = (
                transaction_results.rounds[round_idx - 1].rotations[-1].votes
                if transaction_results.rounds[round_idx - 1].rotations
                else {}
            )
            combined_votes = {**votes_current, **votes_previous}

            majority_outcome = compute_majority(combined_votes)

            if majority_outcome not in ["UNDETERMINED", None]:
                # Count minority validators in combined votes
                minority_count = 0
                expected_burn_per_validator = (
                    PENALTY_REWARD_COEFFICIENT * transaction_budget.validatorsTimeout
                )

                for address, vote in combined_votes.items():
                    # Extract actual vote from complex vote structures
                    actual_vote = vote
                    if isinstance(vote, list):
                        actual_vote = vote[1] if len(vote) > 1 else vote[0]

                    # Check if this is a minority vote
                    if actual_vote not in ["LEADER_RECEIPT", "LEADER_TIMEOUT", "NA"]:
                        if actual_vote != majority_outcome:
                            minority_count += 1

                # Calculate actual burns for this round
                round_burns = sum(
                    e.burned
                    for e in fee_events
                    if e.round_index == round_idx and e.burned and e.role == "VALIDATOR"
                )

                expected_total_burn = minority_count * expected_burn_per_validator

                if round_burns > 0 and abs(round_burns - expected_total_burn) > 1:
                    raise InvariantViolation(
                        "majority_minority_consistency",
                        f"Round {round_idx}: Expected burn ({expected_total_burn}) != "
                        f"actual burn ({round_burns}) for {minority_count} minority validators",
                    )
        else:
            # Standard case - use only current round votes
            for rotation in round_obj.rotations:
                majority_outcome = compute_majority(rotation.votes)

                if majority_outcome not in ["UNDETERMINED", None]:
                    # Count minority validators
                    minority_count = 0
                    expected_burn_per_validator = (
                        PENALTY_REWARD_COEFFICIENT
                        * transaction_budget.validatorsTimeout
                    )

                    for address, vote in rotation.votes.items():
                        # Extract actual vote from complex vote structures
                        actual_vote = vote
                        if isinstance(vote, list):
                            actual_vote = vote[1] if len(vote) > 1 else vote[0]

                        # Check if this is a minority vote
                        if actual_vote not in [
                            "LEADER_RECEIPT",
                            "LEADER_TIMEOUT",
                            "NA",
                        ]:
                            if actual_vote != majority_outcome:
                                minority_count += 1

                    # Calculate actual burns for this round
                    round_burns = sum(
                        e.burned
                        for e in fee_events
                        if e.round_index == round_idx
                        and e.burned
                        and e.role == "VALIDATOR"
                    )

                    expected_total_burn = minority_count * expected_burn_per_validator

                    if round_burns > 0 and abs(round_burns - expected_total_burn) > 1:
                        raise InvariantViolation(
                            "majority_minority_consistency",
                            f"Round {round_idx}: Expected burn ({expected_total_burn}) != "
                            f"actual burn ({round_burns}) for {minority_count} minority validators",
                        )
