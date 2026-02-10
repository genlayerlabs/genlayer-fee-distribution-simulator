from typing import List, Literal, Optional
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    FeeEvent,
    Round,
    Rotation,
    EventSequence,
)

from src.fee_simulator.core.majority import (
    normalize_vote,
)

from src.fee_simulator.metrics.address_metrics import compute_current_stake
from src.fee_simulator.protocol.constants import IDLE_PENALTY_COEFFICIENT

IdleResolutionMode = Literal["replace", "partial"]


def resolve_partial_votes(votes: dict) -> dict:
    """
    Resolve a round with partial votes by treating IDLE validators as DISAGREE.

    In partial vote resolution (SLASH_PARTIAL), non-revealing validators are
    NOT replaced with reserves. Instead their votes count as DISAGREE for
    majority calculation purposes. The original IDLE votes are preserved in
    the returned dict so slashing can still identify them.

    Args:
        votes: Original vote dictionary

    Returns:
        New vote dictionary with IDLE votes converted to DISAGREE
    """
    new_votes = {}
    for addr, vote in votes.items():
        if normalize_vote(vote) == "IDLE":
            new_votes[addr] = "DISAGREE"
        else:
            new_votes[addr] = vote
    return new_votes


def replace_idle_participants(
    event_sequence: EventSequence,
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults,
    idle_resolution_mode: IdleResolutionMode = "replace",
) -> tuple[TransactionRoundResults, List[FeeEvent]]:
    """
    Handle idle validators in the transaction.

    Args:
        event_sequence: Event sequence counter
        fee_events: Current fee events list
        transaction_results: Transaction results to process
        idle_resolution_mode: How to handle idle validators:
            - "replace": Replace idle validators with reserves (default, existing behavior)
            - "partial": Count idle as DISAGREE, no replacement (SLASH_PARTIAL)

    Returns:
        Tuple of (updated TransactionRoundResults, updated fee_events)
    """
    new_fee_events = fee_events.copy()  # Create a copy to avoid modifying the input
    new_rounds = []

    for round_obj in transaction_results.rounds:
        if not round_obj.rotations:
            new_rounds.append(round_obj)
            continue

        rotation = round_obj.rotations[-1]
        votes = rotation.votes

        # Find idle validators
        idle_addresses = [
            addr for addr, vote in votes.items() if normalize_vote(vote) == "IDLE"
        ]

        # Slash idle validators
        for addr in idle_addresses:
            current_stake = compute_current_stake(addr, new_fee_events)
            new_fee_events.append(
                FeeEvent(
                    sequence_id=event_sequence.next_id(),
                    address=addr,
                    slashed=int(current_stake * IDLE_PENALTY_COEFFICIENT),
                )
            )

        if idle_addresses:
            if idle_resolution_mode == "partial":
                # Partial vote resolution: convert IDLE to DISAGREE, no replacement
                new_votes = resolve_partial_votes(votes)
                new_round = Round(
                    rotations=list(round_obj.rotations[:-1]) + [
                        Rotation(
                            votes=new_votes,
                            reserve_votes=rotation.reserve_votes,
                        )
                    ],
                )
                new_rounds.append(new_round)
            else:
                # Replace idle validators with reserves (original behavior)
                new_votes = {
                    addr: vote
                    for addr, vote in votes.items()
                    if normalize_vote(vote) != "IDLE"
                }
                reserve_count = len(idle_addresses)

                # Find available reserves
                available_reserves = [
                    addr
                    for addr, vote in rotation.reserve_votes.items()
                    if addr not in new_votes
                ]

                # Add reserves to replace idle validators
                for i in range(min(reserve_count, len(available_reserves))):
                    reserve_addr = available_reserves[i]
                    new_votes[reserve_addr] = rotation.reserve_votes[reserve_addr]

                # Update votes in the rotation
                new_round = Round(
                    rotations=list(round_obj.rotations[:-1]) + [
                        Rotation(
                            votes=new_votes,
                            reserve_votes=rotation.reserve_votes,
                        )
                    ],
                )
                new_rounds.append(new_round)
        else:
            # If no idle validators, keep the original round
            new_rounds.append(round_obj)

    new_transaction_results = TransactionRoundResults(
        rounds=new_rounds,
    )

    return new_transaction_results, new_fee_events
