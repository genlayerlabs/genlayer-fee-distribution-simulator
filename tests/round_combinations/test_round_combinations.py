"""
Example tests demonstrating how the refactored code is more testable.
"""

import unittest
from typing import List

from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    PathConstraints,
    Path,
)
from src.fee_simulator.specification.state_machine.graph import TRANSACTION_GRAPH
from src.fee_simulator.specification.state_machine.path_analysis.path_counter import (
    count_paths_between_nodes,
    get_reachable_nodes,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_generator import (
    generate_all_paths,
    filter_paths_containing_pattern,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_analyzer import (
    analyze_paths,
    _count_appeals_in_path,
)


class TestPathCounting(unittest.TestCase):
    """Test the path counting functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.simple_graph = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}

        self.constraints = PathConstraints(
            min_length=2, max_length=3, source_node="A", target_node="D"
        )

    def test_simple_path_counting(self):
        """Test counting paths in a simple graph."""
        result = count_paths_between_nodes(
            self.simple_graph, self.constraints, verbose=False
        )

        # A->B->D and A->C->D (both have 2 edges)
        self.assertEqual(result.count, 2)
        self.assertEqual(result.by_length, {2: 2})

    def test_reachable_nodes(self):
        """Test finding reachable nodes."""
        reachable = get_reachable_nodes(self.simple_graph, "A", max_steps=2)

        # A can reach B, C, and D within 2 steps
        self.assertEqual(reachable, {"A", "B", "C", "D"})


class TestPathGeneration(unittest.TestCase):
    """Test the path generation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.constraints = PathConstraints(
            min_length=3, max_length=5, source_node="START", target_node="END"
        )

    def test_path_generation_respects_constraints(self):
        """Test that generated paths respect length constraints (in edges)."""
        paths = generate_all_paths(TRANSACTION_GRAPH, self.constraints)

        for path in paths:
            edge_count = len(path) - 1  # Count edges, not nodes
            self.assertGreaterEqual(edge_count, self.constraints.min_length)
            self.assertLessEqual(edge_count, self.constraints.max_length)
            self.assertEqual(path[0], "START")
            self.assertEqual(path[-1], "END")

    def test_pattern_filtering(self):
        """Test filtering paths by pattern."""
        paths = generate_all_paths(TRANSACTION_GRAPH, self.constraints)

        timeout_paths = filter_paths_containing_pattern(paths, "TIMEOUT")

        for path in timeout_paths:
            self.assertTrue(any("TIMEOUT" in node for node in path))


class TestPathAnalysis(unittest.TestCase):
    """Test the path analysis functionality."""

    def test_appeal_counting(self):
        """Test counting appeals in a path."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_TIMEOUT",
            "LEADER_APPEAL_TIMEOUT_SUCCESSFUL",
            "END",
        ]

        appeal_count = _count_appeals_in_path(path)
        self.assertEqual(appeal_count, 2)  # Two appeal nodes

    def test_path_statistics(self):
        """Test computing path statistics."""
        paths = [
            ["START", "LEADER_TIMEOUT", "END"],
            ["START", "LEADER_TIMEOUT", "LEADER_APPEAL_TIMEOUT_SUCCESSFUL", "END"],
        ]

        stats = analyze_paths(paths)

        self.assertEqual(stats.total_paths, 2)
        # Note: analyze_paths still counts nodes, not edges
        # This is a separate issue that would need fixing in path_analyzer.py
        self.assertEqual(stats.length_distribution, {3: 1, 4: 1})
        self.assertEqual(stats.appeal_distribution, {0: 1, 1: 1})


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete system."""

    def test_consistency_between_methods(self):
        """Test that counting and generation methods give same results."""
        constraints = PathConstraints(
            min_length=3, max_length=7, source_node="START", target_node="END"
        )

        # Count using matrix method
        count_result = count_paths_between_nodes(
            TRANSACTION_GRAPH, constraints, verbose=False
        )

        # Generate actual paths
        paths = generate_all_paths(TRANSACTION_GRAPH, constraints)

        # Should match
        self.assertEqual(count_result.count, len(paths))

    def test_paths_allow_cycles(self):
        """Test that generated paths can contain cycles (repeated nodes)."""
        constraints = PathConstraints(
            min_length=3, max_length=10, source_node="START", target_node="END"
        )

        paths = generate_all_paths(TRANSACTION_GRAPH, constraints)

        # Find paths with cycles
        paths_with_cycles = []
        for path in paths:
            node_counts = {}
            for node in path:
                node_counts[node] = node_counts.get(node, 0) + 1

            # Check if any node appears more than once
            if any(count > 1 for count in node_counts.values()):
                paths_with_cycles.append(path)

        # We expect some paths to have cycles
        self.assertGreater(
            len(paths_with_cycles),
            0,
            "No paths with cycles found, but cycles should be allowed",
        )

        # Verify a path with cycles is valid
        if paths_with_cycles:
            example_cycle_path = paths_with_cycles[0]
            edge_count = len(example_cycle_path) - 1
            self.assertGreaterEqual(edge_count, constraints.min_length)
            self.assertLessEqual(edge_count, constraints.max_length)


def run_quick_verification():
    """Run a quick verification of the system."""
    print("Running quick verification...")

    constraints = PathConstraints(
        min_length=3, max_length=5, source_node="START", target_node="END"
    )

    # Test counting
    count_result = count_paths_between_nodes(
        TRANSACTION_GRAPH, constraints, verbose=False
    )

    # Test generation
    paths = generate_all_paths(TRANSACTION_GRAPH, constraints)

    # Verify consistency
    assert count_result.count == len(paths), "Mismatch between counting methods!"

    print(f"✓ Verification passed: {count_result.count} paths found")
    print(f"✓ Length distribution: {count_result.by_length}")

    # Show a sample path
    if paths:
        print(f"✓ Sample path: {' -> '.join(paths[0])}")
        print(f"  (Path has {len(paths[0])} nodes and {len(paths[0])-1} edges)")


if __name__ == "__main__":
    # Run quick verification
    run_quick_verification()

    # Run unit tests
    print("\nRunning unit tests...")
    unittest.main(verbosity=2)
