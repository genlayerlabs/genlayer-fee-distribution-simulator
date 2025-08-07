#!/usr/bin/env python3
"""Debug why more validators are burned than expected."""

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

# Test path
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

# Get round 8 votes and burns
round_8 = transaction_results.rounds[8]
votes = round_8.rotations[-1].votes

print(f"Round 8 has {len(votes)} voters")

# Get majority/minority
majority = compute_majority(votes)
majority_addresses, minority_addresses = who_is_in_vote_majority(votes, majority)

print(f"Majority: {majority}")
print(f"Majority count: {len(majority_addresses)}")
print(f"Minority count: {len(minority_addresses)}")

# Get burns
burned_addresses = set()
round_8_events = [e for e in fee_events if e.round_index == 8]
for e in round_8_events:
    if e.burned > 0:
        burned_addresses.add(e.address)

print(f"\nBurned addresses: {len(burned_addresses)}")

# Check overlap
minority_set = set(minority_addresses)
burned_set = burned_addresses

print(f"\nOverlap analysis:")
print(f"Minority addresses that were burned: {len(minority_set & burned_set)}")
print(f"Non-minority addresses that were burned: {len(burned_set - minority_set)}")

# Let's see who the extra burned addresses are
extra_burned = burned_set - minority_set
if extra_burned:
    print(f"\nChecking votes of extra burned addresses:")
    for addr in list(extra_burned)[:5]:  # First 5
        vote = votes.get(addr, "NOT FOUND")
        print(f"  {addr[:8]}...: vote={vote}")

# Check if this is related to combining votes from multiple rounds
print(f"\nChecking if APPEAL_VALIDATOR_SUCCESSFUL combines votes...")

# Look at round 7 (previous round)
if len(transaction_results.rounds) > 7:
    round_7 = transaction_results.rounds[7]
    if round_7.rotations:
        votes_7 = round_7.rotations[-1].votes
        print(f"\nRound 7 has {len(votes_7)} voters")

        # Check if round 8 burns are based on combined votes
        combined_votes = {**votes_7, **votes}
        combined_majority = compute_majority(combined_votes)
        combined_majority_addrs, combined_minority_addrs = who_is_in_vote_majority(
            combined_votes, combined_majority
        )

        print(f"\nCombined votes from rounds 7+8:")
        print(f"Total voters: {len(combined_votes)}")
        print(f"Combined majority: {combined_majority}")
        print(f"Combined minority count: {len(combined_minority_addrs)}")

        # Check if this matches burns
        if len(combined_minority_addrs) == len(burned_addresses):
            print("\nMATCH! Burns are based on COMBINED votes from rounds 7+8")

        # Show vote counts
        vote_counts = {}
        for vote in combined_votes.values():
            vote_str = str(vote)
            vote_counts[vote_str] = vote_counts.get(vote_str, 0) + 1
        print(f"Combined vote breakdown: {vote_counts}")
