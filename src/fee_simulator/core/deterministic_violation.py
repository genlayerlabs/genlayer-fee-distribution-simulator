from typing import List

from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    FeeEvent,
)

from src.fee_simulator.core.majority import (
    compute_majority_hash,
    normalize_vote,
    who_is_in_hash_majority,
)

from src.fee_simulator.metrics.address_metrics import compute_current_stake


def handle_deterministic_violations(
    transaction_results: TransactionRoundResults, last_event_index: int
) -> List[FeeEvent]:
    fee_events = []
    new_event_index = last_event_index
    for i, round_obj in enumerate(transaction_results.rounds):
        if round_obj.rotations:
            rotation = round_obj.rotations[-1]
            votes = rotation.votes

            # Compute majority hash (independent of vote type)
            majority_hash = compute_majority_hash(votes)

            if majority_hash:
                # Get addresses in hash majority and minority
                hash_majority_addresses, hash_minority_addresses = (
                    who_is_in_hash_majority(votes, majority_hash)
                )

                # Slash validators in hash minority
                for addr in hash_minority_addresses:
                    if normalize_vote(votes[addr]) != "Idle":
                        # Leader is slashed more (5%) than validators (1%)
                        current_stake = compute_current_stake(addr, fee_events)
                        slash_rate = 0.05 if addr == next(iter(votes.keys())) else 0.01
                        fee_events.append(
                            FeeEvent(
                                sequence_id=new_event_index,
                                address=addr,
                                slashed=current_stake * (1 - slash_rate),
                            )
                        )
                        new_event_index += 1

    return fee_events
