"""Invariant 10: Votes in fee events must match transaction rounds"""

from typing import List
from fee_simulator.models import FeeEvent, TransactionRoundResults
from .common import InvariantViolation


def check_vote_consistency(
    fee_events: List[FeeEvent], transaction_results: TransactionRoundResults
) -> None:
    """Invariant 10: Votes in fee events must match transaction rounds"""
    for event in fee_events:
        if event.vote and event.round_index is not None:
            # Skip appealants - they have vote="NA" and don't participate in voting
            if event.role == "APPEALANT":
                continue

            if event.round_index < len(transaction_results.rounds):
                round_obj = transaction_results.rounds[event.round_index]
                # Assume rotation_index is 0 if not specified
                rotation_index = 0
                if rotation_index < len(round_obj.rotations):
                    rotation = round_obj.rotations[rotation_index]
                    if event.address in rotation.votes:
                        actual_vote = rotation.votes[event.address]
                        # Handle complex vote structures
                        if isinstance(actual_vote, list):
                            if event.vote not in actual_vote:
                                raise InvariantViolation(
                                    "vote_consistency",
                                    f"Vote mismatch for {event.address} in round {event.round_index}: "
                                    f"event has '{event.vote}', transaction has '{actual_vote}'",
                                )
                        elif event.vote != actual_vote:
                            raise InvariantViolation(
                                "vote_consistency",
                                f"Vote mismatch for {event.address} in round {event.round_index}: "
                                f"event has '{event.vote}', transaction has '{actual_vote}'",
                            )
