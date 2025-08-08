#!/usr/bin/env python3
"""
Basic Transaction Example

This example demonstrates a simple transaction flow with a normal round
where the majority of validators agree with the leader.
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
    print("\n" + "="*80)
    print(" BASIC TRANSACTION EXAMPLE ")
    print("="*80)
    print("\nScenario: Normal round with majority agreement")
    print("Path: START → LEADER_RECEIPT_MAJORITY_AGREE → END")
    print("-"*80)
    
    # Generate addresses for participants
    addresses = [generate_random_eth_address() for _ in range(1000)]
    sender_address = addresses[999]
    appealant_address = addresses[998]
    
    # Define the transaction path
    path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
    
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
    print("\n" + "="*80)
    print(" TRANSACTION DETAILS ")
    print("="*80)
    display_transaction_results(transaction_results, labels, verbose=True)
    
    # Display fee distribution
    print("\n" + "="*80)
    print(" FEE DISTRIBUTION ")
    print("="*80)
    display_fee_distribution(fee_events)
    
    # Display summary table
    print("\n" + "="*80)
    print(" SUMMARY TABLE ")
    print("="*80)
    display_summary_table(fee_events, transaction_results, budget, labels, verbose=True)
    
    # Verify invariants
    print("\n" + "="*80)
    print(" INVARIANT VERIFICATION ")
    print("="*80)
    try:
        check_all_invariants(fee_events, budget, transaction_results, labels)
        print("✅ All 22 invariants passed!")
    except Exception as e:
        print(f"❌ Invariant violation: {e}")
    
    print("\n" + "="*80)
    print(" TRANSACTION COMPLETE ")
    print("="*80)

if __name__ == "__main__":
    main()