#!/usr/bin/env python3
"""
Convert decoded test vector output to Solidity test JSON format.

This script takes the existing compressed JSON files and converts them
to a format suitable for Solidity testing, preserving all the actual
simulation results without any modifications.
"""

import json
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Add parent directory to path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fee_simulator.protocol.models import (
    TransactionBudget,
    TransactionRoundResults,
)
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.utils import generate_random_eth_address


def load_lookup_tables(json_dir: Path) -> Dict[str, Dict]:
    """Load the lookup tables from the JSON directory."""
    lookup_file = json_dir / "lookup_tables.json"
    with open(lookup_file, "r") as f:
        return json.load(f)


def decode_path(compressed_data: Dict, lookup_tables: Dict) -> List[str]:
    """Decode the compressed path using lookup tables."""
    path = []
    for idx in compressed_data["path"]:
        path.append(lookup_tables["node_map"][str(idx)])
    return path


def shorten_address(address: str) -> str:
    """Shorten an Ethereum address for display."""
    if len(address) > 10:
        return f"{address[:8]}...{address[-6:]}"
    return address


def convert_to_solidity_format(
    json_file: Path,
    lookup_tables: Dict
) -> Dict[str, Any]:
    """
    Convert a single compressed JSON file to Solidity test format.
    """
    # Load the compressed JSON
    with open(json_file, "r") as f:
        compressed_data = json.load(f)
    
    # Decode the path
    path = decode_path(compressed_data, lookup_tables)
    
    # Generate addresses (deterministic based on file)
    addresses = [generate_random_eth_address() for _ in range(1000)]
    
    # Map compressed indices to actual addresses
    addr_map = {}
    for idx_str in compressed_data["participants"].keys():
        idx = int(idx_str)
        if idx <= len(addresses):
            addr_map[idx] = addresses[idx - 1]  # 1-indexed to 0-indexed
    
    # Identify sender (highest index participant)
    max_addr_idx = max(int(k) for k in compressed_data["participants"].keys())
    sender_address = addr_map.get(max_addr_idx, addresses[999])
    appealant_address = addr_map.get(max_addr_idx - 1, addresses[998]) if max_addr_idx > 1 else None
    
    # Recreate the transaction to get vote information
    transaction_results, transaction_budget = path_to_transaction_results(
        path=path,
        addresses=addresses,
        sender_address=sender_address,
        appealant_address=appealant_address,
        leader_timeout=100,
        validators_timeout=200,
    )
    
    # Process to get fee events
    fee_events, _ = process_transaction(
        addresses=addresses,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )
    
    # Extract test case information
    test_case = {
        "description": f"Test Case: {' -> '.join(path[1:-1])}",
        "initialState": {
            "validators": [],
            "leader": None,
            "sender": shorten_address(sender_address)
        },
        "actions": [{"type": "DISTRIBUTE_FEES", "epoch": 1}],
        "expectedState": {
            "rewards": [],
            "penalties": [],
            "sender_outcome": {
                "address": shorten_address(sender_address),
                "net_change": "0"
            }
        }
    }
    
    # Extract validator information from first round
    if transaction_results.rounds and transaction_results.rounds[0].rotations:
        rotation = transaction_results.rounds[0].rotations[0]
        
        # Sort addresses for consistent ordering
        sorted_votes = sorted(rotation.votes.items())
        
        for addr, vote in sorted_votes:
            # Handle vote which could be a string or list
            vote_str = vote
            if isinstance(vote, list):
                # If it's a list like ['LEADER_RECEIPT', 'AGREE'], extract the leader action
                if len(vote) > 0:
                    if vote[0] in ["LEADER_RECEIPT", "LEADER_TIMEOUT"]:
                        test_case["initialState"]["leader"] = shorten_address(addr)
                        vote_str = vote[0]  # Use just the leader action
                    else:
                        vote_str = vote[1] if len(vote) > 1 else vote[0]
            elif vote in ["LEADER_RECEIPT", "LEADER_TIMEOUT"]:
                test_case["initialState"]["leader"] = shorten_address(addr)
            
            # Add validator info
            test_case["initialState"]["validators"].append({
                "address": shorten_address(addr),
                "stake": "2000000",
                "vote": vote_str
            })
    
    # Calculate rewards and penalties from fee events
    sender_net = 0
    for event in fee_events:
        short_addr = shorten_address(event.address)
        
        if event.address == sender_address:
            sender_net = event.earned - event.cost
        elif event.earned > 0:
            test_case["expectedState"]["rewards"].append({
                "address": short_addr,
                "amount": str(event.earned)
            })
        
        if event.burned > 0:
            test_case["expectedState"]["penalties"].append({
                "address": short_addr,
                "amount": str(event.burned)
            })
    
    test_case["expectedState"]["sender_outcome"]["net_change"] = str(sender_net)
    
    return test_case


