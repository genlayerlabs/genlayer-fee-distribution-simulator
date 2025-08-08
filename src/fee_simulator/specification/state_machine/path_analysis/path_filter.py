#!/usr/bin/env python3
"""
Path filter that applies the ADDRESS_ALLOCATION_ALGORITHM constraints.

This module filters theoretical paths from TRANSITIONS_GRAPH to only include
paths that are achievable with the 1,000 validator pool constraint.
"""

from typing import List, Set, Dict, Tuple, Optional
from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    Path,
    NodeName,
)
from src.fee_simulator.protocol.constants import NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES


class AddressAllocationState:
    """Tracks the state of address allocation as we process a path."""

    def __init__(self, max_addresses: int = 1000):
        self.max_addresses = max_addresses
        self.cumulative_active: Set[int] = set()
        self.next_unused_idx: int = 0
        self.previous_leaders: List[int] = []
        self.removed_addresses: Set[int] = set()
        self.normal_count: int = 0
        self.appeal_count: int = 0

    def get_available_count(self) -> int:
        """Get the number of addresses that haven't been used yet."""
        return self.max_addresses - self.next_unused_idx

    def copy(self) -> "AddressAllocationState":
        """Create a deep copy of the current state."""
        new_state = AddressAllocationState(self.max_addresses)
        new_state.cumulative_active = self.cumulative_active.copy()
        new_state.next_unused_idx = self.next_unused_idx
        new_state.previous_leaders = self.previous_leaders.copy()
        new_state.removed_addresses = self.removed_addresses.copy()
        new_state.normal_count = self.normal_count
        new_state.appeal_count = self.appeal_count
        return new_state


def is_normal_round(node: NodeName) -> bool:
    """Check if a node represents a normal round (not appeal)."""
    return "APPEAL" not in node and node not in ["START", "END"]


def is_appeal_round(node: NodeName) -> bool:
    """Check if a node represents an appeal round."""
    return "APPEAL" in node


def is_unsuccessful_appeal(node: NodeName) -> bool:
    """Check if a node represents an unsuccessful appeal."""
    return "APPEAL" in node and "UNSUCCESSFUL" in node


def get_normal_round_size(state: AddressAllocationState) -> int:
    """Get the size for the next normal round based on normal round count."""
    # Normal rounds use their own counter, not blockchain index
    round_idx = state.normal_count
    return NORMAL_ROUND_SIZES[min(round_idx, len(NORMAL_ROUND_SIZES) - 1)]


def get_appeal_round_size(
    state: AddressAllocationState, prev_was_unsuccessful: bool
) -> int:
    """Get the size for the next appeal round."""
    base_idx = state.appeal_count
    base_size = APPEAL_ROUND_SIZES[min(base_idx, len(APPEAL_ROUND_SIZES) - 1)]

    # Reduce by 2 if previous was unsuccessful appeal
    return base_size - 2 if prev_was_unsuccessful else base_size


def simulate_normal_round(state: AddressAllocationState) -> Optional[int]:
    """
    Simulate address allocation for a normal round.
    Returns the number of addresses needed, or None if impossible.
    """
    required_size = get_normal_round_size(state)

    if state.normal_count == 0:
        # First normal round - need new addresses
        if state.get_available_count() < required_size:
            return None
        return required_size
    else:
        # Subsequent normal rounds - reuse cumulative minus leaders
        available = (
            state.cumulative_active
            - set(state.previous_leaders)
            - state.removed_addresses
        )
        available_count = len(available)

        if available_count >= required_size:
            # We have enough from cumulative
            return 0  # No new addresses needed
        else:
            # Need to pull new addresses
            needed = required_size - available_count
            if state.get_available_count() < needed:
                return None
            return needed


def simulate_appeal_round(
    state: AddressAllocationState, prev_was_unsuccessful: bool
) -> Optional[int]:
    """
    Simulate address allocation for an appeal round.
    Returns the number of new addresses needed, or None if impossible.
    """
    required_size = get_appeal_round_size(state, prev_was_unsuccessful)

    # Appeals always use new addresses
    if state.get_available_count() < required_size:
        return None
    return required_size


