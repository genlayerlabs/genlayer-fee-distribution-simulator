"""
Display and formatting utilities for path analysis results.

This module handles all presentation concerns, keeping them separate
from the business logic.
"""

from typing import List, Dict, Optional, Tuple

from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    Path,
    PathStatistics,
    CountingResult,
    SPECIAL_NODES,
)


class PathFormatter:
    """Responsible for formatting paths in various ways."""

    @staticmethod
    def format_path(path: Path, max_width: Optional[int] = None) -> str:
        """
        Format a path as a string with arrows.

        Args:
            path: The path to format
            max_width: Optional maximum width (truncates if needed)
        """
        formatted = " -> ".join(path)

        if max_width and len(formatted) > max_width:
            # Truncate in the middle
            half = (max_width - 5) // 2
            formatted = formatted[:half] + " ... " + formatted[-half:]

        return formatted

    @staticmethod
    def format_path_with_metadata(path: Path) -> str:
        """Format a path with additional metadata."""
        real_nodes = [n for n in path if n not in SPECIAL_NODES]
        appeals = sum(1 for n in path if "APPEAL" in n)

        return (
            f"Length {len(path)} ({len(real_nodes)} real nodes, {appeals} appeals)\n"
            f"  {PathFormatter.format_path(path)}"
        )


class StatisticsDisplay:
    """Responsible for displaying statistics in a readable format."""

    @staticmethod
    def display_header(title: str, width: int = 70) -> None:
        """Display a formatted header."""
        print(f"\n{title}")
        print("=" * width)

    @staticmethod
    def display_counting_comparison(
        matrix_result: CountingResult, dfs_count: int
    ) -> None:
        """Display comparison between counting methods."""
        StatisticsDisplay.display_header("COUNTING METHOD COMPARISON")

        print(f"\nMethod Results:")
        print(f"  Adjacency Matrix: {matrix_result.count:,}")
        print(f"  DFS Generation:   {dfs_count:,}")

        match = matrix_result.count == dfs_count
        status = "✓ VALID" if match else "✗ MISMATCH"
        print(f"  Status: {status}")

        if not match:
            print(
                f"\n  WARNING: Counts differ by {abs(matrix_result.count - dfs_count):,}"
            )

    @staticmethod
    def display_path_statistics(stats: PathStatistics) -> None:
        """Display comprehensive path statistics."""
        StatisticsDisplay.display_header("PATH ANALYSIS")

        print(f"\nTotal paths: {stats.total_paths:,}")

        # Length distribution
        print("\nPath length distribution:")
        for length in sorted(stats.length_distribution.keys()):
            count = stats.length_distribution[length]
            real_length = length - 2  # Subtract START and END
            percentage = (count / stats.total_paths) * 100
            print(
                f"  Length {length} ({real_length} real): "
                f"{count:,} paths ({percentage:.1f}%)"
            )

        # Appeal distribution
        print("\nAppeal count distribution:")
        for appeals in sorted(stats.appeal_distribution.keys()):
            count = stats.appeal_distribution[appeals]
            percentage = (count / stats.total_paths) * 100
            bar = "█" * int(percentage / 2)  # Visual bar
            print(f"  {appeals} appeals: {count:,} ({percentage:.1f}%) {bar}")

        # Top patterns
        print("\nMost common patterns:")
        sorted_patterns = sorted(
            stats.pattern_frequency.items(), key=lambda x: x[1], reverse=True
        )
        for pattern, count in sorted_patterns[:10]:
            percentage = (count / stats.total_paths) * 100
            print(f"  {pattern}: {count:,} ({percentage:.1f}%)")

    @staticmethod
    def display_example_paths(
        paths: List[Path], title: str, max_examples: int = 3
    ) -> None:
        """Display example paths with a title."""
        print(f"\n{title}:")
        for i, path in enumerate(paths[:max_examples], 1):
            print(f"\n{i}. {PathFormatter.format_path_with_metadata(path)}")


class ProgressReporter:
    """Handles progress reporting for long-running operations."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.last_reported = 0

    def report_length_count(self, length: int, count: int) -> None:
        """Report count for a specific length."""
        if self.verbose and count > 0:
            print(f"Length {length}: {count:,} paths")

    def report_progress(self, current: int, total: int, step: int = 1000) -> None:
        """Report progress for batch operations."""
        if self.verbose and current - self.last_reported >= step:
            percentage = (current / total) * 100
            print(f"Progress: {current:,}/{total:,} ({percentage:.1f}%)")
            self.last_reported = current


def create_summary_report(
    stats: PathStatistics, shortest: List[Path], longest: List[Path]
) -> str:
    """
    Create a comprehensive summary report as a string.

    Useful for saving results to a file.
    """
    lines = []

    lines.append("TRANSACTION PATH ANALYSIS SUMMARY")
    lines.append("=" * 70)
    lines.append(f"\nTotal valid paths: {stats.total_paths:,}")

    # Key metrics
    avg_length = (
        sum(l * c for l, c in stats.length_distribution.items()) / stats.total_paths
    )
    avg_appeals = (
        sum(a * c for a, c in stats.appeal_distribution.items()) / stats.total_paths
    )

    lines.append(f"Average path length: {avg_length:.2f}")
    lines.append(f"Average appeals per path: {avg_appeals:.2f}")

    # Length range
    min_len = min(stats.length_distribution.keys())
    max_len = max(stats.length_distribution.keys())
    lines.append(f"Length range: {min_len} to {max_len}")

    # Most common length
    most_common_length = max(stats.length_distribution.items(), key=lambda x: x[1])
    lines.append(
        f"Most common length: {most_common_length[0]} "
        f"({most_common_length[1]:,} paths)"
    )

    # Pattern summary
    lines.append(f"\nUnique patterns found: {len(stats.pattern_frequency)}")

    # Example paths
    lines.append("\nShortest path example:")
    if shortest:
        lines.append(f"  {PathFormatter.format_path(shortest[0])}")

    lines.append("\nLongest path example:")
    if longest:
        lines.append(f"  {PathFormatter.format_path(longest[0])}")

    return "\n".join(lines)
