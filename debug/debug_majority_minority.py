#!/usr/bin/env python3
"""Debug the majority/minority consistency error."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fee_simulator.core.path_to_transaction import path_to_transaction_results
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.utils import generate_random_eth_address
from fee_simulator.core.majority import compute_majority, who_is_in_vote_majority

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
print(f"Round labels: {round_labels}")

fee_events, labels = process_transaction(
    addresses=addresses,
    transaction_results=transaction_results,
    transaction_budget=transaction_budget,
)

# Focus on round 8
print(f"\nRound 8 label: {round_labels[8]}")

# Get round 8 data
round_8 = transaction_results.rounds[8]
if round_8.rotations:
    votes = round_8.rotations[-1].votes
    majority = compute_majority(votes)
    majority_addresses, minority_addresses = who_is_in_vote_majority(votes, majority)

    print(f"\nRound 8 voting analysis:")
    print(f"Total voters: {len(votes)}")
    print(f"Majority: {majority}")
    print(f"Majority count: {len(majority_addresses)}")
    print(f"Minority count: {len(minority_addresses)}")

    # Count vote types
    vote_counts = {}
    for vote in votes.values():
        vote_str = str(vote)
        vote_counts[vote_str] = vote_counts.get(vote_str, 0) + 1
    print(f"Vote breakdown: {vote_counts}")

# Check round 8 events
round_8_events = [e for e in fee_events if e.round_index == 8]
print(f"\nRound 8 events: {len(round_8_events)} total")

# Count burns by role
minority_burns = []
majority_burns = []
for e in round_8_events:
    if e.burned > 0:
        if e.address in minority_addresses:
            minority_burns.append((e.address, e.burned))
        elif e.address in majority_addresses:
            majority_burns.append((e.address, e.burned))

print(f"\nBurns in round 8:")
print(f"Minority validators with burns: {len(minority_burns)}")
if minority_burns:
    print(f"Burn per minority validator: {minority_burns[0][1]}")
    print(f"Total minority burns: {sum(b[1] for b in minority_burns)}")

print(f"Majority validators with burns: {len(majority_burns)}")
if majority_burns:
    print(f"Total majority burns: {sum(b[1] for b in majority_burns)}")

# Check the budget
print(f"\nBudget validators timeout: {transaction_budget.validatorsTimeout}")
print(f"Expected burn per minority validator: {transaction_budget.validatorsTimeout}")
print(f"Expected total for 118 minority: {118 * transaction_budget.validatorsTimeout}")

# Check if this is related to the appeal bond distribution
print(f"\nChecking if round 8 is APPEAL_VALIDATOR_SUCCESSFUL...")
if round_labels[8] == "APPEAL_VALIDATOR_SUCCESSFUL":
    print("Yes, this is a successful validator appeal")

    # Check the appeal bond calculation
    from fee_simulator.core.bond_computing import compute_appeal_bond

    # Find normal round before appeal
    normal_round_index = 7
    for i in range(7, -1, -1):
        if round_labels[i] == "NORMAL_ROUND":
            normal_round_index = i
            break

    appeal_bond = compute_appeal_bond(
        normal_round_index=normal_round_index,
        leader_timeout=transaction_budget.leaderTimeout,
        validators_timeout=transaction_budget.validatorsTimeout,
        round_labels=round_labels,
        appeal_round_index=8,
    )

    print(f"\nAppeal bond: {appeal_bond}")
    print(f"Should pay 150% to appealant: {int(appeal_bond * 1.5)}")

    # Check what the appealant actually got
    appealant_events = [e for e in round_8_events if e.role == "APPEALANT"]
    if appealant_events:
        print(f"Appealant earned: {sum(e.earned for e in appealant_events)}")

# Check for any coefficient being applied
from fee_simulator.constants import PENALTY_REWARD_COEFFICIENT

print(f"\nPENALTY_REWARD_COEFFICIENT: {PENALTY_REWARD_COEFFICIENT}")

# Let's see if the burn amount matches any pattern
if minority_burns:
    burn_amount = minority_burns[0][1]
    print(f"\nAnalyzing burn amount: {burn_amount}")
    print(
        f"burn_amount / validators_timeout = {burn_amount / transaction_budget.validatorsTimeout}"
    )

    # Check if it's related to round index
    print(f"Round index: 8")
    print(
        f"Number of appeals so far: {sum(1 for label in round_labels[:9] if 'APPEAL' in label)}"
    )
