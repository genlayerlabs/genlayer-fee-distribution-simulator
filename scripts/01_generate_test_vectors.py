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
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

# Add parent directory to path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fee_simulator.specification.state_machine.graph import TRANSACTION_GRAPH
from src.fee_simulator.specification.state_machine.path_analysis.path_generator import (
    generate_all_paths,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    PathConstraints,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_filter import (
    filter_valid_paths,
)
from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.utils import generate_random_eth_address

# Constants
LEADER_TIMEOUT = 100
VALIDATORS_TIMEOUT = 200

# Rich Console
console = Console()

# --- Lookup Tables ---
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
ROLE_TO_IDX = {"LEADER": 0, "VALIDATOR": 1, "SENDER": 2, "APPEALANT": 3}
INVARIANT_BITS = {
    "conservation_of_value": 0,
    "appeal_bond_coverage": 1,
    "majority_minority_consistency": 2,
    "sequential_processing": 3,
    "appeal_follows_normal": 4,
    "round_label_validity": 5,
    "appellant_consistency": 6,
    "burn_non_negativity": 7,
    "no_double_penalties": 8,
    "bounded_slashing_impact": 9,
    "no_profit_from_griefing": 10,
    "cost_of_contention": 11,
    "griefing_amplification": 12,
    "progress_monotonicity": 13,
    "resource_pool_integrity": 14,
    "irreversibility_of_finality": 15,
    "temporal_event_consistency": 16,
    "refund_non_negativity": 17,
    "vote_consistency": 18,
    "idle_slashing": 19,
    "deterministic_violation_slashing": 20,
    "leader_timeout_earning": 21,
    "appeal_bond_consistency": 22,
    "round_size_consistency": 23,
}


# --- Helper Functions ---
def hash_path(path: List[str]) -> str:
    path_str = "-".join(path)
    return hashlib.sha256(path_str.encode()).hexdigest()


def get_address_index(address: str, address_map: Dict[str, int]) -> int:
    if address not in address_map:
        address_map[address] = len(address_map) + 1
    return address_map[address]


def check_invariants(
    fee_events, transaction_budget, transaction_results, round_labels
) -> int:
    from src.fee_simulator.specification.invariants.checker import (
        check_all_invariants,
    )

    num_rounds = len(round_labels)
    split_rounds = sum(
        1
        for label in round_labels
        if label
        in [
            "NORMAL_ROUND",
            "SPLIT_PREVIOUS_APPEAL_BOND",
            "APPEAL_VALIDATOR_SUCCESSFUL",
            "APPEAL_VALIDATOR_UNSUCCESSFUL",
            "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
        ]
    )
    tolerance = split_rounds * 200 + num_rounds * 2

    check_all_invariants(
        fee_events,
        transaction_budget,
        transaction_results,
        round_labels,
        tolerance=tolerance,
    )
    return (1 << len(INVARIANT_BITS)) - 1


def process_path(path: List[str], addresses: List[str]) -> Tuple[Dict[str, Any], Tuple]:
    sender_address = addresses[-1]
    appealant_address = addresses[-2]
    transaction_results, transaction_budget = path_to_transaction_results(
        path=path,
        addresses=addresses,
        sender_address=sender_address,
        appealant_address=appealant_address,
        leader_timeout=LEADER_TIMEOUT,
        validators_timeout=VALIDATORS_TIMEOUT,
    )
    round_labels = label_rounds(transaction_results)
    fee_events, _ = process_transaction(
        addresses=addresses,
        transaction_results=transaction_results,
        transaction_budget=transaction_budget,
    )
    address_map = {}
    participants = defaultdict(lambda: {"r": [], "c": 0, "e": 0, "s": 0, "b": 0})
    for event in fee_events:
        if event.address:
            addr_idx = get_address_index(event.address, address_map)
            if event.round_index is not None and event.role:
                role_idx = ROLE_TO_IDX.get(event.role, -1)
                if role_idx >= 0:
                    participants[addr_idx]["r"].append([event.round_index, role_idx])
            participants[addr_idx]["c"] += event.cost
            participants[addr_idx]["e"] += event.earned
            participants[addr_idx]["s"] += event.slashed
            participants[addr_idx]["b"] += event.burned
    active_participants = {
        k: v for k, v in participants.items() if v["c"] or v["e"] or v["s"] or v["b"]
    }
    path_indices = [NODE_TO_IDX[node] for node in path]
    label_indices = [LABEL_TO_IDX.get(label, -1) for label in round_labels]
    result_data = {
        "path": path_indices,
        "labels": label_indices,
        "participants": active_participants,
        "hash": hash_path(path),
    }
    invariant_data = (fee_events, transaction_budget, transaction_results, round_labels)
    return result_data, invariant_data


def generate_filename(path: List[str]) -> str:
    path_length = len(path) - 2
    path_hash = hash_path(path)[:8]
    return f"{path_length:02d}-{path_hash}.json"


def save_lookup_tables(output_dir: Path):
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
    console.print(f"[green]Saved lookup tables to[/green] {lookup_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate JSON files for fee distribution paths"
    )
    parser.add_argument(
        "--output-dir", type=str, default="path_jsons", help="Output directory"
    )
    parser.add_argument("--max-length", type=int, default=16, help="Max path length")
    parser.add_argument(
        "--test-mode", action="store_true", help="Run with limited paths"
    )
    parser.add_argument("--debug", action="store_true", help="Show detailed error info")
    parser.add_argument("--no-filter", action="store_true", help="Process all paths")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    save_lookup_tables(output_dir)

    addresses = [generate_random_eth_address() for _ in range(1000)]
    processed, errors = 0, 0

    console.rule("[bold cyan]Path Generation Setup[/bold cyan]")
    console.print(f"Generating paths up to length [bold]{args.max_length}[/bold]...")
    if not args.no_filter:
        console.print(
            "[yellow]Filtering enabled[/yellow]: Only processing paths valid with 1000 validators"
        )

    # --- Path Counting ---
    total_paths, total_valid_paths = 0, 0
    console.print("[bold]Counting total paths...[/bold]")
    count_table = Table(title="Path Counts by Length")
    count_table.add_column("Length", justify="right")
    count_table.add_column("Valid Paths", justify="right")
    count_table.add_column("Total Paths", justify="right")
    count_table.add_column("Validity Rate", justify="right")

    for length in range(3, args.max_length + 1):
        constraints = PathConstraints(
            source_node="START", target_node="END", min_length=length, max_length=length
        )
        all_paths = list(generate_all_paths(TRANSACTION_GRAPH, constraints))
        path_count = len(all_paths)
        valid_count = (
            len(filter_valid_paths(all_paths, max_addresses=1000))
            if not args.no_filter
            else path_count
        )
        total_paths += path_count
        total_valid_paths += valid_count
        rate = f"{(valid_count/path_count*100):.1f}%" if path_count > 0 else "N/A"
        count_table.add_row(str(length), f"{valid_count:,}", f"{path_count:,}", rate)

    console.print(count_table)
    paths_to_process_count = total_valid_paths if not args.no_filter else total_paths
    console.print(
        f"\n[bold]Total paths to process: [cyan]{paths_to_process_count:,}[/cyan][/bold]"
    )
    console.rule("[bold cyan]Processing Paths[/bold cyan]")

    # --- Path Processing ---
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=paths_to_process_count)

        for length in range(3, args.max_length + 1):
            length_dir = output_dir / f"length_{length:02d}"
            length_dir.mkdir(exist_ok=True)
            length_count = 0

            constraints = PathConstraints(
                source_node="START",
                target_node="END",
                min_length=length,
                max_length=length,
            )
            all_paths = list(generate_all_paths(TRANSACTION_GRAPH, constraints))
            paths_to_process = (
                filter_valid_paths(all_paths, max_addresses=1000)
                if not args.no_filter
                else all_paths
            )

            if not paths_to_process:
                continue

            for path in paths_to_process:
                if args.test_mode and length_count >= 10:
                    break

                invariant_exception = None
                try:
                    result_data, invariant_data = process_path(path, addresses)
                    filename = generate_filename(path)
                    filepath = length_dir / filename

                    try:
                        invariant_bitfield = check_invariants(*invariant_data)
                    except Exception as e:
                        invariant_bitfield = 0
                        invariant_exception = e

                    result_data["invariants"] = invariant_bitfield
                    with open(filepath, "w") as f:
                        json.dump(result_data, f, separators=(",", ":"))

                    if invariant_exception:
                        errors += 1
                        error_text = Text(
                            f"\nError processing path {' -> '.join(path)}: {invariant_exception}"
                        )
                        error_text.stylize("bold red")
                        console.print(error_text)
                        console.print(
                            f"  -> [bold]Check generated file for details:[/] {filepath}"
                        )
                        if args.debug:
                            console.print_exception(show_locals=True)

                    processed += 1
                    length_count += 1
                except Exception as e:
                    errors += 1
                    filename = generate_filename(path)
                    filepath = length_dir / filename
                    console.print(
                        f"\n[bold red]Critical error processing path {path}: {e}[/bold red]"
                    )
                    console.print(
                        f"  -> [bold]Check generated file for details:[/] {filepath}"
                    )
                    if args.debug:
                        console.print_exception(show_locals=True)

                progress.update(task, advance=1)

            if args.test_mode:
                break

    # --- Final Summary ---
    console.rule("[bold cyan]Completion Summary[/bold cyan]")
    summary_table = Table(show_header=False, box=None)
    summary_table.add_row(
        "Total Paths Processed:", f"[bold green]{processed:,}[/bold green]"
    )
    summary_table.add_row(
        "Errors Encountered:",
        (
            f"[bold red]{errors:,}[/bold red]"
            if errors > 0
            else "[bold green]0[/bold green]"
        ),
    )
    console.print(summary_table)

    if not args.no_filter:
        filter_table = Table(title="Filtering Summary", box=None)
        filter_table.add_column("Metric", justify="right")
        filter_table.add_column("Value", justify="left")
        filter_table.add_row("Theoretical Paths:", f"{total_paths:,}")
        filter_table.add_row(
            "Valid Paths (1000 validator limit):", f"{total_valid_paths:,}"
        )
        filter_table.add_row(
            "Paths Filtered Out:", f"{total_paths - total_valid_paths:,}"
        )
        filter_table.add_row(
            "Validity Rate:", f"{(total_valid_paths/total_paths*100):.1f}%"
        )
        console.print(filter_table)


if __name__ == "__main__":
    main()
