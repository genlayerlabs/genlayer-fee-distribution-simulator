#!/usr/bin/env python3
"""Check if leader appeal burns are happening correctly."""

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

print("Checking burns after unsuccessful appeals:")
print("=" * 80)

for i, label in enumerate(round_labels):
    if i > 0 and round_labels[i - 1] in [
        "APPEAL_LEADER_UNSUCCESSFUL",
        "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
    ]:
        print(f"\nRound {i} ({label}) follows unsuccessful leader appeal")

        # Get events from previous round to see appeal bond
        prev_events = [
            e for e in fee_events if e.round_index == i - 1 and e.role == "APPEALANT"
        ]
        appeal_bond = sum(e.cost for e in prev_events)
        print(f"Previous round appeal bond: {appeal_bond}")

        # Check burns in current round
        curr_events = [e for e in fee_events if e.round_index == i]
        total_burn = sum(e.burned for e in curr_events)
        appealant_burn = sum(e.burned for e in curr_events if e.role == "APPEALANT")

        print(f"Burns in current round: total={total_burn}, appealant={appealant_burn}")

        # Check if burn matches what's expected
        earned_in_curr = sum(e.earned for e in curr_events)
        expected_burn = (
            appeal_bond - earned_in_curr if appeal_bond > earned_in_curr else 0
        )
        print(f"Earned in current round: {earned_in_curr}")
        print(f"Expected burn: {expected_burn}")

        if abs(total_burn - expected_burn) > 1:
            print(f"WARNING: Burn mismatch! Expected {expected_burn}, got {total_burn}")

# Also check the specific case in round 8
print("\n" + "=" * 80)
print("Detailed check of round 8 (SPLIT_PREVIOUS_APPEAL_BOND):")
print("=" * 80)

round_8_events = [e for e in fee_events if e.round_index == 8]
print(f"\nAll events in round 8:")
for e in round_8_events:
    if e.earned > 0 or e.burned > 0:
        print(f"  {e.role} ({e.address[:8]}...): earned={e.earned}, burned={e.burned}")

# Check if this round is supposed to burn
if round_labels[7] == "APPEAL_LEADER_UNSUCCESSFUL":
    appeal_events = [
        e for e in fee_events if e.round_index == 7 and e.role == "APPEALANT"
    ]
    appeal_bond = sum(e.cost for e in appeal_events)
    print(f"\nPrevious appeal bond: {appeal_bond}")
    print(f"Total earned in round 8: {sum(e.earned for e in round_8_events)}")
    print(f"Total burned in round 8: {sum(e.burned for e in round_8_events)}")
    print(f"Missing burn: {appeal_bond - sum(e.earned for e in round_8_events)}")
