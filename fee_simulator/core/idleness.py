from typing import List
from fee_simulator.models import (
    TransactionRoundResults,
    FeeEvent,
    Round,
    Rotation,
    EventSequence,
)

from fee_simulator.core.majority import (
    normalize_vote,
)

from fee_simulator.fee_aggregators.address_metrics import compute_current_stake


def replace_idle_participants(
    event_sequence: EventSequence,
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults,
) -> tuple[TransactionRoundResults, List[FeeEvent]]:
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
                    slashed=current_stake * 0.01,
                )
            )

        # Replace idle validators with reserves
        if idle_addresses:
            new_votes = {
                addr: vote
                for addr, vote in votes.items()
                if normalize_vote(vote) != "Idle"
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
                rotations=[
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
