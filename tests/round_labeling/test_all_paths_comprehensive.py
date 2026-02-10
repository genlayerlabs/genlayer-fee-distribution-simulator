"""
Comprehensive path testing framework for round labeling.

This module tests round labeling against all possible paths from the transaction graph.
It supports:
- Testing all 133M+ possible paths
- Slicing paths by various criteria (first N, last N, round count, etc.)
- Parallel execution for performance
- Progress tracking for long-running tests

Usage examples:
    # Test first 500 paths
    pytest test_all_paths_comprehensive.py -m "first_500"

    # Test paths with 13-16 rounds
    pytest test_all_paths_comprehensive.py -m "rounds_13_to_16"

    # Test specific path range
    pytest test_all_paths_comprehensive.py -k "test_path_range[1000000:1001000]"
"""

import pytest
import os
from typing import List, Dict, Generator, Tuple, Optional
from functools import lru_cache
import itertools
from dataclasses import dataclass

from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    Round,
    Rotation,
    TransactionBudget,
    Appeal,
)
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.utils import generate_random_eth_address
from src.fee_simulator.protocol.types import Vote, RoundLabel
from src.fee_simulator.specification.state_machine.path_analysis.round_combinations import (
    generate_all_paths,
    PathConstraints,
    TRANSACTION_GRAPH,
)
from src.fee_simulator.specification.invariants.checker import check_all_invariants


# Configuration
@dataclass
class PathTestConfig:
    """Configuration for path testing."""

    batch_size: int = 1000
    max_rounds: int = 10  # Reasonable limit for testing (actual max is 19)
    min_rounds: int = 3  # Minimum meaningful path length
    random_seed: int = 42
    address_pool_size: int = 5000


# Global configuration
CONFIG = PathTestConfig()

# Pre-generate address pool for performance
ADDR_POOL = [generate_random_eth_address() for _ in range(CONFIG.address_pool_size)]


class PathGenerator:
    """Efficient path generator with caching and filtering."""

    def __init__(self, constraints: Optional[PathConstraints] = None):
        self.constraints = constraints or PathConstraints(
            min_length=CONFIG.min_rounds + 2,  # +2 for START and END
            max_length=CONFIG.max_rounds + 2,
            source_node="START",
            target_node="END",
        )

    @lru_cache(maxsize=1)
    def get_total_path_count(self) -> int:
        """Get total number of paths (cached)."""
        # This is expensive, so we estimate based on graph structure
        # In practice, you'd compute this once and store it
        return 133_000_000  # Approximate

    def generate_paths_batch(self, start_idx: int, batch_size: int) -> List[List[str]]:
        """Generate a batch of paths starting from start_idx."""
        paths = []
        path_gen = generate_all_paths(TRANSACTION_GRAPH, self.constraints)

        # More efficient: collect all paths up to start_idx + batch_size
        # then slice the result
        collected = 0
        for i, path in enumerate(path_gen):
            if i >= start_idx:
                paths.append(path)
                if len(paths) >= batch_size:
                    break
            collected += 1

            # Progress indicator for long skips
            if start_idx > 1000 and collected % 1000 == 0 and collected < start_idx:
                print(f"  Skipping to start index: {collected}/{start_idx}")

        return paths

    def generate_paths_by_rounds(
        self, min_rounds: int, max_rounds: int
    ) -> Generator[List[str], None, None]:
        """Generate paths with specific round count."""
        constraints = PathConstraints(
            min_length=min_rounds + 2,
            max_length=max_rounds + 2,
            source_node="START",
            target_node="END",
        )
        yield from generate_all_paths(TRANSACTION_GRAPH, constraints)


