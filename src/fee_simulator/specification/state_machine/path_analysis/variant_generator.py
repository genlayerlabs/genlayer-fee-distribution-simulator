"""
Variant generator for exhaustive combinatorial testing of rotations and idleness.

Expands base TRANSACTION_GRAPH paths into (path, rotation_counts, idle_config) tuples
by testing all valid combinations of rotations and idle validators per normal round.
"""

import hashlib
import itertools
from typing import Dict, Generator, List, NamedTuple, Optional, Tuple

from src.fee_simulator.specification.state_machine.graph import (
    GRAPH_NODE_METADATA,
)
from src.fee_simulator.core.path_to_transaction import is_appeal_node


class VariantConfig(NamedTuple):
    """A specific variant of a path with rotation and idleness parameters."""

    path: List[str]
    rotation_counts: Dict[int, int]
    idle_config: Dict[int, int]

    @property
    def variant_id(self) -> str:
        """Stable unique identifier for this variant."""
        parts = ["-".join(self.path)]
        if self.rotation_counts:
            rot_str = ",".join(
                f"{k}:{v}" for k, v in sorted(self.rotation_counts.items())
            )
            parts.append(f"rot={rot_str}")
        if self.idle_config:
            idle_str = ",".join(
                f"{k}:{v}" for k, v in sorted(self.idle_config.items())
            )
            parts.append(f"idle={idle_str}")
        combined = "|".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:12]


def get_normal_round_nodes(
    path: List[str],
) -> List[Tuple[int, str]]:
    """
    Extract normal round nodes with their 0-based normal round indices.

    Uses the same indexing convention as path_to_transaction.py: only counts
    non-appeal nodes (excluding START/END), indexed from 0.

    Returns:
        List of (normal_round_index, node_name) tuples.
    """
    normal_rounds = []
    normal_idx = 0
    for node in path[1:-1]:  # Skip START and END
        if not is_appeal_node(node):
            normal_rounds.append((normal_idx, node))
            normal_idx += 1
    return normal_rounds


def _get_node_ranges(
    node: str,
    max_rotations: int,
    max_idle: int,
) -> Tuple[range, range]:
    """
    Get the valid rotation and idle ranges for a graph node.

    Returns:
        (rotation_range, idle_range) for itertools.product
    """
    meta = GRAPH_NODE_METADATA.get(node, {"rotations": False, "idle": False})
    rot_range = range(0, max_rotations + 1) if meta["rotations"] else range(0, 1)
    idle_range = range(0, max_idle + 1) if meta["idle"] else range(0, 1)
    return rot_range, idle_range


def count_variants(
    path: List[str],
    max_rotations: int = 3,
    max_idle: int = 2,
) -> int:
    """
    Count the number of variants for a path without generating them.

    This is useful for progress display and estimating total work.
    """
    normal_rounds = get_normal_round_nodes(path)
    if not normal_rounds:
        return 1

    total = 1
    for _, node in normal_rounds:
        rot_range, idle_range = _get_node_ranges(node, max_rotations, max_idle)
        total *= len(rot_range) * len(idle_range)
    return total


def generate_variants(
    path: List[str],
    max_rotations: int = 3,
    max_idle: int = 2,
) -> Generator[VariantConfig, None, None]:
    """
    Generate all valid rotation/idle variants for a single path.

    For each normal round node, generates the Cartesian product of:
    - {0..max_rotations} if the node supports rotations
    - {0..max_idle} if the node supports idle validators

    Appeal nodes are not expanded (they have no rotations or idle).
    """
    normal_rounds = get_normal_round_nodes(path)

    if not normal_rounds:
        # Path with no normal rounds (shouldn't happen, but handle gracefully)
        yield VariantConfig(path=path, rotation_counts={}, idle_config={})
        return

    # Build per-round option lists
    round_options = []
    for _, node in normal_rounds:
        rot_range, idle_range = _get_node_ranges(node, max_rotations, max_idle)
        round_options.append(list(itertools.product(rot_range, idle_range)))

    # Cartesian product across all normal rounds
    for combo in itertools.product(*round_options):
        rotation_counts = {}
        idle_config = {}
        for round_idx_pos, (rot, idle) in enumerate(combo):
            normal_round_idx = normal_rounds[round_idx_pos][0]
            if rot > 0:
                rotation_counts[normal_round_idx] = rot
            if idle > 0:
                idle_config[normal_round_idx] = idle

        yield VariantConfig(
            path=path,
            rotation_counts=rotation_counts,
            idle_config=idle_config,
        )


def generate_all_path_variants(
    paths: List[List[str]],
    max_rotations: int = 3,
    max_idle: int = 2,
) -> Generator[VariantConfig, None, None]:
    """
    Batch expansion of multiple paths into variants (lazy generator).

    Args:
        paths: List of TRANSACTION_GRAPH paths.
        max_rotations: Maximum number of leader timeout rotations per normal round.
        max_idle: Maximum number of idle validators per normal round.

    Yields:
        VariantConfig for each valid combination.
    """
    for path in paths:
        yield from generate_variants(path, max_rotations, max_idle)


def count_all_path_variants(
    paths: List[List[str]],
    max_rotations: int = 3,
    max_idle: int = 2,
) -> int:
    """Count total variants across all paths without generating them."""
    return sum(count_variants(p, max_rotations, max_idle) for p in paths)