def process_directory(json_dir: Path, output_dir: Path, pretty: bool = False):
    """Process all JSON files in a directory."""
    lookup_tables = load_lookup_tables(json_dir)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_test_cases = []
    
    # Process each length directory
    for length_dir in sorted(json_dir.iterdir()):
        if not length_dir.is_dir() or not length_dir.name.startswith("length_"):
            continue
        
        # Create output subdirectory
        output_length_dir = output_dir / length_dir.name
        output_length_dir.mkdir(exist_ok=True)
        
        # Process each JSON file in this length directory
        for json_file in sorted(length_dir.glob("*.json")):
            test_case = convert_to_solidity_format(json_file, lookup_tables)
            
            # Save individual file
            output_file = output_length_dir / f"{json_file.stem}_solidity.json"
            with open(output_file, "w") as f:
                json.dump([test_case], f, indent=4 if pretty else None)
            
            all_test_cases.append(test_case)
            print(f"Processed: {json_file.name} -> {output_file.name}")
    
    # Save all test cases in one file
    all_output_file = output_dir / "all_test_cases.json"
    with open(all_output_file, "w") as f:
        json.dump(all_test_cases, f, indent=4 if pretty else None)
    
    print(f"\nTotal test cases: {len(all_test_cases)}")
    print(f"All test cases saved to: {all_output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert path JSON files to Solidity test format",
        epilog="Examples:\n"
        "  python 03_convert_to_solidity_json.py path_jsons/length_01/01-6290536c.json\n"
        "  python 03_convert_to_solidity_json.py --all --json-dir path_jsons --output-dir solidity_test_jsons",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "json_file",
        type=str,
        nargs="?",
        help="Path to a specific JSON file to convert"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all JSON files in the json-dir"
    )
    parser.add_argument(
        "--json-dir",
        type=str,
        default="path_jsons",
        help="Directory containing the JSON files (default: path_jsons)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="solidity_test_jsons",
        help="Output directory for Solidity test JSONs (default: solidity_test_jsons)"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print the JSON output"
    )
    
    args = parser.parse_args()
    
    if not args.json_file and not args.all:
        parser.error("Either specify a json_file or use --all flag")
    
    if args.json_file:
        # Process single file
        json_file = Path(args.json_file)
        json_dir = Path(args.json_dir)
        lookup_tables = load_lookup_tables(json_dir)
        
        test_case = convert_to_solidity_format(json_file, lookup_tables)
        
        # Output to stdout
        if args.pretty:
            print(json.dumps([test_case], indent=4))
        else:
            print(json.dumps([test_case]))
        
        # Save to file
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{json_file.stem}_solidity.json"
        with open(output_file, "w") as f:
            json.dump([test_case], f, indent=4 if args.pretty else None)
        
        print(f"\nSaved to: {output_file}", file=sys.stderr)
    
    else:
        # Process all files
        json_dir = Path(args.json_dir)
        output_dir = Path(args.output_dir)
        process_directory(json_dir, output_dir, args.pretty)


if __name__ == "__main__":
    main()