def apply_round_to_state(
    state: AddressAllocationState, node: NodeName, prev_node: Optional[NodeName]
) -> bool:
    """
    Apply a round to the state, updating it in place.
    Returns True if successful, False if the round would exceed address limits.
    """
    if node in ["START", "END"]:
        return True

    prev_was_unsuccessful = prev_node and is_unsuccessful_appeal(prev_node)

    if is_normal_round(node):
        new_addresses_needed = simulate_normal_round(state)
        if new_addresses_needed is None:
            return False

        # Update state for normal round
        round_size = get_normal_round_size(state)

        if state.normal_count == 0:
            # First round - all new addresses
            new_indices = set(
                range(state.next_unused_idx, state.next_unused_idx + round_size)
            )
            state.next_unused_idx += round_size
        else:
            # Reuse cumulative minus leaders
            available = list(
                state.cumulative_active
                - set(state.previous_leaders)
                - state.removed_addresses
            )
            available.sort()

            if len(available) >= round_size:
                new_indices = set(available[:round_size])
            else:
                # Use all available plus new ones
                new_indices = set(available)
                needed = round_size - len(available)
                for _ in range(needed):
                    new_indices.add(state.next_unused_idx)
                    state.next_unused_idx += 1

        # Update cumulative active set
        state.cumulative_active.update(new_indices)

        # Record leader (first address in the round)
        leader = min(new_indices)
        state.previous_leaders.append(leader)

        state.normal_count += 1

    else:  # Appeal round
        new_addresses_needed = simulate_appeal_round(state, prev_was_unsuccessful)
        if new_addresses_needed is None:
            return False

        # Update state for appeal round
        round_size = get_appeal_round_size(state, prev_was_unsuccessful)

        # Appeals always use new addresses
        new_indices = set(
            range(state.next_unused_idx, state.next_unused_idx + round_size)
        )
        state.next_unused_idx += round_size

        # Update cumulative active set
        state.cumulative_active.update(new_indices)

        state.appeal_count += 1

    return True


def is_valid_path(path: Path, max_addresses: int = 1000) -> bool:
    """
    Check if a path is valid under the address allocation constraints.

    Args:
        path: The path to validate
        max_addresses: Maximum number of available addresses (default 1000)

    Returns:
        True if the path is achievable within address constraints, False otherwise
    """
    state = AddressAllocationState(max_addresses)

    prev_node = None
    for node in path:
        if not apply_round_to_state(state, node, prev_node):
            return False
        prev_node = node

    return True


def filter_valid_paths(paths: List[Path], max_addresses: int = 1000) -> List[Path]:
    """
    Filter a list of paths to only include those achievable with address constraints.

    Args:
        paths: List of paths to filter
        max_addresses: Maximum number of available addresses (default 1000)

    Returns:
        List of valid paths that can be achieved within address constraints
    """
    return [path for path in paths if is_valid_path(path, max_addresses)]


def get_path_statistics(
    path: Path, max_addresses: int = 1000
) -> Optional[Dict[str, any]]:
    """
    Get detailed statistics about address allocation for a path.

    Args:
        path: The path to analyze
        max_addresses: Maximum number of available addresses

    Returns:
        Dictionary with statistics if path is valid, None otherwise
    """
    state = AddressAllocationState(max_addresses)

    round_details = []
    prev_node = None

    for i, node in enumerate(path):
        if node in ["START", "END"]:
            prev_node = node
            continue

        # Get state before applying
        addresses_before = state.next_unused_idx

        if not apply_round_to_state(state, node, prev_node):
            return None

        # Calculate what happened
        addresses_after = state.next_unused_idx
        new_addresses_used = addresses_after - addresses_before

        if is_normal_round(node):
            # Create a state with correct normal_count for size calculation
            temp_state = AddressAllocationState(max_addresses)
            temp_state.normal_count = sum(
                1 for detail in round_details if detail["type"] == "normal"
            )
            round_size = get_normal_round_size(temp_state)
            round_type = "normal"
        else:
            prev_unsuccessful = prev_node and is_unsuccessful_appeal(prev_node)
            # Create a state with correct appeal_count for size calculation
            temp_state = AddressAllocationState(max_addresses)
            temp_state.appeal_count = sum(
                1 for detail in round_details if detail["type"] == "appeal"
            )
            round_size = get_appeal_round_size(temp_state, prev_unsuccessful)
            round_type = "appeal"

        round_details.append(
            {
                "index": i,
                "node": node,
                "type": round_type,
                "size": round_size,
                "new_addresses": new_addresses_used,
                "total_used": state.next_unused_idx,
                "is_unsuccessful": (
                    is_unsuccessful_appeal(node) if round_type == "appeal" else None
                ),
            }
        )

        prev_node = node

    return {
        "path": path,
        "total_addresses_used": state.next_unused_idx,
        "addresses_remaining": max_addresses - state.next_unused_idx,
        "normal_rounds": state.normal_count,
        "appeal_rounds": state.appeal_count,
        "round_details": round_details,
        "is_valid": True,
    }


