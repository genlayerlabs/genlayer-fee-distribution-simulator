#!/usr/bin/env python3
"""Debug all burns in round 8."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fee_simulator.core.path_to_transaction import path_to_transaction_results
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.utils import generate_random_eth_address

# Generate addresses
addresses = [generate_random_eth_address() for _ in range(1000)]
sender_address = addresses[-1]
appealant_address = addresses[-2]

# Test path with error
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
    "END",
]

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

# Get ALL burns in round 8
round_8_events = [e for e in fee_events if e.round_index == 8]

print("ALL burns in round 8:")
print("=" * 80)

total_burns = 0
burns_by_role = {}

for e in round_8_events:
    if e.burned > 0:
        total_burns += e.burned
        if e.role not in burns_by_role:
            burns_by_role[e.role] = 0
        burns_by_role[e.role] += e.burned

print(f"Total burns: {total_burns}")
print(f"\nBurns by role:")
for role, amount in burns_by_role.items():
    print(f"  {role}: {amount}")

# Count events by role
print(f"\nEvent counts by role:")
role_counts = {}
for e in round_8_events:
    if e.burned > 0:
        key = f"{e.role} (burn={e.burned})"
        role_counts[key] = role_counts.get(key, 0) + 1

for role, count in role_counts.items():
    print(f"  {role}: {count} events")

# Check if there are any APPEALANT burns
appealant_burns = [e for e in round_8_events if e.role == "APPEALANT" and e.burned > 0]
if appealant_burns:
    print(f"\nAppealant burns found: {len(appealant_burns)}")
    for e in appealant_burns:
        print(f"  Burn amount: {e.burned}")

# Let's see all the previous round labels
print(f"\nAll round labels: {round_labels}")

# Check for burns from previous unsuccessful appeals
print("\nChecking for burns from previous rounds...")
for i in range(7):
    if round_labels[i] in [
        "APPEAL_VALIDATOR_UNSUCCESSFUL",
        "APPEAL_LEADER_UNSUCCESSFUL",
    ]:
        # Get appeal bond for this round
        appeal_events = [
            e
            for e in fee_events
            if e.round_index == i and e.role == "APPEALANT" and e.cost > 0
        ]
        if appeal_events:
            appeal_bond = sum(e.cost for e in appeal_events)
            print(f"Round {i} ({round_labels[i]}): appeal bond = {appeal_bond}")

            # Check if this bond was burned in round i+1
            next_round_burns = [
                e
                for e in fee_events
                if e.round_index == i + 1 and e.role == "APPEALANT" and e.burned > 0
            ]
            if next_round_burns:
                burn_amount = sum(e.burned for e in next_round_burns)
                print(f"  Burned in round {i+1}: {burn_amount}")
            else:
                print(f"  NOT burned in round {i+1}!")