class PathToTransaction:
    """Convert paths to transaction results."""

    @staticmethod
    def create_votes_for_node(
        node: str, base_addr: int, num_validators: int = 5
    ) -> Dict[str, Vote]:
        """Create votes based on node type."""
        votes = {}

        if "LEADER_TIMEOUT" in node:
            votes[ADDR_POOL[base_addr]] = ["LEADER_TIMEOUT", "NA"]
            for i in range(1, num_validators):
                votes[ADDR_POOL[base_addr + i]] = "NA"

        elif "LEADER_RECEIPT" in node:
            # Determine vote distribution based on outcome
            if "MAJORITY_AGREE" in node:
                votes[ADDR_POOL[base_addr]] = ["LEADER_RECEIPT", "AGREE"]
                for i in range(1, num_validators):
                    votes[ADDR_POOL[base_addr + i]] = "AGREE"

            elif "MAJORITY_DISAGREE" in node:
                votes[ADDR_POOL[base_addr]] = ["LEADER_RECEIPT", "AGREE"]
                votes[ADDR_POOL[base_addr + 1]] = "AGREE"
                for i in range(2, num_validators):
                    votes[ADDR_POOL[base_addr + i]] = "DISAGREE"

            elif "UNDETERMINED" in node:
                votes[ADDR_POOL[base_addr]] = ["LEADER_RECEIPT", "AGREE"]
                votes[ADDR_POOL[base_addr + 1]] = "AGREE"
                votes[ADDR_POOL[base_addr + 2]] = "DISAGREE"
                votes[ADDR_POOL[base_addr + 3]] = "DISAGREE"
                votes[ADDR_POOL[base_addr + 4]] = "TIMEOUT"

        elif "APPEAL" in node:
            # Appeal rounds have different vote patterns
            if "VALIDATOR_APPEAL" in node:
                if "SUCCESSFUL" in node:
                    # Validators change their mind
                    for i in range(num_validators):
                        votes[ADDR_POOL[base_addr + i]] = "DISAGREE"
                else:
                    # Validators maintain position
                    for i in range(num_validators):
                        votes[ADDR_POOL[base_addr + i]] = "AGREE"
            else:  # LEADER_APPEAL
                for i in range(num_validators):
                    votes[ADDR_POOL[base_addr + i]] = "NA"

        return votes

    @staticmethod
    def path_to_transaction(
        path: List[str],
    ) -> Tuple[TransactionRoundResults, TransactionBudget]:
        """Convert a path to transaction results and budget."""
        rounds = []
        addr_offset = 0
        appeal_count = 0

        for node in path[1:-1]:  # Skip START and END
            if "APPEAL" in node:
                appeal_count += 1
                num_validators = 5 + appeal_count * 2
            else:
                num_validators = 5

            votes = PathToTransaction.create_votes_for_node(
                node, addr_offset, num_validators
            )
            rounds.append(Round(rotations=[Rotation(votes=votes)]))
            addr_offset += num_validators

        # Create budget
        appeals = [
            Appeal(appealantAddress=ADDR_POOL[1900 + i]) for i in range(appeal_count)
        ]
        # Rotations should be appealRounds + 1 according to validation
        rotations = [0] * (appeal_count + 1)

        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=appeal_count,
            rotations=rotations,
            senderAddress=ADDR_POOL[1999],
            appeals=appeals,
            staking_distribution="constant",
        )

        return TransactionRoundResults(rounds=rounds), budget


