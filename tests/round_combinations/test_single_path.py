#!/usr/bin/env python3
"""Test a single problematic path to debug the error."""

import sys
import os

# Add parent directory to path to import fee_simulator
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from fee_simulator.core.path_to_transaction import path_to_transaction_results
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.utils import generate_random_eth_address
from fee_simulator.constants import NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES

# Test one of the problematic paths
path = [
    "START",
    "LEADER_RECEIPT_MAJORITY_AGREE",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_SUCCESSFUL",
    "LEADER_RECEIPT_MAJORITY_AGREE",
    "END",
]

print(f"Testing path of length {len(path)}: {path}")
print(f"\nExpected round sizes based on new algorithm:")
print(f"Round 0 (Normal): {NORMAL_ROUND_SIZES[0]} = 5")
print(f"Round 1 (Appeal 0): {APPEAL_ROUND_SIZES[0]} = 7")
print(f"Round 2 (Appeal 1, unsuccessful): {APPEAL_ROUND_SIZES[1] - 2} = 11")
print(f"Round 3 (Appeal 2, unsuccessful): {APPEAL_ROUND_SIZES[2] - 2} = 23")
print(f"Round 4 (Appeal 3, unsuccessful): {APPEAL_ROUND_SIZES[3] - 2} = 47")
print(f"Round 5 (Appeal 4, unsuccessful): {APPEAL_ROUND_SIZES[4] - 2} = 95")
print(f"Round 6 (Appeal 5, unsuccessful): {APPEAL_ROUND_SIZES[5] - 2} = 191")
print(f"Round 7 (Appeal 6, unsuccessful): {APPEAL_ROUND_SIZES[6] - 2} = 383")
print(f"Round 8 (Appeal 7, successful): {APPEAL_ROUND_SIZES[7] - 2} = 767")
print(
    f"Round 9 (Normal): {NORMAL_ROUND_SIZES[1]} = 11 (but we have {5+7+11+23+47+95+191+383+767-1} = 1528 addresses used)"
)

# Generate addresses
addresses = [generate_random_eth_address() for _ in range(1000)]
sender_address = addresses[-1]
appealant_address = addresses[-2]

# Create a simple mapping for debugging
address_to_index = {addr: i for i, addr in enumerate(addresses)}

try:
    # Convert path to transaction results
    transaction_results, transaction_budget = path_to_transaction_results(
        path=path,
        addresses=addresses,
        sender_address=sender_address,
        appealant_address=appealant_address,
        leader_timeout=100,
        validators_timeout=200,
    )

    print(
        f"\nSuccessfully created transaction with {len(transaction_results.rounds)} rounds"
    )

    # Show address allocation for each round
    print("\nAddress allocation per round:")
    cumulative_used = set()
    for i, round_obj in enumerate(transaction_results.rounds):
        if round_obj.rotations:
            votes = round_obj.rotations[0].votes
            round_addresses = sorted(votes.keys(), key=lambda x: address_to_index[x])
            indices = [address_to_index[addr] for addr in round_addresses]

            print(f"\nRound {i}: {len(votes)} participants")
            if len(indices) > 20:
                print(
                    f"  Address indices: [{indices[0]}, {indices[1]}, ..., {indices[-2]}, {indices[-1]}]"
                )
            else:
                print(f"  Address indices: {indices}")
            print(f"  Range: {min(indices)}-{max(indices)}")

            cumulative_used.update(round_addresses)

    print(f"\nTotal unique addresses used: {len(cumulative_used)}")
    print(
        f"Maximum address index: {max(address_to_index[addr] for addr in cumulative_used)}"
    )

    # Get round labels
    round_labels = label_rounds(transaction_results)
    print(f"\nRound labels: {round_labels}")

    # Process transaction
    fee_events, _ = process_transaction(
        addresses=addresses,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    print(f"\nSuccessfully processed transaction with {len(fee_events)} fee events")

except Exception as e:
    import traceback

    print(f"\nError: {e}")
    traceback.print_exc()
