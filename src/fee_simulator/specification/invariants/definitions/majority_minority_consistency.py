"""Invariant 4: validator rewards and burns match each round's majority."""

from collections import defaultdict
from typing import List
from src.fee_simulator.protocol.models import (
    FeeEvent,
    TransactionRoundResults,
    TransactionBudget,
)
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.protocol.constants import PENALTY_REWARD_COEFFICIENT
from src.fee_simulator.core.majority import (
    compute_majority,
    normalize_vote,
    who_is_in_vote_majority,
)
from src.fee_simulator.utils_round_sizes import find_previous_normal_round
from .common import InvariantViolation


def check_majority_minority_consistency(
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults,
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],
) -> None:
    """Invariant 4: validator rewards and burns match each round's majority."""
    for round_idx, round_obj in enumerate(transaction_results.rounds):
        # Skip if no rotations
        if not round_obj.rotations:
            continue

        # Get the round label to check special successful-appeal settlement.
        round_label = round_labels[round_idx] if round_idx < len(round_labels) else ""

        # A successful validator appeal settles its own committee normally and,
        # on a clear result, pays one additional validator fee to each voter in
        # the original round whose vote matches the new majority. The votes are
        # not combined to determine the appeal majority.
        if round_label == "APPEAL_VALIDATOR_SUCCESSFUL" and round_idx > 0:
            votes_current = round_obj.rotations[-1].votes
            majority_outcome = compute_majority(votes_current)

            expected_earnings = defaultdict(int)
            expected_burns = defaultdict(int)

            if majority_outcome == "UNDETERMINED":
                for address in votes_current:
                    expected_earnings[address] += transaction_budget.validatorsTimeout
            else:
                majority_addresses, minority_addresses = who_is_in_vote_majority(
                    votes_current, majority_outcome
                )
                for address in majority_addresses:
                    expected_earnings[address] += transaction_budget.validatorsTimeout
                for address in minority_addresses:
                    expected_burns[address] += (
                        PENALTY_REWARD_COEFFICIENT
                        * transaction_budget.validatorsTimeout
                    )

                original_round_index = find_previous_normal_round(
                    round_idx, round_labels
                )
                if original_round_index is not None:
                    original_round = transaction_results.rounds[original_round_index]
                    if original_round.rotations:
                        for address, vote in original_round.rotations[-1].votes.items():
                            if normalize_vote(vote) == majority_outcome:
                                expected_earnings[address] += (
                                    transaction_budget.validatorsTimeout
                                )

            actual_earnings = defaultdict(int)
            actual_burns = defaultdict(int)
            for event in fee_events:
                if event.round_index != round_idx or event.role != "VALIDATOR":
                    continue
                if event.earned:
                    actual_earnings[event.address] += event.earned
                if event.burned:
                    actual_burns[event.address] += event.burned

            if dict(actual_earnings) != dict(expected_earnings):
                raise InvariantViolation(
                    "majority_minority_consistency",
                    f"Round {round_idx}: Expected validator earnings "
                    f"{dict(expected_earnings)}, got {dict(actual_earnings)}",
                )
            if dict(actual_burns) != dict(expected_burns):
                raise InvariantViolation(
                    "majority_minority_consistency",
                    f"Round {round_idx}: Expected validator burns "
                    f"{dict(expected_burns)}, got {dict(actual_burns)}",
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
