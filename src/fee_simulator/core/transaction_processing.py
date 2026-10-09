from dataclasses import dataclass
from types import MappingProxyType
from typing import List, Mapping

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
from src.fee_simulator.utils_round_sizes import find_previous_normal_round

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


@dataclass(frozen=True)
class EventOrigin:
    generation: int
    round_index: int


@dataclass(frozen=True)
class GenerationEvidence:
    generation: int
    results: TransactionRoundResults
    labels: tuple[RoundLabel, ...]
    invalidated: bool


@dataclass(frozen=True)
class FeeSimulation:
    """Ordinary fee output plus provenance; does not change any fee rule."""

    fee_events: tuple[FeeEvent, ...]
    labels: tuple[RoundLabel, ...]
    origins: Mapping[int, EventOrigin]
    generations: tuple[GenerationEvidence, ...]


def process_transaction(
    addresses: List[str],
    transaction_results: TransactionRoundResults,
    transaction_budget: TransactionBudget,
    discarded_generations: List[TransactionRoundResults] | None = None,
) -> tuple[List[FeeEvent], List[RoundLabel]]:
    simulation = process_transaction_with_provenance(
        addresses, transaction_results, transaction_budget, discarded_generations,
    )
    return list(simulation.fee_events), list(simulation.labels)


def process_transaction_with_provenance(
    addresses: List[str],
    transaction_results: TransactionRoundResults,
    transaction_budget: TransactionBudget,
    discarded_generations: List[TransactionRoundResults] | None = None,
) -> FeeSimulation:
    """Keep generation/round identity separate from mutable payout labels.

    The ordinary entry point retains its tuple result and event serialization.
    This evidence is used by the opt-in owner-liability settlement.
    """
    history = discarded_generations or []
    return _process_transaction(
        addresses, transaction_results, transaction_budget, history, len(history),
    )


def _process_transaction(
    addresses, transaction_results, transaction_budget, discarded_generations, generation_id,
) -> FeeSimulation:

    discarded_generations = discarded_generations or []
    if discarded_generations:
        _validate_recompute_allowance(discarded_generations, transaction_results, transaction_budget)

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
                    normal_round_index = find_previous_normal_round(i, labels)
                    if normal_round_index is None:
                        normal_round_index = i - 1  # Default to previous round
                    bond = compute_appeal_bond(
                        normal_round_index=normal_round_index,
                        leader_timeout=transaction_budget.leaderTimeout,
                        validators_timeout=transaction_budget.validatorsTimeout,
                        round_labels=labels,  # Pass labels
                        appeal_round_index=i,  # Pass the current appeal round index
                        rotations=transaction_budget.rotations,
                        rotations_used=transaction_budget.rotationsUsed,
                        invalidated_generation=transaction_budget.recomputeInvalidated,
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

    origins = {
        event.sequence_id: EventOrigin(generation_id, event.round_index)
        for event in fee_events if event.round_index is not None
    }
    evidence = [GenerationEvidence(
        generation_id, replace_idle_transaction_results.model_copy(deep=True),
        tuple(labels), transaction_budget.recomputeInvalidated,
    )]

    # Preserve historical time-unit work without collecting another sender
    # deposit or spending appeal bonds already returned on invalidation.
    for historical_id, generation in enumerate(discarded_generations):
        historical = _process_transaction(
            addresses, generation,
            transaction_budget.model_copy(update={"recomputeInvalidated": True}),
            [], historical_id,
        )
        evidence.extend(historical.generations)
        for event in historical.fee_events:
            if event.role in ("LEADER", "VALIDATOR") and not event.staked:
                new_id = event_sequence.next_id()
                fee_events.append(event.model_copy(update={"sequence_id": new_id}))
                if event.sequence_id in historical.origins:
                    origins[new_id] = historical.origins[event.sequence_id]

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

    return FeeSimulation(
        tuple(fee_events), tuple(labels), MappingProxyType(origins),
        tuple(sorted(evidence, key=lambda item: item.generation)),
    )


def _validate_recompute_allowance(history, current, budget):
    """Ordinary rotations and lazy replays consume the same per-round limit."""
    used = [0] * len(budget.rotations)
    for generation in [*history, current]:
        labels = label_rounds(generation)
        for index, round_obj in enumerate(generation.rounds):
            if is_appeal_round(labels[index]) or not round_obj.rotations:
                continue
            ordinal = index // 2
            if ordinal >= len(used):
                raise ValueError("Missing funded normal round")
            used[ordinal] += max(0, len(round_obj.rotations) - 1)
    for generation in history:
        ordinal = (len(generation.rounds) - 1) // 2
        used[ordinal] += 1
    if any(spent > funded for spent, funded in zip(used, budget.rotations)):
        raise ValueError("Recomputation exceeds assigned rotations")
