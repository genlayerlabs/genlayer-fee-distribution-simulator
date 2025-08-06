#!/usr/bin/env python3
"""Debug conservation issues for longer paths (length 7-9)."""

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
from fee_simulator.fee_aggregators.aggregated import (
    compute_agg_costs,
    compute_agg_earnings,
    compute_agg_burnt,
    compute_agg_appealant_burnt,
)
from fee_simulator.core.refunds import compute_sender_refund
from fee_simulator.display.fee_distribution import display_fee_distribution

# Generate addresses
addresses = [generate_random_eth_address() for _ in range(1000)]
sender_address = addresses[-1]
appealant_address = addresses[-2]

# Find paths with large conservation issues
print("Finding paths with large conservation issues...")

for length in [7, 8, 9]:
    constraints = PathConstraints(
        source_node="START", target_node="END", min_length=length, max_length=length
    )
    paths = list(generate_all_paths(TRANSACTION_GRAPH, constraints))

    for path in paths:
        # Skip if doesn't have multiple appeals
        appeal_count = sum(1 for node in path if "APPEAL" in node)
        if appeal_count < 3:  # Look for paths with 3+ appeals
            continue

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

            # Check conservation
            total_costs = compute_agg_costs(fee_events)
            total_earnings = compute_agg_earnings(fee_events)

            # Exclude sender's earnings
            sender_earnings = sum(
                event.earned
                for event in fee_events
                if event.address == transaction_budget.senderAddress
            )
            earnings_without_sender = total_earnings - sender_earnings

            # Calculate refund
            sender_refund = compute_sender_refund(
                transaction_budget.senderAddress,
                fee_events,
                transaction_budget,
                round_labels,
            )

            # Calculate appealant burns
            appealant_burns = compute_agg_appealant_burnt(fee_events)

            expected = earnings_without_sender + sender_refund + appealant_burns
            difference = total_costs - expected

            # Look for significant differences (> 2000)
            if abs(difference) > 2000:
                print(f"\n{'='*80}")
                print(f"Found path with large conservation issue: {' → '.join(path)}")
                print(f"Path length: {length}, Appeal count: {appeal_count}")
                print(f"Round labels: {round_labels}")
                print(f"\nConservation Analysis:")
                print(f"Total costs: {total_costs}")
                print(f"Total earnings (excl. sender): {earnings_without_sender}")
                print(f"Sender refund: {sender_refund}")
                print(f"Appealant burns: {appealant_burns}")
                print(f"Expected total: {expected}")
                print(f"Difference: {difference}")

                # Show appealant-related events
                print("\nAppealant events:")
                for event in fee_events:
                    if event.role == "APPEALANT":
                        print(
                            f"  Round {event.round_index}: cost={event.cost}, earned={event.earned}, burned={event.burned}"
                        )

                # Show burn events
                print("\nAll burn events:")
                burn_count = 0
                for event in fee_events:
                    if event.burned > 0:
                        burn_count += 1
                        print(
                            f"  Round {event.round_index} ({event.role}): burned={event.burned}"
                        )

                if burn_count == 0:
                    print("  No burn events found!")

                # Show leader appeal labels
                print("\nLeader appeal rounds:")
                for i, label in enumerate(round_labels):
                    if "LEADER" in label and "APPEAL" in label:
                        print(f"  Round {i}: {label}")

                # Break after finding first issue
                break

        except Exception as e:
            print(f"Error processing path {path}: {e}")
            import traceback

            traceback.print_exc()
            continue

    # Break if we found an issue
    if abs(difference) > 2000:
        break

print("\nDone.")
