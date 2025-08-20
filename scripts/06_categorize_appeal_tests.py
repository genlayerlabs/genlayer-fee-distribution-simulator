#!/usr/bin/env python3
"""
Categorize and compress length_03 Solidity test JSONs by appeal type.

This script reads the Solidity test JSONs for length_03 paths and categorizes
them into different appeal types, creating compressed summary files for each category.
"""

import json
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

# Add parent directory to path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


def categorize_path(path: List[str]) -> str:
    """
    Categorize a path based on the appeal type present.
    
    Returns one of:
    - validator_appeal_successful
    - validator_appeal_unsuccessful
    - leader_appeal_successful
    - leader_appeal_unsuccessful
    - leader_timeout_appeal_successful
    - leader_timeout_appeal_unsuccessful
    - other
    """
    path_str = " -> ".join(path)
    
    if "VALIDATOR_APPEAL_SUCCESSFUL" in path_str:
        return "validator_appeal_successful"
    elif "VALIDATOR_APPEAL_UNSUCCESSFUL" in path_str:
        return "validator_appeal_unsuccessful"
    elif "LEADER_APPEAL_SUCCESSFUL" in path_str:
        return "leader_appeal_successful"
    elif "LEADER_APPEAL_UNSUCCESSFUL" in path_str:
        return "leader_appeal_unsuccessful"
    elif "LEADER_APPEAL_TIMEOUT_SUCCESSFUL" in path_str:
        return "leader_timeout_appeal_successful"
    elif "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL" in path_str:
        return "leader_timeout_appeal_unsuccessful"
    else:
        return "other"


def simplify_addresses(data: Any, address_map: Dict[str, str] = None) -> Any:
    """
    Recursively replace hex addresses with simple validator names.
    """
    if address_map is None:
        address_map = {}
    
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            if key == "address" and isinstance(value, str) and value.startswith("0x"):
                # Replace hex address with validator name
                if value not in address_map:
                    if "sender" in str(data) or value == data.get("sender"):
                        address_map[value] = "sender"
                    else:
                        validator_num = len([k for k in address_map.keys() if address_map[k].startswith("validator")]) + 1
                        address_map[value] = f"validator{validator_num}"
                new_dict[key] = address_map[value]
            elif key == "leader" and isinstance(value, str) and value.startswith("0x"):
                # Handle leader field
                if value not in address_map:
                    validator_num = len([k for k in address_map.keys() if address_map[k].startswith("validator")]) + 1
                    address_map[value] = f"validator{validator_num}"
                new_dict[key] = address_map[value]
            elif key == "sender" and isinstance(value, str) and value.startswith("0x"):
                # Handle sender field
                if value not in address_map:
                    address_map[value] = "sender"
                new_dict[key] = address_map[value]
            else:
                new_dict[key] = simplify_addresses(value, address_map)
        return new_dict
    elif isinstance(data, list):
        return [simplify_addresses(item, address_map) for item in data]
    else:
        return data


