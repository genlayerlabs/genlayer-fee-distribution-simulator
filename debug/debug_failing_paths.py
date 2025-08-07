#!/usr/bin/env python3
"""Debug specific failing paths in the fee distribution system."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.round_combinations.graph_data import TRANSACTION_GRAPH
from tests.round_combinations.path_generator import generate_all_paths
from tests.round_combinations.path_types import PathConstraints
from fee_simulator.core.path_to_transaction import path_to_transaction_results
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.utils import generate_random_eth_address
from tests.fee_distributions.check_invariants.comprehensive_invariants import (
    check_all_invariants,
)
from fee_simulator.display.fee_distribution import display_fee_distribution
from fee_simulator.display.summary_table import display_summary_table
from fee_simulator.display.transaction_results import display_transaction_results

# Generate addresses
addresses = [generate_random_eth_address() for _ in range(1000)]
sender_address = addresses[-1]
appealant_address = addresses[-2]

# Generate paths of length 3 and 4
failing_paths = []
print("Searching for failing paths...")

for length in [3, 4]:
    constraints = PathConstraints(min_length=length, max_length=length)
    paths = list(generate_all_paths(TRANSACTION_GRAPH, constraints))

    for path in paths:
        try:
            # Convert path to transaction
            transaction_results, transaction_budget = path_to_transaction_results(
                path=path,
                addresses=addresses,
                sender_address=sender_address,
                appealant_address=appealant_address,
                leader_timeout=100,
                validators_timeout=200,
            )

            # Get round labels
            round_labels = label_rounds(transaction_results)

            # Process transaction
            fee_events, labels = process_transaction(
                addresses=addresses,
                transaction_results=transaction_results,
                transaction_budget=transaction_budget,
            )

            # Check invariants
            success, violations = check_all_invariants(
                fee_events=fee_events,
                transaction_results=transaction_results,
                transaction_budget=transaction_budget,
                round_labels=round_labels,
            )

            if not success:
                failing_paths.append((path, violations))

        except Exception as e:
            print(f"Error processing path {path}: {e}")

print(f"\nFound {len(failing_paths)} failing paths")

# Analyze the first few failing paths
for i, (path, violations) in enumerate(failing_paths[:5]):
    print(f"\n{'='*80}")
    print(f"Failing path {i+1}: {' → '.join(path)}")
    print(f"Violations: {violations}")

    # Re-process to show details
    transaction_results, transaction_budget = path_to_transaction_results(
        path=path,
        addresses=addresses,
        sender_address=sender_address,
        appealant_address=appealant_address,
        leader_timeout=100,
        validators_timeout=200,
    )

    round_labels = label_rounds(transaction_results)
    print(f"Round labels: {round_labels}")

    fee_events, _ = process_transaction(
        addresses=addresses,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    print("\nFee Distribution:")
    display_fee_distribution(fee_events)
