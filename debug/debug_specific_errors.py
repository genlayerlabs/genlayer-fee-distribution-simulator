#!/usr/bin/env python3
"""Debug the specific errors found in max-length 10 paths."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fee_simulator.core.path_to_transaction import path_to_transaction_results
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.utils import generate_random_eth_address, is_appeal_round
from fee_simulator.display.fee_distribution import display_fee_distribution
from fee_simulator.fee_aggregators.aggregated import (
    compute_agg_costs,
    compute_agg_earnings,
    compute_agg_appealant_burnt,
)
from fee_simulator.core.refunds import compute_sender_refund

# Generate addresses
addresses = [generate_random_eth_address() for _ in range(1000)]
sender_address = addresses[-1]
appealant_address = addresses[-2]

# Test path with conservation error
print("=" * 80)
print("DEBUGGING CONSERVATION ERROR (300 difference)")
print("=" * 80)

path1 = [
    "START",
    "LEADER_RECEIPT_MAJORITY_TIMEOUT",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "VALIDATOR_APPEAL_SUCCESSFUL",
    "LEADER_RECEIPT_MAJORITY_DISAGREE",
    "LEADER_APPEAL_UNSUCCESSFUL",
    "LEADER_RECEIPT_UNDETERMINED",
    "END",
]

transaction_results, transaction_budget = path_to_transaction_results(
    path=path1,
    addresses=addresses,
    sender_address=sender_address,
    appealant_address=appealant_address,
    leader_timeout=100,
    validators_timeout=200,
)

round_labels = label_rounds(transaction_results)
print(f"\nRound labels: {round_labels}")

fee_events, labels = process_transaction(
    addresses=addresses,
    transaction_results=transaction_results,
    transaction_budget=transaction_budget,
)

# Calculate conservation
total_costs = compute_agg_costs(fee_events)
total_earnings = compute_agg_earnings(fee_events)
sender_earnings = sum(
    event.earned for event in fee_events if event.address == sender_address
)
earnings_without_sender = total_earnings - sender_earnings
sender_refund = compute_sender_refund(
    sender_address, fee_events, transaction_budget, round_labels
)
appealant_burns = compute_agg_appealant_burnt(fee_events)

print(f"\nConservation analysis:")
print(f"Total costs: {total_costs}")
print(f"Earnings (excl. sender): {earnings_without_sender}")
print(f"Sender refund: {sender_refund}")
print(f"Appealant burns: {appealant_burns}")
print(f"Sum: {earnings_without_sender + sender_refund + appealant_burns}")
print(
    f"Difference: {total_costs - (earnings_without_sender + sender_refund + appealant_burns)}"
)

# Show round-by-round breakdown
print("\nRound-by-round breakdown:")
for i, label in enumerate(round_labels):
    round_events = [e for e in fee_events if e.round_index == i]
    if round_events:
        cost = sum(e.cost for e in round_events)
        earned = sum(e.earned for e in round_events)
        burned = sum(e.burned for e in round_events)
        slashed = sum(e.slashed for e in round_events)
        print(
            f"  Round {i} ({label}): cost={cost}, earned={earned}, burned={burned}, slashed={slashed}"
        )

# Check for any LEADER_TIMEOUT labels
timeout_labels = [
    i for i, label in enumerate(round_labels) if label == "LEADER_TIMEOUT"
]
if timeout_labels:
    print(f"\nWARNING: Found LEADER_TIMEOUT labels at indices: {timeout_labels}")

print("\n" + "=" * 80)
print("DEBUGGING VOTE CONSISTENCY ERROR")
print("=" * 80)

path2 = [
    "START",
    "LEADER_RECEIPT_MAJORITY_TIMEOUT",
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

transaction_results2, transaction_budget2 = path_to_transaction_results(
    path=path2,
    addresses=addresses,
    sender_address=sender_address,
    appealant_address=appealant_address,
    leader_timeout=100,
    validators_timeout=200,
)

round_labels2 = label_rounds(transaction_results2)
print(f"\nRound labels: {round_labels2}")

fee_events2, labels2 = process_transaction(
    addresses=addresses,
    transaction_results=transaction_results2,
    transaction_budget=transaction_budget2,
)

# Check round 8 specifically
print(f"\nRound 8 label: {round_labels2[8] if len(round_labels2) > 8 else 'N/A'}")

# Get votes from transaction
if len(transaction_results2.rounds) > 8:
    round8 = transaction_results2.rounds[8]
    if round8.rotations:
        votes = round8.rotations[-1].votes
        print(f"\nRound 8 votes from transaction:")
        for addr, vote in list(votes.items())[:5]:
            print(f"  {addr}: {vote}")

# Get events for round 8
round8_events = [e for e in fee_events2 if e.round_index == 8]
if round8_events:
    print(f"\nRound 8 events (first 5):")
    for event in round8_events[:5]:
        print(f"  {event.address}: role={event.role}, vote={event.vote}")

# Check if this is supposed to be an appeal round
if len(round_labels2) > 8:
    is_appeal = is_appeal_round(round_labels2[8])
    print(f"\nIs round 8 an appeal? {is_appeal}")
    print(f"Round 8 label: {round_labels2[8]}")