def compress_test_cases(test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compress multiple test cases into a summary format.
    
    Groups test cases by similar patterns and provides statistics.
    """
    compressed = {
        "category": "",
        "total_cases": len(test_cases),
        "patterns": defaultdict(lambda: {
            "count": 0,
            "examples": [],
            "summary": {
                "rewards": 0,
                "penalties": 0,
                "sender_outcomes": 0
            }
        })
    }
    
    for test_case in test_cases:
        # Simplify addresses in the test case
        simplified_case = simplify_addresses(test_case)
        
        # Extract pattern key from description
        description = simplified_case["description"]
        pattern_key = description.replace("Test Case: ", "")
        
        pattern_data = compressed["patterns"][pattern_key]
        pattern_data["count"] += 1
        
        # Add example if we have less than 3
        if len(pattern_data["examples"]) < 3:
            pattern_data["examples"].append(simplified_case)
        
        # Track totals for summary
        total_rewards = sum(int(r["amount"]) for r in simplified_case["expectedState"]["rewards"])
        total_penalties = sum(int(p["amount"]) for p in simplified_case["expectedState"]["penalties"])
        sender_outcome = int(simplified_case["expectedState"]["sender_outcome"]["net_change"])
        
        # Since each pattern appears only once in length_03, we can just set the values
        pattern_data["summary"]["rewards"] = total_rewards
        pattern_data["summary"]["penalties"] = total_penalties
        pattern_data["summary"]["sender_outcomes"] = sender_outcome
    
    # Convert defaultdicts to regular dicts for JSON serialization
    compressed["patterns"] = dict(compressed["patterns"])
    
    return compressed


def create_category_summary(category: str, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a comprehensive summary for a category of test cases.
    """
    # Simplify addresses in all test cases
    simplified_cases = [simplify_addresses(tc) for tc in test_cases]
    
    summary = {
        "category": category,
        "total_test_cases": len(simplified_cases),
        "unique_patterns": len(set(tc["description"] for tc in simplified_cases)),
        "test_cases": simplified_cases,
        "statistics": {
            "average_validators": 0,
            "total_rewards_distributed": 0,
            "total_penalties_applied": 0,
            "sender_net_changes": {
                "positive": 0,
                "negative": 0,
                "neutral": 0
            }
        }
    }
    
    # Calculate statistics
    total_validators = 0
    total_rewards = 0
    total_penalties = 0
    
    for test_case in simplified_cases:
        # Count validators
        total_validators += len(test_case["initialState"]["validators"])
        
        # Sum rewards
        for reward in test_case["expectedState"]["rewards"]:
            total_rewards += int(reward["amount"])
        
        # Sum penalties
        for penalty in test_case["expectedState"]["penalties"]:
            total_penalties += int(penalty["amount"])
        
        # Track sender outcomes
        net_change = int(test_case["expectedState"]["sender_outcome"]["net_change"])
        if net_change > 0:
            summary["statistics"]["sender_net_changes"]["positive"] += 1
        elif net_change < 0:
            summary["statistics"]["sender_net_changes"]["negative"] += 1
        else:
            summary["statistics"]["sender_net_changes"]["neutral"] += 1
    
    summary["statistics"]["average_validators"] = total_validators / len(simplified_cases) if simplified_cases else 0
    summary["statistics"]["total_rewards_distributed"] = total_rewards
    summary["statistics"]["total_penalties_applied"] = total_penalties
    
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Categorize and compress length_03 appeal test cases",
        epilog="Example:\n"
        "  python 05_categorize_appeal_tests.py --input-dir solidity_test_jsons/length_03 --output-dir categorized_tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="solidity_test_jsons/length_03",
        help="Input directory containing Solidity test JSONs (default: solidity_test_jsons/length_03)"
    )
    parser.add_argument(
        "--path-jsons-dir",
        type=str,
        default="path_jsons",
        help="Directory containing original path JSONs with lookup tables (default: path_jsons)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="categorized_appeal_tests",
        help="Output directory for categorized tests (default: categorized_appeal_tests)"
    )
    parser.add_argument(
        "--compressed",
        action="store_true",
        help="Generate compressed summaries instead of full test cases"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print the JSON output"
    )
    
    args = parser.parse_args()
    
    # Load lookup tables
    path_jsons_dir = Path(args.path_jsons_dir)
    lookup_tables = load_lookup_tables(path_jsons_dir)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Categories to process
    categories = {
        "validator_appeal_successful": [],
        "validator_appeal_unsuccessful": [],
        "leader_appeal_successful": [],
        "leader_appeal_unsuccessful": [],
        "leader_timeout_appeal_successful": [],
        "leader_timeout_appeal_unsuccessful": []
    }
    
    # Process each Solidity test JSON
    input_dir = Path(args.input_dir)
    
    for json_file in sorted(input_dir.glob("*.json")):
        # Load the Solidity test JSON
        with open(json_file, "r") as f:
            test_cases = json.load(f)
        
        # Get the corresponding original path JSON to determine category
        # Extract the original file name (remove _solidity suffix)
        original_name = json_file.stem.replace("_solidity", "")
        original_path_file = path_jsons_dir / "length_03" / f"{original_name}.json"
        
        if original_path_file.exists():
            with open(original_path_file, "r") as f:
                compressed_data = json.load(f)
            
            # Decode and categorize the path
            path = decode_path(compressed_data, lookup_tables)
            category = categorize_path(path)
            
            # Add test cases to appropriate category
            if category in categories:
                categories[category].extend(test_cases)
                print(f"Added {json_file.name} to {category}")
    
    # Generate output for each category
    for category_name, test_cases in categories.items():
        if not test_cases:
            print(f"No test cases found for {category_name}")
            continue
        
        if args.compressed:
            # Generate compressed summary
            output_data = compress_test_cases(test_cases)
            output_data["category"] = category_name
            output_file = output_dir / f"{category_name}_compressed.json"
        else:
            # Generate full category summary
            output_data = create_category_summary(category_name, test_cases)
            output_file = output_dir / f"{category_name}.json"
        
        # Save to file
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=4 if args.pretty else None)
        
        print(f"Created {output_file} with {len(test_cases)} test cases")
    
    # Create a combined summary file
    summary = {
        "total_test_cases": sum(len(tc) for tc in categories.values()),
        "categories": {}
    }
    
    for category_name, test_cases in categories.items():
        if test_cases:
            summary["categories"][category_name] = {
                "count": len(test_cases),
                "unique_patterns": len(set(tc["description"] for tc in test_cases))
            }
    
    summary_file = output_dir / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=4 if args.pretty else None)
    
    print(f"\nSummary saved to {summary_file}")
    print(f"Total categorized test cases: {summary['total_test_cases']}")


if __name__ == "__main__":
    main()