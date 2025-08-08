from typing import List

from src.fee_simulator.protocol.models import (
    TransactionBudget,
    TransactionRoundResults,
    FeeEvent,
    EventSequence,
)

from src.fee_simulator.protocol.types import (
    RoundLabel,
)

from src.fee_simulator.utils import (
    compute_total_cost,
    initialize_constant_stakes,
    is_appeal_round,
)

from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.core.idleness import replace_idle_participants
from src.fee_simulator.core.deterministic_violation import (
    handle_deterministic_violations,
)
from src.fee_simulator.core.round_fee_distribution.distribute_round import (
    distribute_round,
)
from src.fee_simulator.core.refunds import compute_sender_refund


def process_transaction(
    addresses: List[str],
    transaction_results: TransactionRoundResults,
    transaction_budget: TransactionBudget,
) -> tuple[List[FeeEvent], List[RoundLabel]]:

    event_sequence = EventSequence()  # singleton
    fee_events = []  # list of immutable objects that can be audited

    # Initialize stakes
    fee_events.extend(initialize_constant_stakes(event_sequence, addresses))

    # Subtract total cost from sender address
    sender_address = transaction_budget.senderAddress
    fee_events.append(
        FeeEvent(
            sequence_id=event_sequence.next_id(),
            address=sender_address,
            role="SENDER",
            cost=compute_total_cost(transaction_budget),
        )
    )

    # Replace idle validators and slash them
    replace_idle_transaction_results, replace_idle_fee_events = (
        replace_idle_participants(
            event_sequence=event_sequence,
            fee_events=fee_events,
            transaction_results=transaction_results,
        )
    )
    fee_events = replace_idle_fee_events

    # Handle deterministic violations (hash mismatches)
    fee_events.extend(
        handle_deterministic_violations(
            replace_idle_transaction_results, event_sequence
        )
    )

    # Get labels for all rounds
    labels = label_rounds(replace_idle_transaction_results)

    # Process each round with its label
    for i, round_obj in enumerate(replace_idle_transaction_results.rounds):
        if i < len(labels):

            # Subtract appeal bond from appealant address
            if is_appeal_round(labels[i]):  # Use the new function
                # Find which appeal this is (counting only actual appeals)
                appeal_count = sum(
                    1 for j in range(i + 1) if is_appeal_round(labels[j])
                )
                appeal_index = appeal_count - 1

                if appeal_index < len(transaction_budget.appeals):
                    appealant_address = transaction_budget.appeals[
                        appeal_index
                    ].appealantAddress
                    # Find the most recent normal round before this appeal
                    normal_round_index = i - 1  # Default to previous round
                    for j in range(i - 1, -1, -1):
                        if not is_appeal_round(labels[j]):
                            normal_round_index = j
                            break
                    bond = compute_appeal_bond(
                        normal_round_index=normal_round_index,
                        leader_timeout=transaction_budget.leaderTimeout,
                        validators_timeout=transaction_budget.validatorsTimeout,
                        round_labels=labels,  # Pass labels
                        appeal_round_index=i,  # Pass the current appeal round index
                    )
                    fee_events.append(
                        FeeEvent(
                            sequence_id=event_sequence.next_id(),
                            round_index=i,
                            round_label=labels[i],
                            role="APPEALANT",
                            address=appealant_address,
                            cost=bond,
                        )
                    )

            round_fee_events = distribute_round(
                transaction_results=replace_idle_transaction_results,
                round_index=i,
                label=labels[i],
                budget=transaction_budget,
                event_sequence=event_sequence,
                round_labels=labels,  # Pass labels
            )
            fee_events.extend(round_fee_events)

    refunds = compute_sender_refund(
        sender_address, fee_events, transaction_budget, labels
    )
    fee_events.append(
        FeeEvent(
            sequence_id=event_sequence.next_id(),
            address=sender_address,
            role="SENDER",
            earned=refunds,
        )
    )

    return fee_events, labels
