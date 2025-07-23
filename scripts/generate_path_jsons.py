#!/usr/bin/env python3
"""
Generate JSON files for all paths in the TRANSITIONS_GRAPH.

This script processes all possible paths through the fee distribution state machine
and generates compressed JSON files containing the results for verification by
the consensus algorithm implementation.
"""

import json
import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import argparse
from tqdm import tqdm

# Add parent directory to path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.round_combinations.graph_data import TRANSACTION_GRAPH
from tests.round_combinations.path_generator import generate_all_paths
from tests.round_combinations.path_types import PathConstraints
from tests.round_combinations.path_filter import filter_valid_paths, is_valid_path
from fee_simulator.core.path_to_transaction import path_to_transaction_results
from fee_simulator.core.transaction_processing import process_transaction
from fee_simulator.core.round_labeling import label_rounds
from fee_simulator.types import RoundLabel
from fee_simulator.utils import generate_random_eth_address

# Constants
LEADER_TIMEOUT = 100
VALIDATORS_TIMEOUT = 200


# Create lookup tables for compression
NODE_TO_IDX = {
    "START": 0,
    "LEADER_RECEIPT_MAJORITY_AGREE": 1,
    "LEADER_RECEIPT_UNDETERMINED": 2,
    "LEADER_RECEIPT_MAJORITY_DISAGREE": 3,
    "LEADER_RECEIPT_MAJORITY_TIMEOUT": 4,
    "LEADER_TIMEOUT": 5,
    "VALIDATOR_APPEAL_SUCCESSFUL": 6,
    "VALIDATOR_APPEAL_UNSUCCESSFUL": 7,
    "LEADER_APPEAL_SUCCESSFUL": 8,
    "LEADER_APPEAL_UNSUCCESSFUL": 9,
    "LEADER_APPEAL_TIMEOUT_SUCCESSFUL": 10,
    "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL": 11,
    "END": 12,
}

LABEL_TO_IDX = {
    "NORMAL_ROUND": 0,
    "EMPTY_ROUND": 1,
    "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL": 2,
    "APPEAL_LEADER_TIMEOUT_SUCCESSFUL": 3,
    "APPEAL_LEADER_SUCCESSFUL": 4,
    "APPEAL_LEADER_UNSUCCESSFUL": 5,
    "APPEAL_VALIDATOR_SUCCESSFUL": 6,
    "APPEAL_VALIDATOR_UNSUCCESSFUL": 7,
    "LEADER_TIMEOUT": 8,
    "SKIP_ROUND": 9,
    "LEADER_TIMEOUT_50_PERCENT": 10,
    "SPLIT_PREVIOUS_APPEAL_BOND": 11,
    "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND": 12,
    "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND": 13,
}

ROLE_TO_IDX = {
    "LEADER": 0,
    "VALIDATOR": 1,
    "SENDER": 2,
    "APPEALANT": 3,
}

# Invariant bit positions
INVARIANT_BITS = {
    "conservation_of_value": 0,
    "non_negative_balances": 1,
    "appeal_bond_coverage": 2,
    "majority_minority_consistency": 3,
    "role_exclusivity": 4,
    "sequential_processing": 5,
    "appeal_follows_normal": 6,
    "burn_non_negativity": 7,
    "refund_non_negativity": 8,
    "vote_consistency": 9,
    "idle_slashing_correctness": 10,
    "deterministic_violation_slashing": 11,
    "leader_timeout_earning_limits": 12,
    "appeal_bond_consistency": 13,
    "round_size_consistency": 14,
    "fee_event_ordering": 15,
    "stake_immutability": 16,
    "round_label_validity": 17,
    "no_double_penalties": 18,
    "earning_justification": 19,
    "cost_accounting": 20,
    "slashing_proportionality": 21,
}


def hash_path(path: List[str]) -> str:
    """Generate SHA256 hash of a path for deduplication."""
    path_str = "-".join(path)
    return hashlib.sha256(path_str.encode()).hexdigest()


def get_address_index(address: str, address_map: Dict[str, int]) -> int:
    """Get sequential index for address."""
    if address not in address_map:
        address_map[address] = len(address_map) + 1
    return address_map[address]


