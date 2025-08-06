#!/usr/bin/env python3
"""Trace where the 300 conservation loss happens."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fee_simulator.core.path_to_transaction import path_to_transaction_results
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.utils import generate_random_eth_address, is_appeal_round

# Generate addresses
addresses = [generate_random_eth_address() for _ in range(1000)]
sender_address = addresses[-1]
appealant_address = addresses[-2]

# Test path with conservation error
path = [
    "START",
    "LEADER_RECEIPT_MAJORITY_AGREE",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_SUCCESSFUL",
    "LEADER_RECEIPT_UNDETERMINED",
    "LEADER_APPEAL_UNSUCCESSFUL",
    "LEADER_RECEIPT_UNDETERMINED",
    "END",
]

print(f"Path: {' → '.join(path[1:-1])}")
print("=" * 80)

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

# Track the flow of value
print("\nVALUE FLOW TRACKING")
print("=" * 80)

# Track each round's net flow
net_flow = 0
for i, label in enumerate(round_labels):
    round_events = [e for e in fee_events if e.round_index == i]
    if round_events:
        cost = sum(e.cost for e in round_events)
        earned = sum(e.earned for e in round_events)
        burned = sum(e.burned for e in round_events)
        slashed = sum(e.slashed for e in round_events)

        # Net flow: costs go in, earnings+burns+slashes go out
        round_net = cost - earned - burned - slashed
        net_flow += round_net

        print(f"\nRound {i} ({label}):")
        print(f"  IN:  cost={cost}")
        print(
            f"  OUT: earned={earned}, burned={burned}, slashed={slashed} (total={earned+burned+slashed})"
        )
        print(f"  Net: {round_net} (cumulative: {net_flow})")

        # Check for specific issues
        if label == "APPEAL_VALIDATOR_UNSUCCESSFUL":
            # Count how many times this has occurred
            appeal_count = sum(
                1 for j in range(i + 1) if is_appeal_round(round_labels[j])
            )
            print(f"  This is appeal #{appeal_count}")

            # Check the appealant events
            appealant_events = [e for e in round_events if e.role == "APPEALANT"]
            for e in appealant_events:
                print(
                    f"  Appealant: cost={e.cost}, earned={e.earned}, burned={e.burned}"
                )

# The remaining net flow should be equal to the sender's refund
print(f"\nFinal net flow: {net_flow}")
print(f"This should equal the sender's refund")

# Check refunds
sender_events = [e for e in fee_events if e.address == sender_address]
sender_costs = sum(e.cost for e in sender_events)
sender_earnings = sum(e.earned for e in sender_events)
print(f"\nSender paid: {sender_costs}")
print(f"Sender earned: {sender_earnings}")

# Check if the 300 is related to specific appeal bonds
print("\n" + "=" * 80)
print("APPEAL BOND SIZES")
print("=" * 80)

from fee_simulator.core.bond_computing import compute_appeal_bond

for i, label in enumerate(round_labels):
    if is_appeal_round(label):
        # Find the normal round before this appeal
        normal_round_index = i - 1
        for j in range(i - 1, -1, -1):
            if not is_appeal_round(round_labels[j]):
                normal_round_index = j
                break

        bond = compute_appeal_bond(
            normal_round_index=normal_round_index,
            leader_timeout=100,
            validators_timeout=200,
            round_labels=round_labels,
            appeal_round_index=i,
        )

        print(f"Round {i} ({label}): bond = {bond}")

        # Check actual cost paid
        appealant_events = [
            e
            for e in fee_events
            if e.round_index == i and e.role == "APPEALANT" and e.cost > 0
        ]
        if appealant_events:
            actual_cost = sum(e.cost for e in appealant_events)
            print(f"  Actual cost paid: {actual_cost}")
            if actual_cost != bond:
                print(f"  MISMATCH: Expected {bond}, got {actual_cost}")

print(
    "\nNote: The 300 difference might be accumulating from multiple small discrepancies."
)
