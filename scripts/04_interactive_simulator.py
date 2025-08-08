#!/usr/bin/env python3
"""
Interactive Fee Distribution Simulator

This script provides an interactive way to build transaction paths and
visualize the fee distribution results with all tables and outputs.
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
from src.fee_simulator.specification.state_machine.graph import TRANSACTION_GRAPH
from src.fee_simulator.specification.state_machine.path_analysis.path_generator import generate_all_paths
from src.fee_simulator.specification.state_machine.path_analysis.path_types import PathConstraints

# Available nodes from the TRANSACTION_GRAPH
AVAILABLE_NODES = {
    "1": "LEADER_RECEIPT_MAJORITY_AGREE",
    "2": "LEADER_RECEIPT_MAJORITY_DISAGREE", 
    "3": "LEADER_RECEIPT_UNDETERMINED",
    "4": "LEADER_RECEIPT_MAJORITY_TIMEOUT",
    "5": "LEADER_TIMEOUT",
    "6": "LEADER_APPEAL_SUCCESSFUL",
    "7": "LEADER_APPEAL_UNSUCCESSFUL",
    "8": "VALIDATOR_APPEAL_SUCCESSFUL",
    "9": "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "10": "LEADER_APPEAL_TIMEOUT_SUCCESSFUL",
    "11": "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL",
}

def print_header():
    """Print the application header."""
    print("\n" + "="*80)
    print(" INTERACTIVE FEE DISTRIBUTION SIMULATOR ")
    print("="*80)
    print("\nBuild your own transaction path and see how fees are distributed!")
    print("-"*80)

def print_available_nodes():
    """Print available node options."""
    print("\n📋 Available Transaction Nodes:")
    print("-" * 40)
    for key, value in AVAILABLE_NODES.items():
        print(f"  [{key:2}] {value}")
    print("-" * 40)

def validate_path_transitions(path):
    """Validate if a path has valid transitions according to TRANSACTION_GRAPH."""
    for i in range(len(path) - 1):
        current = path[i]
        next_node = path[i + 1]
        
        if current not in TRANSACTION_GRAPH:
            return False, f"Unknown node: {current}"
        
        valid_next = TRANSACTION_GRAPH.get(current, [])
        if next_node not in valid_next:
            return False, f"Invalid transition: {current} → {next_node}\nValid next nodes from {current}: {', '.join(valid_next)}"
    
    return True, "Valid path"

def build_path_interactive():
    """Build a transaction path by entering node numbers."""
    print("\n" + "="*80)
    print(" CUSTOM PATH BUILDER ")
    print("="*80)
    
    print("\n📋 How to build a path:")
    print("  • Enter node numbers separated by commas (e.g., 1,8,2)")
    print("  • The path automatically starts with START and ends with END")
    print("  • Use the node reference table to find numbers")
    
    print("\n📌 Example paths:")
    print("  • Simple: 1")
    print("  • With appeal: 1,8,2")
    print("  • Complex: 1,9,8,1")
    
    while True:
        path_input = input("\n👉 Enter node numbers (comma-separated) or 'q' to quit: ").strip()
        
        if path_input.lower() == 'q':
            print("\n👋 Returning to main menu...")
            return None
        
        if not path_input:
            print("❌ Please enter at least one node number")
            continue
        
        try:
            # Parse the input
            node_numbers = [n.strip() for n in path_input.split(',')]
            path_nodes = []
            
            # Convert numbers to node names
            invalid = False
            for num in node_numbers:
                if num not in AVAILABLE_NODES:
                    print(f"❌ Invalid node number: {num}")
                    print(f"   Valid numbers are: {', '.join(AVAILABLE_NODES.keys())}")
                    invalid = True
                    break
                path_nodes.append(AVAILABLE_NODES[num])
            
            if invalid:
                continue
            
            # Build complete path
            full_path = ["START"] + path_nodes + ["END"]
            
            # Validate the path
            is_valid, message = validate_path_transitions(full_path)
            
            if not is_valid:
                print(f"\n❌ Invalid path: {message}")
                print("\n💡 Tip: Check src/fee_simulator/specification/state_machine/graph.py")
                print("   to see all valid transitions, or use the step-by-step builder.")
                print("\n🔍 Your attempted path:")
                print("   " + " → ".join(full_path))
                continue
            
            # Success!
            print("\n✅ Valid path created!")
            print("   " + " → ".join(full_path))
            return full_path
            
        except Exception as e:
            print(f"❌ Error: {e}")
            print("   Please enter numbers separated by commas (e.g., 1,8,2)")

def get_simulation_parameters():
    """Get simulation parameters from user."""
    print("\n⚙️  Simulation Parameters")
    print("-" * 40)
    
    # Leader timeout
    while True:
        try:
            leader_timeout = input("Leader timeout (default 100): ").strip()
            leader_timeout = int(leader_timeout) if leader_timeout else 100
            if leader_timeout > 0:
                break
            print("❌ Must be positive")
        except ValueError:
            print("❌ Invalid number")
    
    # Validators timeout
    while True:
        try:
            validators_timeout = input("Validators timeout (default 200): ").strip()
            validators_timeout = int(validators_timeout) if validators_timeout else 200
            if validators_timeout > 0:
                break
            print("❌ Must be positive")
        except ValueError:
            print("❌ Invalid number")
    
    return leader_timeout, validators_timeout

def run_simulation(path, leader_timeout, validators_timeout):
    """Run the simulation with the given path and parameters."""
    print("\n" + "="*80)
    print(" RUNNING SIMULATION ")
    print("="*80)
    
    # Generate addresses
    print("\n🎲 Generating addresses...")
    addresses = [generate_random_eth_address() for _ in range(1000)]
    sender_address = addresses[999]
    appealant_address = addresses[998]
    
    # Convert path to transaction
    print("📝 Creating transaction from path...")
    transaction_results, budget = path_to_transaction_results(
        path=path,
        addresses=addresses,
        sender_address=sender_address,
        appealant_address=appealant_address,
        leader_timeout=leader_timeout,
        validators_timeout=validators_timeout,
    )
    
    # Label rounds
    print("🏷️  Labeling rounds...")
    labels = label_rounds(transaction_results)
    
    # Process transaction
    print("💰 Processing fee distribution...")
    fee_events, _ = process_transaction(addresses, transaction_results, budget)
    
    return transaction_results, budget, labels, fee_events

def display_results(transaction_results, budget, labels, fee_events, path):
    """Display all results with tables."""
    
    # Display the path
    print("\n" + "="*80)
    print(" TRANSACTION PATH ")
    print("="*80)
    print(" → ".join(path))
    
    # Display transaction details
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
    
    # Display round labels explanation
    print("\n" + "="*80)
    print(" ROUND LABELS EXPLANATION ")
    print("="*80)
    for i, label in enumerate(labels):
        print(f"  Round {i}: {label}")
    
    print("\n" + "="*80)
    print(" SIMULATION COMPLETE ")
    print("="*80)

def main():
    """Main interactive loop."""
    print_header()
    
    while True:
        print("\n" + "="*80)
        print(" MAIN MENU ")
        print("="*80)
        print("\n[1] Build custom path interactively")
        print("[2] Use example path (Simple)")
        print("[3] Use example path (With Appeal)")
        print("[4] Use example path (Complex)")
        print("[5] Show available nodes reference")
        print("[q] Quit")
        
        choice = input("\n👉 Enter your choice: ").strip().lower()
        
        if choice == 'q':
            print("\n👋 Thank you for using the Fee Distribution Simulator!")
            break
        
        elif choice == '1':
            # Build custom path
            print_available_nodes()
            path = build_path_interactive()
            if path is None:
                continue
            
            print("\n✅ Path built successfully!")
            print("Path:", " → ".join(path))
            
            # Get parameters
            leader_timeout, validators_timeout = get_simulation_parameters()
            
            # Run simulation
            transaction_results, budget, labels, fee_events = run_simulation(
                path, leader_timeout, validators_timeout
            )
            
            # Display results
            display_results(transaction_results, budget, labels, fee_events, path)
            
            input("\n📊 Press Enter to continue...")
        
        elif choice == '2':
            # Simple example
            path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
            print("\n📌 Using simple path:", " → ".join(path))
            
            # Run with default parameters
            transaction_results, budget, labels, fee_events = run_simulation(
                path, 100, 200
            )
            
            # Display results
            display_results(transaction_results, budget, labels, fee_events, path)
            
            input("\n📊 Press Enter to continue...")
        
        elif choice == '3':
            # Appeal example
            path = [
                "START",
                "LEADER_RECEIPT_MAJORITY_AGREE",
                "VALIDATOR_APPEAL_SUCCESSFUL",
                "LEADER_RECEIPT_MAJORITY_DISAGREE",
                "END"
            ]
            print("\n📌 Using appeal path:", " → ".join(path))
            
            # Run with default parameters
            transaction_results, budget, labels, fee_events = run_simulation(
                path, 100, 200
            )
            
            # Display results
            display_results(transaction_results, budget, labels, fee_events, path)
            
            input("\n📊 Press Enter to continue...")
        
        elif choice == '4':
            # Complex example
            path = [
                "START",
                "LEADER_RECEIPT_MAJORITY_AGREE",
                "VALIDATOR_APPEAL_UNSUCCESSFUL",
                "VALIDATOR_APPEAL_SUCCESSFUL",
                "LEADER_RECEIPT_MAJORITY_AGREE",
                "END"
            ]
            print("\n📌 Using complex path:", " → ".join(path))
            
            # Run with default parameters
            transaction_results, budget, labels, fee_events = run_simulation(
                path, 100, 200
            )
            
            # Display results
            display_results(transaction_results, budget, labels, fee_events, path)
            
            input("\n📊 Press Enter to continue...")
        
        elif choice == '5':
            # Show nodes reference
            print_available_nodes()
            input("\n📊 Press Enter to continue...")
        
        else:
            print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        import traceback
        traceback.print_exc()