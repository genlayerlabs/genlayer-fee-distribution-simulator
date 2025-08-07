#!/usr/bin/env python3
"""Debug specific errors for max-length 10 paths."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.round_combinations.graph_data import TRANSACTION_GRAPH
from tests.round_combinations.path_generator import generate_all_paths
from tests.round_combinations.path_types import PathConstraints
from fee_simulator.core.path_to_transaction import path_to_transaction_results
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.utils import generate_random_eth_address, is_appeal_round
from fee_simulator.fee_aggregators.aggregated import (
    compute_agg_costs,
    compute_agg_earnings,
    compute_agg_burnt,
    compute_agg_appealant_burnt,
)
from fee_simulator.core.refunds import compute_sender_refund
from tests.fee_distributions.check_invariants.comprehensive_invariants import (
    check_comprehensive_invariants,
)

# Generate addresses
addresses = [generate_random_eth_address() for _ in range(1000)]
sender_address = addresses[-1]
appealant_address = addresses[-2]

print("Searching for paths with specific errors...")

constraints = PathConstraints(
    source_node="START", target_node="END", min_length=10, max_length=10
)
paths = list(generate_all_paths(TRANSACTION_GRAPH, constraints))

error_types = {"conservation": [], "majority_minority": [], "vote_consistency": []}

for i, path in enumerate(paths):
    if i % 100 == 0:
        print(f"Checked {i}/{len(paths)} paths...")
    if (
        len(error_types["conservation"]) >= 5
        and len(error_types["majority_minority"]) >= 5
    ):
        break  # Found enough examples

    try:
        # Process the path
        transaction_results, transaction_budget = path_to_transaction_results(
            path=path,
            addresses=addresses,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=100,
            validators_timeout=200,
        )

        round_labels = label_rounds(transaction_results)

        fee_events, labels = process_transaction(
            addresses=addresses,
            transaction_results=transaction_results,
            transaction_budget=transaction_budget,
        )

        # Check invariants with dynamic tolerance
        num_rounds = len(round_labels)
        tolerance = num_rounds * 20

        try:
            check_comprehensive_invariants(
                fee_events,
                transaction_budget,
                transaction_results,
                round_labels,
                tolerance=tolerance,
            )
        except AssertionError as e:
            error_msg = str(e)

            # Categorize the error
            if "Conservation of value" in error_msg:
                if "300" in error_msg:
                    error_types["conservation"].append((path, error_msg))
                    print(f"\n{'='*80}")
                    print(f"Found conservation error (300): {' → '.join(path)}")
                    print(f"Round labels: {round_labels}")

                    # Check for LEADER_TIMEOUT labels
                    timeout_indices = [
                        i
                        for i, label in enumerate(round_labels)
                        if label == "LEADER_TIMEOUT"
                    ]
                    if timeout_indices:
                        print(f"LEADER_TIMEOUT at indices: {timeout_indices}")

            elif "Majority/minority consistency" in error_msg:
                error_types["majority_minority"].append((path, error_msg))
                print(f"\n{'='*80}")
                print(f"Found majority/minority error: {' → '.join(path)}")
                print(f"Error: {error_msg}")

            elif "Vote consistency" in error_msg:
                error_types["vote_consistency"].append((path, error_msg))
                print(f"\n{'='*80}")
                print(f"Found vote consistency error: {' → '.join(path)}")
                print(f"Error: {error_msg}")

    except Exception as e:
        continue

print(f"\n{'='*80}")
print("Summary:")
print(f"Conservation errors: {len(error_types['conservation'])}")
print(f"Majority/minority errors: {len(error_types['majority_minority'])}")
print(f"Vote consistency errors: {len(error_types['vote_consistency'])}")

# Analyze first conservation error in detail
if error_types["conservation"]:
    print(f"\n{'='*80}")
    print("Analyzing first conservation error in detail...")

    path, error_msg = error_types["conservation"][0]
    print(f"Path: {' → '.join(path)}")

    # Reprocess to get details
    transaction_results, transaction_budget = path_to_transaction_results(
        path=path,
        addresses=addresses,
        sender_address=sender_address,
        appealant_address=appealant_address,
        leader_timeout=100,
        validators_timeout=200,
    )

    round_labels = label_rounds(transaction_results)

    fee_events, labels = process_transaction(
        addresses=addresses,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Show round by round
    print("\nRound by round analysis:")
    for i, label in enumerate(round_labels):
        print(f"Round {i}: {label}")

        # Show fee events for this round
        round_events = [e for e in fee_events if e.round_index == i]
        if round_events:
            total_cost = sum(e.cost for e in round_events)
            total_earned = sum(e.earned for e in round_events)
            total_burned = sum(e.burned for e in round_events)
            print(
                f"  Cost: {total_cost}, Earned: {total_earned}, Burned: {total_burned}"
            )