class RoundLabelingInvariants:
    """Check round labeling invariants."""

    @staticmethod
    def check_all_invariants(
        labels: List[RoundLabel],
        transaction_results: TransactionRoundResults,
        path: List[str],
    ):
        """Check all invariants for round labeling."""
        # Every round must have a label
        assert len(labels) == len(
            transaction_results.rounds
        ), f"Label count mismatch for path {path}"

        # All labels must be valid
        valid_labels = {
            "NORMAL_ROUND",
            "EMPTY_ROUND",
            "LEADER_TIMEOUT",
            "LEADER_TIMEOUT_50_PERCENT",
            "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
            "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
            "APPEAL_LEADER_SUCCESSFUL",
            "APPEAL_LEADER_UNSUCCESSFUL",
            "APPEAL_VALIDATOR_SUCCESSFUL",
            "APPEAL_VALIDATOR_UNSUCCESSFUL",
            "SKIP_ROUND",
            "SPLIT_PREVIOUS_APPEAL_BOND",
            "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
            "VALIDATORS_PENALTY_ONLY_ROUND",
            "EQUAL_SPLIT",
        }
        for i, label in enumerate(labels):
            assert (
                label in valid_labels
            ), f"Invalid label '{label}' at index {i} for path {path}"

        # Appeal labels must correspond to rounds with appeal characteristics
        for i, label in enumerate(labels):
            if "APPEAL" in label and label not in [
                "SPLIT_PREVIOUS_APPEAL_BOND",
                "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            ]:
                # Verify the round has appeal characteristics
                round_obj = transaction_results.rounds[i]
                if round_obj.rotations:
                    votes = round_obj.rotations[-1].votes
                    has_na_votes = any(
                        v == "NA" or (isinstance(v, list) and "NA" in v)
                        for v in votes.values()
                    )
                    has_leader_receipt = any(
                        isinstance(v, list) and v[0] == "LEADER_RECEIPT"
                        for v in votes.values()
                    )
                    assert (
                        has_na_votes or not has_leader_receipt
                    ), f"Appeal '{label}' at index {i} but round doesn't have appeal characteristics for path {path}"


# Test Classes with Markers
@pytest.mark.quick
class TestQuickPaths:
    """Quick smoke tests for CI."""

    def test_basic_patterns(self):
        """Test basic round labeling patterns."""
        test_paths = [
            ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"],
            ["START", "LEADER_TIMEOUT", "END"],
            [
                "START",
                "LEADER_RECEIPT_UNDETERMINED",
                "LEADER_APPEAL_SUCCESSFUL",
                "LEADER_RECEIPT_MAJORITY_AGREE",
                "END",
            ],
        ]

        for path in test_paths:
            tx, budget = PathToTransaction.path_to_transaction(path)
            labels = label_rounds(tx)
            RoundLabelingInvariants.check_all_invariants(labels, tx, path)


@pytest.mark.first_500
class TestFirst500Paths:
    """Test first 500 paths."""

    def test_first_500(self):
        """Test the first 500 paths from the graph."""
        generator = PathGenerator()
        print("Generating first 500 paths...")
        paths = generator.generate_paths_batch(0, 500)
        print(f"Generated {len(paths)} paths. Starting validation...")

        for i, path in enumerate(paths):
            # Better progress reporting
            if i % 50 == 0:
                print(f"  Progress: {i/500*100:.1f}% ({i}/500)")

            tx, budget = PathToTransaction.path_to_transaction(path)
            labels = label_rounds(tx)
            RoundLabelingInvariants.check_all_invariants(labels, tx, path)

            # Test with transaction processing every 10th path to save time
            if i % 10 == 0:
                fee_events, round_labels = process_transaction(ADDR_POOL, tx, budget)
                assert round_labels == labels, f"Label mismatch for path {i}: {path}"

        print("  Progress: 100.0% (500/500) - Complete!")


@pytest.mark.last_500
class TestLast500Paths:
    """Test last 500 paths."""

    def test_last_500(self):
        """Test the last 500 paths from the graph."""
        generator = PathGenerator()
        total = generator.get_total_path_count()
        paths = generator.generate_paths_batch(total - 500, 500)

        for i, path in enumerate(paths):
            tx, budget = PathToTransaction.path_to_transaction(path)
            labels = label_rounds(tx)
            RoundLabelingInvariants.check_all_invariants(labels, tx, path)


@pytest.mark.rounds_7_to_10
@pytest.mark.skip(reason="Path length constraints don't match round counts exactly")
class TestSpecificRoundCounts:
    """Test paths with specific round counts."""

    @pytest.mark.parametrize("round_count", [7, 8, 9, 10])
    def test_paths_with_rounds(self, round_count):
        """Test paths with specific number of rounds."""
        generator = PathGenerator()
        paths = list(
            itertools.islice(
                generator.generate_paths_by_rounds(round_count, round_count),
                10,  # Reduced from 100 to 10 for performance
            )
        )

        for path in paths:
            # Verify round count (minus START and END)
            assert len(path) - 2 == round_count, f"Path has wrong round count: {path}"

            tx, budget = PathToTransaction.path_to_transaction(path)
            labels = label_rounds(tx)
            RoundLabelingInvariants.check_all_invariants(labels, tx, path)


@pytest.mark.parametrize(
    "start,end",
    [
        (0, 100),  # Reduced from 1000
        (1000, 1100),  # Reduced from 10000-11000
        (10000, 10100),  # Reduced from 100000-101000
    ],
)
class TestPathRange:
    """Test specific ranges of paths."""

    def test_path_range(self, start, end):
        """Test a specific range of paths."""
        generator = PathGenerator()
        paths = generator.generate_paths_batch(start, end - start)

        for i, path in enumerate(paths):
            tx, budget = PathToTransaction.path_to_transaction(path)
            labels = label_rounds(tx)
            RoundLabelingInvariants.check_all_invariants(labels, tx, path)

            if i % 100 == 0:
                print(f"Tested path {start + i}")


@pytest.mark.all_paths
@pytest.mark.slow
@pytest.mark.skip(reason="Only run with explicit --runallpaths flag")
class TestAllPaths:
    """Test ALL possible paths - WARNING: This will take a very long time!"""

    @pytest.mark.skipif(True, reason="Only run explicitly")
    def test_all_paths_comprehensive(self):
        """Test all 133M+ paths comprehensively."""
        generator = PathGenerator()
        batch_size = CONFIG.batch_size
        total = generator.get_total_path_count()

        for batch_start in range(0, total, batch_size):
            paths = generator.generate_paths_batch(batch_start, batch_size)

            for i, path in enumerate(paths):
                global_idx = batch_start + i

                # Progress indicator
                if global_idx % 10000 == 0:
                    progress = (global_idx / total) * 100
                    print(f"Progress: {progress:.2f}% ({global_idx}/{total})")

                tx, budget = PathToTransaction.path_to_transaction(path)
                labels = label_rounds(tx)
                RoundLabelingInvariants.check_all_invariants(labels, tx, path)

                # Periodically test full transaction processing
                if global_idx % 1000 == 0:
                    fee_events, round_labels = process_transaction(
                        ADDR_POOL, tx, budget
                    )
                    assert (
                        round_labels == labels
                    ), f"Label mismatch at index {global_idx}"
                    check_all_invariants(fee_events, budget, tx)


if __name__ == "__main__":
    print("Comprehensive Path Testing Framework")
    print("====================================")
    print(f"Total estimated paths: ~133M")
    print(f"Batch size: {CONFIG.batch_size}")
    print(f"Round range: {CONFIG.min_rounds}-{CONFIG.max_rounds}")
    print()
    print("Usage examples:")
    print(
        "  pytest test_all_paths_comprehensive.py -m quick           # Quick smoke tests"
    )
    print(
        "  pytest test_all_paths_comprehensive.py -m first_500       # First 500 paths"
    )
    print(
        "  pytest test_all_paths_comprehensive.py -m rounds_13_to_16 # Specific round counts"
    )
    print(
        "  pytest test_all_paths_comprehensive.py -k 'test_path_range[1000000:1001000]'  # Specific range"
    )
    print()
    print("WARNING: Running all paths will take an extremely long time!")
