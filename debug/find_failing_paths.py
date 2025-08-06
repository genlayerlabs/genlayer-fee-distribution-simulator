#!/usr/bin/env python3
"""Find paths that are failing invariant checks."""

import sys
import os
import json

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

print("Finding paths with failing invariants...")

# Try different lengths
for max_length in [10]:
    print(f"\nChecking paths of length {max_length}...")

    constraints = PathConstraints(
        source_node="START",
        target_node="END",
        min_length=max_length,
        max_length=max_length,
    )
    paths = list(generate_all_paths(TRANSACTION_GRAPH, constraints))

    failed_paths = []
    error_types = {}

    for i, path in enumerate(paths[:50]):  # Check first 50 paths
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
                failed_paths.append(path)

                # Categorize error
                if "Conservation of value" in error_msg:
                    error_type = "conservation"
                elif "Majority/minority consistency" in error_msg:
                    error_type = "majority_minority"
                elif "Vote consistency" in error_msg:
                    error_type = "vote_consistency"
                elif "Leader timeout earning" in error_msg:
                    error_type = "leader_timeout"
                else:
                    error_type = "other"

                if error_type not in error_types:
                    error_types[error_type] = []
                error_types[error_type].append((path, error_msg))

                if len(failed_paths) == 1:  # Analyze first failure in detail
                    print(f"\nFirst failing path: {' → '.join(path)}")
                    print(f"Error: {error_msg}")
                    print(f"Round labels: {round_labels}")

                    # Show round details
                    print("\nRound details:")
                    for j, label in enumerate(round_labels):
                        round_events = [e for e in fee_events if e.round_index == j]
                        if round_events:
                            total_cost = sum(e.cost for e in round_events)
                            total_earned = sum(e.earned for e in round_events)
                            total_burned = sum(e.burned for e in round_events)
                            total_slashed = sum(e.slashed for e in round_events)
                            print(
                                f"  Round {j} ({label}): cost={total_cost}, earned={total_earned}, burned={total_burned}, slashed={total_slashed}"
                            )

        except Exception as e:
            continue

    print(f"\nSummary for length {max_length}:")
    print(f"Total paths checked: {min(50, len(paths))}")
    print(f"Failed paths: {len(failed_paths)}")

    if error_types:
        print("\nError breakdown:")
        for error_type, errors in error_types.items():
            print(f"  {error_type}: {len(errors)}")

        # Show examples
        if "conservation" in error_types and error_types["conservation"]:
            path, msg = error_types["conservation"][0]
            print(f"\nExample conservation error:")
            print(f"  Path: {' → '.join(path[:5])}...")
            print(f"  {msg[:200]}...")

        if "majority_minority" in error_types and error_types["majority_minority"]:
            path, msg = error_types["majority_minority"][0]
            print(f"\nExample majority/minority error:")
            print(f"  Path: {' → '.join(path[:5])}...")
            print(f"  {msg[:200]}...")