def find_max_appeal_chain_length(max_addresses: int = 1000) -> int:
    """
    Find the maximum number of consecutive unsuccessful appeals possible.

    This helps understand the theoretical limits of the system.
    """
    # Start with a normal round
    state = AddressAllocationState(max_addresses)

    # First normal round
    if not apply_round_to_state(state, "LEADER_RECEIPT_MAJORITY_AGREE", None):
        return 0

    # Now try consecutive unsuccessful appeals
    appeal_count = 0
    prev_node = "LEADER_RECEIPT_MAJORITY_AGREE"

    while True:
        node = "VALIDATOR_APPEAL_UNSUCCESSFUL"
        if not apply_round_to_state(state, node, prev_node):
            break
        appeal_count += 1
        prev_node = node

    return appeal_count


def analyze_path_distribution(
    paths: List[Path], max_addresses: int = 1000
) -> Dict[str, any]:
    """
    Analyze the distribution of valid vs invalid paths.

    Returns statistics about path filtering.
    """
    total_paths = len(paths)
    valid_paths = []
    invalid_paths = []

    # Statistics by length
    valid_by_length = {}
    invalid_by_length = {}

    # Address usage statistics
    address_usage_stats = []

    for path in paths:
        path_length = len(path) - 1  # Edges, not nodes

        if is_valid_path(path, max_addresses):
            valid_paths.append(path)
            valid_by_length[path_length] = valid_by_length.get(path_length, 0) + 1

            # Get detailed stats for valid paths
            stats = get_path_statistics(path, max_addresses)
            if stats:
                address_usage_stats.append(stats["total_addresses_used"])
        else:
            invalid_paths.append(path)
            invalid_by_length[path_length] = invalid_by_length.get(path_length, 0) + 1

    # Calculate statistics
    if address_usage_stats:
        avg_addresses = sum(address_usage_stats) / len(address_usage_stats)
        max_addresses_used = max(address_usage_stats)
        min_addresses_used = min(address_usage_stats)
    else:
        avg_addresses = max_addresses_used = min_addresses_used = 0

    return {
        "total_paths": total_paths,
        "valid_paths": len(valid_paths),
        "invalid_paths": len(invalid_paths),
        "validity_rate": len(valid_paths) / total_paths if total_paths > 0 else 0,
        "valid_by_length": dict(sorted(valid_by_length.items())),
        "invalid_by_length": dict(sorted(invalid_by_length.items())),
        "address_usage": {
            "average": avg_addresses,
            "max": max_addresses_used,
            "min": min_addresses_used,
        },
        "max_appeal_chain": find_max_appeal_chain_length(max_addresses),
    }


if __name__ == "__main__":
    # Example usage and testing
    print("Path Filter - Address Allocation Algorithm")
    print("=" * 50)

    # Test some example paths
    test_paths = [
        # Simple path
        ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"],
        # Path with appeal
        [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "END",
        ],
        # Path with consecutive unsuccessful appeals
        ["START", "LEADER_RECEIPT_MAJORITY_AGREE"]
        + ["VALIDATOR_APPEAL_UNSUCCESSFUL"] * 3
        + ["VALIDATOR_APPEAL_SUCCESSFUL", "END"],
        # Very long appeal chain (should fail)
        ["START", "LEADER_RECEIPT_MAJORITY_AGREE"]
        + ["VALIDATOR_APPEAL_UNSUCCESSFUL"] * 10
        + ["END"],
    ]

    for i, path in enumerate(test_paths):
        print(f"\nTest Path {i+1}:")
        print(f"Length: {len(path)-1} edges")
        print(f"Valid: {is_valid_path(path)}")

        stats = get_path_statistics(path)
        if stats:
            print(f"Total addresses used: {stats['total_addresses_used']}")
            print(f"Addresses remaining: {stats['addresses_remaining']}")

    # Find theoretical limits
    print(f"\n\nTheoretical Limits:")
    print(f"Maximum consecutive unsuccessful appeals: {find_max_appeal_chain_length()}")
