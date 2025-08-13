#!/usr/bin/env python3
"""
Complex Path Example

This example demonstrates a complex transaction path with multiple
appeals and different outcomes, showing how the system handles
sophisticated scenarios.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.utils import generate_random_eth_address
from src.fee_simulator.display import (
    display_transaction_results,
    display_fee_distribution,
    display_summary_table,
)
from src.fee_simulator.specification.invariants.checker import check_all_invariants


def main():
    print("\n" + "=" * 80)
    print(" COMPLEX PATH EXAMPLE ")
    print("=" * 80)
    print("\nScenario: Multiple rounds with consecutive appeals, then a final normal round")
    print("Path: START → LEADER_RECEIPT_MAJORITY_AGREE → VALIDATOR_APPEAL_UNSUCCESSFUL")
    print("      → VALIDATOR_APPEAL_SUCCESSFUL → LEADER_RECEIPT_MAJORITY_AGREE → END")
    print("-" * 80)

    # Generate addresses for participants
    addresses = [generate_random_eth_address() for _ in range(1000)]
    sender_address = addresses[999]
    appealant_address = addresses[998]

    # Define a complex transaction path
    path = [
        "START",
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "VALIDATOR_APPEAL_UNSUCCESSFUL",
        "VALIDATOR_APPEAL_SUCCESSFUL",
        "LEADER_RECEIPT_MAJORITY_AGREE",
        "END",
    ]

    # Convert path to transaction results
    transaction_results, budget = path_to_transaction_results(
        path=path,
        addresses=addresses,
        sender_address=sender_address,
        appealant_address=appealant_address,
        leader_timeout=100,
        validators_timeout=200,
    )

    # Label the rounds based on vote patterns
    labels = label_rounds(transaction_results)

    # Process the transaction and distribute fees
    fee_events, _ = process_transaction(addresses, transaction_results, budget)

    # Display the transaction details
    print("\n" + "=" * 80)
    print(" TRANSACTION DETAILS ")
    print("=" * 80)
    display_transaction_results(transaction_results, labels, verbose=True)

    # Display fee distribution
    print("\n" + "=" * 80)
    print(" FEE DISTRIBUTION ")
    print("=" * 80)
    display_fee_distribution(fee_events)

    # Display summary table
    print("\n" + "=" * 80)
    print(" SUMMARY TABLE ")
    print("=" * 80)
    display_summary_table(fee_events, transaction_results, budget, labels, verbose=True)

    # Verify invariants
    print("\n" + "=" * 80)
    print(" INVARIANT VERIFICATION ")
    print("=" * 80)
    try:
        check_all_invariants(fee_events, budget, transaction_results, labels)
        print("✅ All 24 invariants passed!")
    except Exception as e:
        print(f"❌ Invariant violation: {e}")

    # Explain the outcome
    print("\n" + "=" * 80)
    print(" OUTCOME EXPLANATION ")
    print("=" * 80)
    print("In this complex scenario:")
    print("1. Round 0: Normal round where majority agreed")
    print("2. Round 1: First validator appeal - unsuccessful")
    print("3. Round 2: Second validator appeal - successful (appealing the first appeal)")
    print("4. Round 3: Final normal round where majority agreed")
    print("5. Results:")
    print("   - Round 0 becomes SKIP_ROUND (retroactively skipped due to successful appeal)")
    print("   - Round 1 becomes APPEAL_VALIDATOR_UNSUCCESSFUL")
    print("   - Round 2 becomes APPEAL_VALIDATOR_SUCCESSFUL")
    print("   - Round 3 becomes NORMAL_ROUND")
    print("6. Fee distribution:")
    print("   - Round 2 appellant earns 1.5x their appeal bond (50% ROI)")
    print("   - Round 1's unsuccessful appeal bond gets burned")
    print("   - Round 3 operates as a normal round with standard fee distribution")
    print("7. This demonstrates how consecutive appeals work and their economic consequences")

    print("\n" + "=" * 80)
    print(" TRANSACTION COMPLETE ")
    print("=" * 80)


if __name__ == "__main__":
    main()
