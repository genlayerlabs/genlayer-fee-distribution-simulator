"""Invariant 19: Finite resource consumption prevents infinite loops"""

from typing import List
from src.fee_simulator.protocol.models import FeeEvent, TransactionRoundResults
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.utils import is_appeal_round
from .common import InvariantViolation


def check_progress_monotonicity(
    transaction_results: TransactionRoundResults,
    fee_events: List[FeeEvent],
    round_labels: List[RoundLabel],
) -> None:
    """
    Invariant 19: Finite resource consumption prevents infinite loops.
    Each round should consume new addresses, and total consumption should be bounded.
    Rounds immediately following an appeal are exempt from the new address requirement.
    """
    consumed_addresses = set()

    for i, round_obj in enumerate(transaction_results.rounds):
        round_addresses = set()

        # Get addresses from votes
        if round_obj.rotations:
            for rotation in round_obj.rotations:
                round_addresses.update(rotation.votes.keys())

        # Get addresses from fee events for this round
        for event in fee_events:
            if event.round_index == i:
                round_addresses.add(event.address)

        # Check that non-empty rounds consume new addresses
        if round_addresses and not (round_addresses - consumed_addresses):
            # This round didn't introduce any new addresses.
            # This is OK for appeal rounds or rounds immediately following an appeal.
            is_current_round_appeal = is_appeal_round(round_labels[i])
            is_previous_round_appeal = i > 0 and is_appeal_round(round_labels[i - 1])

            if not is_current_round_appeal and not is_previous_round_appeal:
                raise InvariantViolation(
                    "progress_monotonicity",
                    f"Round {i} ({round_labels[i]}) did not consume any new addresses, potential infinite loop",
                )

        consumed_addresses.update(round_addresses)

    # Check total consumption is bounded
    MAX_ADDRESSES = 1100  # Increased limit for stress tests
    if len(consumed_addresses) > MAX_ADDRESSES:
        raise InvariantViolation(
            "progress_monotonicity",
            f"Total address consumption ({len(consumed_addresses)}) exceeds maximum pool size ({MAX_ADDRESSES})",
        )

    # Check that the transaction eventually terminates
    MAX_ROUNDS = 100  # Reasonable upper bound
    if len(transaction_results.rounds) > MAX_ROUNDS:
        raise InvariantViolation(
            "progress_monotonicity",
            f"Transaction has {len(transaction_results.rounds)} rounds, exceeding reasonable limit of {MAX_ROUNDS}",
        )
