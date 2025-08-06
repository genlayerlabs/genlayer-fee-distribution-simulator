#!/usr/bin/env python3
"""Debug conservation issues for length 10 paths."""

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
from fee_simulator.display.fee_distribution import display_fee_distribution

# Generate addresses
addresses = [generate_random_eth_address() for _ in range(1000)]
sender_address = addresses[-1]
appealant_address = addresses[-2]

# Look for specific conservation amounts
print("Finding paths with specific conservation issues (5100 or 300)...")

constraints = PathConstraints(
    source_node="START", target_node="END", min_length=10, max_length=10
)
paths = list(generate_all_paths(TRANSACTION_GRAPH, constraints))

found_5100 = False
found_300 = False

for path in paths:
    if found_5100 and found_300:
        break

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

        # Look for specific differences
        if abs(difference - 5100) < 10 and not found_5100:
            found_5100 = True
            print(f"\n{'='*80}")
            print(f"Found path with 5100 conservation issue: {' → '.join(path)}")
            print(f"Round labels: {round_labels}")
            print(f"\nConservation Analysis:")
            print(f"Total costs: {total_costs}")
            print(f"Total earnings (excl. sender): {earnings_without_sender}")
            print(f"Sender refund: {sender_refund}")
            print(f"Appealant burns: {appealant_burns}")
            print(f"Expected total: {expected}")
            print(f"Difference: {difference}")

            # Count LEADER_TIMEOUT labels
            leader_timeout_count = sum(
                1 for label in round_labels if label == "LEADER_TIMEOUT"
            )
            print(f"\nLEADER_TIMEOUT labels: {leader_timeout_count}")

            # Show appealant events
            print("\nAppealant events:")
            for event in fee_events:
                if event.role == "APPEALANT":
                    print(
                        f"  Round {event.round_index}: cost={event.cost}, earned={event.earned}, burned={event.burned}"
                    )

            # Show which rounds have which labels
            print("\nRound label details:")
            for i, label in enumerate(round_labels):
                if "TIMEOUT" in label or "APPEAL" in label:
                    print(f"  Round {i}: {label}")

        elif abs(difference - 300) < 10 and not found_300:
            found_300 = True
            print(f"\n{'='*80}")
            print(f"Found path with 300 conservation issue: {' → '.join(path)}")
            print(
                f"Round labels: {round_labels[:5]} ... {round_labels[-5:]}"
            )  # Show first and last 5
            print(f"Total rounds: {len(round_labels)}")
            print(f"Total costs: {total_costs}")
            print(f"Difference: {difference}")

            # Count round types
            appeal_count = sum(1 for label in round_labels if is_appeal_round(label))
            normal_count = sum(1 for label in round_labels if label == "NORMAL_ROUND")
            print(f"Appeals: {appeal_count}, Normal rounds: {normal_count}")

    except Exception as e:
        continue

print("\nDone.")