def check_invariants(
    fee_events, transaction_budget, transaction_results, round_labels
) -> int:
    """
    Check invariants and return bitfield of results.
    Returns an integer where each bit represents whether an invariant passed (1) or failed (0).
    """
    from tests.fee_distributions.check_invariants.comprehensive_invariants import (
        check_comprehensive_invariants,
    )

    bitfield = 0
    
    # Dynamic tolerance based on number of rounds and actual rounding operations
    # Rounding errors occur when split_amount divides amounts among validators
    # Count rounds that actually perform splits
    num_rounds = len(round_labels)
    
    # Count rounds that perform fee splits (these cause rounding errors)
    split_rounds = 0
    for label in round_labels:
        if label in [
            "NORMAL_ROUND",
            "SPLIT_PREVIOUS_APPEAL_BOND", 
            "APPEAL_VALIDATOR_SUCCESSFUL",
            "APPEAL_VALIDATOR_UNSUCCESSFUL",
            "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND"
        ]:
            split_rounds += 1
    
    # Each split can lose up to (number_of_recipients - 1) wei
    # Use average round size as estimate
    avg_round_size = 200  # Conservative average between small and large rounds
    tolerance = split_rounds * avg_round_size + num_rounds * 2  # Plus small buffer per round

    try:
        # Try to check all invariants
        check_comprehensive_invariants(
            fee_events,
            transaction_budget,
            transaction_results,
            round_labels,
            tolerance=tolerance,
        )
        # If no exception, all invariants passed
        bitfield = (1 << len(INVARIANT_BITS)) - 1  # All bits set to 1
    except AssertionError as e:
        print(f"Error checking invariants: {e}")
        # Parse which invariants failed from the error message
        # For now, we'll set all bits to 1 except a few to indicate some failure
        # In a real implementation, we'd parse the specific failing invariants
        bitfield = (1 << len(INVARIANT_BITS)) - 1  # Start with all passing
        # Clear first bit to indicate at least one failure
        bitfield &= ~1
        # Re-raise the error so it gets counted as an error
        raise

    return bitfield


def process_path(path: List[str], addresses: List[str]) -> Dict[str, Any]:
    """Process a single path and return the compressed result."""
    # Fixed addresses for sender and appealant
    sender_address = addresses[-1]
    appealant_address = addresses[-2]

    # Convert path to transaction results
    transaction_results, transaction_budget = path_to_transaction_results(
        path=path,
        addresses=addresses,
        sender_address=sender_address,
        appealant_address=appealant_address,
        leader_timeout=LEADER_TIMEOUT,
        validators_timeout=VALIDATORS_TIMEOUT,
    )

    # Get round labels
    round_labels = label_rounds(transaction_results)

    # Process transaction
    fee_events, _ = process_transaction(
        addresses=addresses,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )

    # Address mapping for sequential numbering
    address_map = {}

    # Aggregate results by participant
    participants = defaultdict(
        lambda: {
            "r": [],  # rounds with roles
            "c": 0,  # cost
            "e": 0,  # earned
            "s": 0,  # slashed
            "b": 0,  # burned
        }
    )

    for event in fee_events:
        if event.address:
            addr_idx = get_address_index(event.address, address_map)

            # Track rounds and roles
            if event.round_index is not None and event.role:
                role_idx = ROLE_TO_IDX.get(event.role, -1)
                if role_idx >= 0:
                    participants[addr_idx]["r"].append([event.round_index, role_idx])

            # Aggregate amounts
            participants[addr_idx]["c"] += event.cost
            participants[addr_idx]["e"] += event.earned
            participants[addr_idx]["s"] += event.slashed
            participants[addr_idx]["b"] += event.burned

    # Filter out participants with no activity (excluding initial stake events)
    active_participants = {}
    for addr_idx, data in participants.items():
        if data["c"] > 0 or data["e"] > 0 or data["s"] > 0 or data["b"] > 0:
            active_participants[addr_idx] = data

    # Convert path and labels to indices
    path_indices = [NODE_TO_IDX[node] for node in path]
    label_indices = [LABEL_TO_IDX.get(label, -1) for label in round_labels]

    # Check invariants
    invariant_bitfield = check_invariants(
        fee_events, transaction_budget, transaction_results, round_labels
    )

    # Create result
    result = {
        "path": path_indices,
        "labels": label_indices,
        "participants": active_participants,
        "invariants": invariant_bitfield,
        "hash": hash_path(path),
    }

    return result


def generate_filename(path: List[str]) -> str:
    """Generate filename for a path."""
    path_length = len(path) - 2  # Exclude START and END
    # Create a short hash of the path for uniqueness
    path_hash = hash_path(path)[:8]
    return f"{path_length:02d}-{path_hash}.json"


def save_lookup_tables(output_dir: Path):
    """Save the lookup tables as a separate JSON file."""
    # Reverse the dictionaries for decoding
    idx_to_node = {v: k for k, v in NODE_TO_IDX.items()}
    idx_to_label = {v: k for k, v in LABEL_TO_IDX.items()}
    idx_to_role = {v: k for k, v in ROLE_TO_IDX.items()}

    lookup_tables = {
        "node_map": idx_to_node,
        "label_map": idx_to_label,
        "role_map": idx_to_role,
        "invariant_bits": {str(v): k for k, v in INVARIANT_BITS.items()},
    }

    lookup_file = output_dir / "lookup_tables.json"
    with open(lookup_file, "w") as f:
        json.dump(lookup_tables, f, indent=2)

    print(f"Saved lookup tables to {lookup_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate JSON files for fee distribution paths"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="path_jsons",
        help="Output directory for JSON files",
    )
    parser.add_argument(
        "--max-length", type=int, default=16, help="Maximum path length to generate (default: 16, as 17+ have no valid paths)"
    )
    parser.add_argument(
        "--test-mode", action="store_true", help="Run in test mode with limited paths"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of paths to process before updating progress (deprecated, kept for compatibility)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show detailed error information including stack traces",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Process all paths without 1000 validator filtering (not recommended)",
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Save lookup tables
    save_lookup_tables(output_dir)

    # Generate addresses pool
    addresses = [generate_random_eth_address() for _ in range(1000)]

    # Initialize counters
    processed = 0
    errors = 0

    print(f"Generating paths up to length {args.max_length}...")
    if not args.no_filter:
        print("Filtering enabled: Only processing paths valid with 1000 validators")

    # First, count total paths to process
    total_paths = 0
    total_valid_paths = 0
    print("Counting total paths...")
    for length in range(3, args.max_length + 1):
        constraints = PathConstraints(
            source_node="START", target_node="END", min_length=length, max_length=length
        )
        all_paths = list(generate_all_paths(TRANSACTION_GRAPH, constraints))
        path_count = len(all_paths)
        
        if args.no_filter:
            valid_count = path_count
        else:
            # Filter valid paths
            valid_paths = filter_valid_paths(all_paths, max_addresses=1000)
            valid_count = len(valid_paths)
        
        total_paths += path_count
        total_valid_paths += valid_count
        
        if args.no_filter:
            print(f"Length {length}: {path_count} paths")
        else:
            print(f"Length {length}: {valid_count}/{path_count} valid paths ({valid_count/path_count*100:.1f}%)" if path_count > 0 else f"Length {length}: 0 paths")

    if args.no_filter:
        print(f"\nTotal paths to process: {total_paths}")
    else:
        print(f"\nTotal paths to process: {total_valid_paths} (out of {total_paths} theoretical paths)")

    # Process by length to organize output
    # Start from length 3 as minimum
    progress_bar = tqdm(total=total_valid_paths if not args.no_filter else total_paths, 
                       desc="Processing paths", unit="path")

    for length in range(3, args.max_length + 1):
        length_dir = output_dir / f"length_{length:02d}"
        length_dir.mkdir(exist_ok=True)

        length_count = 0

        # Generate paths of this length
        constraints = PathConstraints(
            source_node="START",
            target_node="END",
            min_length=length,  # length is measured in edges
            max_length=length,  # exact length
        )

        all_paths = list(generate_all_paths(TRANSACTION_GRAPH, constraints))
        
        # Filter if needed
        if args.no_filter:
            paths_to_process = all_paths
        else:
            paths_to_process = filter_valid_paths(all_paths, max_addresses=1000)
        
        # Skip if no valid paths
        if not paths_to_process:
            continue

        for path in paths_to_process:

            if args.test_mode and length_count >= 10:
                break

            try:
                # Process the path
                result = process_path(path, addresses)

                # Save to file
                filename = generate_filename(path)
                filepath = length_dir / filename

                with open(filepath, "w") as f:
                    json.dump(result, f, separators=(",", ":"))  # Compact format

                processed += 1
                length_count += 1
                progress_bar.update(1)

            except Exception as e:
                errors += 1
                print(f"\nError processing path {path}: {e}")
                if args.debug or args.test_mode:
                    import traceback

                    traceback.print_exc()
                    print(f"Path length: {len(path)}")
                    print(f"Path hash: {hash_path(path)}")
                if args.test_mode:
                    raise

        if args.test_mode:
            print("Test mode: stopping after first length")
            break

    progress_bar.close()

    print(f"\nCompleted!")
    print(f"Total paths processed: {processed}")
    print(f"Errors: {errors}")
    
    if not args.no_filter:
        print(f"\nFiltering summary:")
        print(f"Theoretical paths (no filtering): {total_paths:,}")
        print(f"Valid paths (1000 validator limit): {total_valid_paths:,}")
        print(f"Paths filtered out: {total_paths - total_valid_paths:,}")
        print(f"Validity rate: {total_valid_paths/total_paths*100:.1f}%")


if __name__ == "__main__":
    main()
