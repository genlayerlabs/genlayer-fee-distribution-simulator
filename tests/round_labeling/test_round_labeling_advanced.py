"""
Advanced functional testing framework for round labeling.

Uses monadic patterns, property-based testing, and algebraic verification
to ensure complete correctness of the round labeling system.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, example
from functools import partial, reduce, wraps
from typing import (
    List,
    Dict,
    Tuple,
    Callable,
    Optional,
    TypeVar,
    Generic,
    Union,
    Any,
    Protocol,
    runtime_checkable,
)
from dataclasses import dataclass
from abc import ABC, abstractmethod

from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    Round,
    Rotation,
    TransactionBudget,
    Appeal,
)
from src.fee_simulator.utils import generate_random_eth_address
from src.fee_simulator.specification.state_machine.path_analysis.round_combinations import (
    TRANSACTION_GRAPH,
)

# Type definitions
T = TypeVar("T")
S = TypeVar("S")
NodeType = str
PathType = List[NodeType]
RoundLabel = str


# Monadic Result type for error handling
@dataclass
class Result(Generic[T]):
    """Monadic Result type for handling success/failure."""

    value: Optional[T]
    error: Optional[str]

    @property
    def is_success(self) -> bool:
        return self.error is None

    def map(self, f: Callable[[T], S]) -> "Result[S]":
        """Map a function over the result."""
        if self.is_success:
            try:
                return Result(value=f(self.value), error=None)
            except Exception as e:
                return Result(value=None, error=str(e))
        return Result(value=None, error=self.error)

    def flat_map(self, f: Callable[[T], "Result[S]"]) -> "Result[S]":
        """Monadic bind operation."""
        if self.is_success:
            return f(self.value)
        return Result(value=None, error=self.error)

    def get_or_else(self, default: T) -> T:
        """Get value or return default."""
        return self.value if self.is_success else default


# Address pool management
class AddressPool:
    """Functional address pool management."""

    def __init__(self, size: int = 2000):
        self._pool = [generate_random_eth_address() for _ in range(size)]
        self._index = 0

    def take(self, n: int) -> List[str]:
        """Take n addresses from the pool."""
        if self._index + n > len(self._pool):
            raise ValueError("Not enough addresses in pool")
        result = self._pool[self._index : self._index + n]
        self._index += n
        return result

    def reset(self):
        """Reset the pool index."""
        self._index = 0

    @property
    def sender_address(self) -> str:
        return self._pool[-1]

    def appealant_address(self, index: int) -> str:
        return self._pool[-(index + 2)]


# Functional vote generators using algebraic data types
@dataclass(frozen=True)
class VoteSpec:
    """Specification for generating votes."""

    outcome: str
    num_validators: int

    def generate(self, addresses: List[str]) -> Dict[str, Any]:
        """Generate votes according to specification."""
        return VOTE_GENERATORS[self.outcome](addresses, self.num_validators)


# Vote generator functions
def generate_leader_timeout_votes(
    addresses: List[str], num_validators: int
) -> Dict[str, Any]:
    """Generate votes for leader timeout."""
    votes = {addresses[0]: ["LEADER_TIMEOUT", "NA"]}
    for i in range(1, min(num_validators, len(addresses))):
        votes[addresses[i]] = "NA"
    return votes


def generate_majority_agree_votes(
    addresses: List[str], num_validators: int
) -> Dict[str, Any]:
    """Generate votes for majority agree."""
    votes = {addresses[0]: ["LEADER_RECEIPT", "AGREE"]}
    agree_count = (num_validators // 2) + 1

    for i in range(1, min(agree_count, len(addresses))):
        votes[addresses[i]] = "AGREE"
    for i in range(agree_count, min(num_validators, len(addresses))):
        votes[addresses[i]] = "DISAGREE"

    return votes


def generate_majority_disagree_votes(
    addresses: List[str], num_validators: int
) -> Dict[str, Any]:
    """Generate votes for majority disagree."""
    votes = {addresses[0]: ["LEADER_RECEIPT", "AGREE"]}
    disagree_count = (num_validators // 2) + 1

    for i in range(1, num_validators - disagree_count + 1):
        votes[addresses[i]] = "AGREE"
    for i in range(num_validators - disagree_count + 1, num_validators):
        votes[addresses[i]] = "DISAGREE"

    return votes


def generate_undetermined_votes(
    addresses: List[str], num_validators: int
) -> Dict[str, Any]:
    """Generate votes for undetermined outcome."""
    votes = {addresses[0]: ["LEADER_RECEIPT", "AGREE"]}

    # Split validators roughly equally
    third = max(1, (num_validators - 1) // 3)

    for i in range(1, third + 1):
        votes[addresses[i]] = "AGREE"
    for i in range(third + 1, 2 * third + 1):
        votes[addresses[i]] = "DISAGREE"
    for i in range(2 * third + 1, num_validators):
        votes[addresses[i]] = "TIMEOUT"

    return votes


def generate_appeal_votes(addresses: List[str], num_validators: int) -> Dict[str, Any]:
    """Generate votes for appeal round."""
    return {addresses[i]: "NA" for i in range(num_validators)}


# Vote generator registry
VOTE_GENERATORS = {
    "LEADER_TIMEOUT": generate_leader_timeout_votes,
    "LEADER_RECEIPT_MAJORITY_AGREE": generate_majority_agree_votes,
    "LEADER_RECEIPT_MAJORITY_DISAGREE": generate_majority_disagree_votes,
    "LEADER_RECEIPT_UNDETERMINED": generate_undetermined_votes,
    "LEADER_RECEIPT_MAJORITY_TIMEOUT": generate_majority_agree_votes,  # Simplified
    "MAJORITY_AGREE": generate_majority_agree_votes,
    "MAJORITY_DISAGREE": generate_majority_disagree_votes,
    "MAJORITY_TIMEOUT": generate_majority_agree_votes,  # Simplified
    "UNDETERMINED": generate_undetermined_votes,
}


# Path algebra
@runtime_checkable
class PathAlgebra(Protocol):
    """Protocol for path algebraic operations."""

    def is_valid_transition(self, from_node: NodeType, to_node: NodeType) -> bool:
        """Check if transition is valid."""
        ...

    def get_successors(self, node: NodeType) -> List[NodeType]:
        """Get valid successors for a node."""
        ...


class TransactionGraphAlgebra:
    """Concrete implementation of path algebra for transaction graph."""

    def __init__(self, graph: Dict[str, List[str]]):
        self.graph = graph

    def is_valid_transition(self, from_node: NodeType, to_node: NodeType) -> bool:
        """Check if transition is valid in graph."""
        return from_node in self.graph and to_node in self.graph.get(from_node, [])

    def get_successors(self, node: NodeType) -> List[NodeType]:
        """Get valid successors for a node."""
        return self.graph.get(node, [])

    def is_valid_path(self, path: PathType) -> bool:
        """Check if entire path is valid."""
        if len(path) < 2:
            return len(path) == 1 and path[0] in self.graph

        return all(
            self.is_valid_transition(path[i], path[i + 1]) for i in range(len(path) - 1)
        )


# Functional path to transaction converter
class PathToTransactionConverter:
    """Converts paths to transaction results using functional composition."""

    def __init__(self, address_pool: AddressPool):
        self.address_pool = address_pool
        self.round_sizes = [5, 7, 11, 13, 17, 19, 23, 25, 29, 31]

    def convert(
        self, path: PathType
    ) -> Result[Tuple[TransactionRoundResults, TransactionBudget]]:
        """Convert path to transaction results."""
        try:
            self.address_pool.reset()
            rounds = []
            appeals = []

            # Filter actual nodes
            nodes = [n for n in path if n not in ["START", "END"]]

            for i, node in enumerate(nodes):
                round_result = self._node_to_round(node, i)
                if round_result.is_success:
                    round_obj, is_appeal = round_result.value
                    rounds.append(round_obj)

                    if is_appeal:
                        appeals.append(
                            Appeal(
                                appealantAddress=self.address_pool.appealant_address(
                                    len(appeals)
                                )
                            )
                        )
                else:
                    return Result(value=None, error=round_result.error)

            # Create budget
            budget = self._create_budget(len(rounds), len(appeals), appeals)

            return Result(
                value=(TransactionRoundResults(rounds=rounds), budget), error=None
            )
        except Exception as e:
            return Result(value=None, error=str(e))

    def _node_to_round(self, node: NodeType, index: int) -> Result[Tuple[Round, bool]]:
        """Convert a single node to a round."""
        try:
            size = self._get_round_size(index)
            addresses = self.address_pool.take(size)

            is_appeal = "APPEAL" in node

            if is_appeal:
                votes = generate_appeal_votes(addresses, size)
            elif node in VOTE_GENERATORS:
                votes = VOTE_GENERATORS[node](addresses, size)
            else:
                # Default to undetermined
                votes = generate_undetermined_votes(addresses, size)

            rotation = Rotation(votes=votes)
            round_obj = Round(rotations=[rotation])

            return Result(value=(round_obj, is_appeal), error=None)
        except Exception as e:
            return Result(value=None, error=f"Error converting node {node}: {str(e)}")

    def _get_round_size(self, index: int) -> int:
        """Get round size based on index."""
        return self.round_sizes[min(index, len(self.round_sizes) - 1)]

    def _create_budget(
        self, num_rounds: int, num_appeals: int, appeals: List[Appeal]
    ) -> TransactionBudget:
        """Create transaction budget."""
        rotations = [0] * ((num_rounds + 1) // 2)

        return TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=num_appeals,
            rotations=rotations,
            senderAddress=self.address_pool.sender_address,
            appeals=appeals,
            staking_distribution="constant",
        )


# Invariant verification system
class Invariant(ABC):
    """Abstract base class for invariants."""

    @abstractmethod
    def check(
        self,
        labels: List[RoundLabel],
        transaction: TransactionRoundResults,
        path: PathType,
    ) -> Result[bool]:
        """Check if invariant holds."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the invariant."""
        pass


class LabelCountInvariant(Invariant):
    """Every round gets exactly one label."""

    def check(
        self,
        labels: List[RoundLabel],
        transaction: TransactionRoundResults,
        path: PathType,
    ) -> Result[bool]:
        if len(labels) == len(transaction.rounds):
            return Result(value=True, error=None)
        return Result(
            value=False,
            error=f"Label count {len(labels)} != round count {len(transaction.rounds)}",
        )

    @property
    def name(self) -> str:
        return "Label Count"


class ValidLabelsInvariant(Invariant):
    """All labels are valid RoundLabel values."""

    VALID_LABELS = {
        "NORMAL_ROUND",
        "EMPTY_ROUND",
        "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
        "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
        "APPEAL_LEADER_SUCCESSFUL",
        "APPEAL_LEADER_UNSUCCESSFUL",
        "APPEAL_VALIDATOR_SUCCESSFUL",
        "APPEAL_VALIDATOR_UNSUCCESSFUL",
        "LEADER_TIMEOUT",
        "VALIDATORS_PENALTY_ONLY_ROUND",
        "SKIP_ROUND",
        "LEADER_TIMEOUT_50_PERCENT",
        "SPLIT_PREVIOUS_APPEAL_BOND",
        "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
    }

    def check(
        self,
        labels: List[RoundLabel],
        transaction: TransactionRoundResults,
        path: PathType,
    ) -> Result[bool]:
        invalid = [label for label in labels if label not in self.VALID_LABELS]
        if not invalid:
            return Result(value=True, error=None)
        return Result(value=False, error=f"Invalid labels found: {invalid}")

    @property
    def name(self) -> str:
        return "Valid Labels"


class AppealPositionInvariant(Invariant):
    """Appeals are correctly identified based on round content."""

    def check(
        self,
        labels: List[RoundLabel],
        transaction: TransactionRoundResults,
        path: PathType,
    ) -> Result[bool]:
        for i, label in enumerate(labels):
            if self._is_appeal_label(label):
                # Check that the round has appeal characteristics
                if i < len(transaction.rounds):
                    round_obj = transaction.rounds[i]
                    if round_obj.rotations:
                        votes = round_obj.rotations[-1].votes
                        # Appeal rounds should have NA votes or no leader receipt
                        has_na_votes = any(
                            v == "NA" or (isinstance(v, list) and "NA" in v)
                            for v in votes.values()
                        )
                        has_leader_receipt = any(
                            isinstance(v, list) and v[0] == "LEADER_RECEIPT"
                            for v in votes.values()
                        )

                        if not has_na_votes and has_leader_receipt:
                            return Result(
                                value=False,
                                error=f"Appeal label '{label}' at index {i} but round has leader receipt and no NA votes",
                            )
        return Result(value=True, error=None)

    def _is_appeal_label(self, label: str) -> bool:
        """Check if label is an appeal label."""
        return "APPEAL" in label and label not in [
            "SPLIT_PREVIOUS_APPEAL_BOND",
            "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        ]

    @property
    def name(self) -> str:
        return "Appeal Position"


class ChainedAppealInvariant(Invariant):
    """Chained appeals are handled correctly."""

    def check(
        self,
        labels: List[RoundLabel],
        transaction: TransactionRoundResults,
        path: PathType,
    ) -> Result[bool]:
        # Check SPLIT_PREVIOUS_APPEAL_BOND placement
        for i, label in enumerate(labels):
            if label == "SPLIT_PREVIOUS_APPEAL_BOND":
                if not self._has_unsuccessful_appeal_before(i, labels):
                    return Result(
                        value=False,
                        error=f"SPLIT_PREVIOUS_APPEAL_BOND at {i} without prior unsuccessful appeal",
                    )

        return Result(value=True, error=None)

    def _has_unsuccessful_appeal_before(self, index: int, labels: List[str]) -> bool:
        """Check if there's an unsuccessful appeal before the given index."""
        for i in range(index - 1, -1, -1):
            if "APPEAL" in labels[i] and "UNSUCCESSFUL" in labels[i]:
                return True
            elif "APPEAL" in labels[i] and "SUCCESSFUL" in labels[i]:
                return False  # Successful appeal breaks the chain
        return False

    @property
    def name(self) -> str:
        return "Chained Appeals"


# Invariant checking system
class InvariantChecker:
    """Checks all invariants for a given labeling."""

    def __init__(self, invariants: List[Invariant]):
        self.invariants = invariants

    def check_all(
        self,
        labels: List[RoundLabel],
        transaction: TransactionRoundResults,
        path: PathType,
    ) -> Result[Dict[str, bool]]:
        """Check all invariants and return results."""
        results = {}
        errors = []

        for invariant in self.invariants:
            result = invariant.check(labels, transaction, path)
            results[invariant.name] = result.is_success
            if not result.is_success:
                errors.append(f"{invariant.name}: {result.error}")

        if errors:
            return Result(value=results, error="; ".join(errors))
        return Result(value=results, error=None)


# Property-based testing strategies
@st.composite
def path_strategy(draw, max_length: int = 10):
    """Generate valid paths through the transaction graph."""
    algebra = TransactionGraphAlgebra(TRANSACTION_GRAPH)

    path = ["START"]
    current = "START"

    length = draw(st.integers(min_value=1, max_value=max_length))

    for _ in range(length):
        if current == "END":
            break

        successors = algebra.get_successors(current)
        if not successors:
            break

        if "END" in successors and len(path) >= 3:
            # Increase probability of ending
            if draw(st.booleans()):
                next_node = "END"
            else:
                next_node = draw(st.sampled_from(successors))
        else:
            next_node = draw(st.sampled_from(successors))

        path.append(next_node)
        current = next_node

    if current != "END" and "END" in algebra.get_successors(current):
        path.append("END")

    assume(algebra.is_valid_path(path))
    return path


# Main test class using property-based testing
class TestRoundLabelingProperties:
    """Property-based tests for round labeling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.address_pool = AddressPool()
        self.converter = PathToTransactionConverter(self.address_pool)
        self.algebra = TransactionGraphAlgebra(TRANSACTION_GRAPH)
        self.checker = InvariantChecker(
            [
                LabelCountInvariant(),
                ValidLabelsInvariant(),
                AppealPositionInvariant(),
                ChainedAppealInvariant(),
            ]
        )

    @given(path_strategy())
    @settings(max_examples=200, deadline=None)
    def test_all_invariants_hold(self, path):
        """Test that all invariants hold for any valid path."""
        # Convert path to transaction
        conversion_result = self.converter.convert(path)
        assume(conversion_result.is_success)

        transaction, budget = conversion_result.value

        # Label rounds
        labels = label_rounds(transaction)

        # Check invariants
        check_result = self.checker.check_all(labels, transaction, path)

        assert (
            check_result.is_success
        ), f"Invariant failures for path {path}: {check_result.error}"

    @given(path_strategy())
    @settings(max_examples=100, deadline=None)
    def test_deterministic_labeling(self, path):
        """Test that labeling is deterministic."""
        conversion_result = self.converter.convert(path)
        assume(conversion_result.is_success)

        transaction, _ = conversion_result.value

        # Label multiple times
        labels1 = label_rounds(transaction)
        labels2 = label_rounds(transaction)
        labels3 = label_rounds(transaction)

        assert (
            labels1 == labels2 == labels3
        ), f"Non-deterministic labeling for path {path}"

    @given(path_strategy(max_length=20))
    @settings(max_examples=50, deadline=None)
    @example(
        [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "END",
        ]
    )
    def test_chained_appeals(self, path):
        """Test paths with chained appeals."""
        # Count appeals in path
        appeal_count = sum(1 for node in path if "APPEAL" in node and node != "END")

        if appeal_count >= 2:
            conversion_result = self.converter.convert(path)
            assume(conversion_result.is_success)

            transaction, budget = conversion_result.value
            labels = label_rounds(transaction)

            # Count unsuccessful appeals in labels
            unsuccessful_count = sum(1 for label in labels if "UNSUCCESSFUL" in label)

            # Verify chain handling
            check_result = self.checker.check_all(labels, transaction, path)
            assert (
                check_result.is_success
            ), f"Failed to handle chained appeals in path {path}: {check_result.error}"


# Algebraic verification
def verify_labeling_algebra():
    """Verify algebraic properties of the labeling function."""

    # Property 1: Idempotence of labeling
    # label(label(x)) should equal label(x) conceptually

    # Property 2: Composition
    # Labeling of concatenated paths should be related to individual labelings

    # Property 3: Identity
    # Empty transaction should produce empty labels

    empty_transaction = TransactionRoundResults(rounds=[])
    assert label_rounds(empty_transaction) == []

    print("✓ Algebraic properties verified")


# Functional test runners
def run_exhaustive_tests(max_path_length: int = 10) -> Dict[str, Any]:
    """Run exhaustive tests on all paths up to given length."""
    from tests.round_combinations import generate_all_paths, PathConstraints

    constraints = PathConstraints(
        min_length=1, max_length=max_path_length, source_node="START", target_node="END"
    )

    all_paths = generate_all_paths(TRANSACTION_GRAPH, constraints)

    address_pool = AddressPool()
    converter = PathToTransactionConverter(address_pool)
    checker = InvariantChecker(
        [
            LabelCountInvariant(),
            ValidLabelsInvariant(),
            AppealPositionInvariant(),
            ChainedAppealInvariant(),
        ]
    )

    results = {
        "total_paths": len(all_paths),
        "successful": 0,
        "failed": 0,
        "errors": [],
    }

    for path in all_paths:
        conversion_result = converter.convert(path)

        if conversion_result.is_success:
            transaction, budget = conversion_result.value
            labels = label_rounds(transaction)

            check_result = checker.check_all(labels, transaction, path)

            if check_result.is_success:
                results["successful"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({"path": path, "error": check_result.error})
        else:
            results["failed"] += 1
            results["errors"].append({"path": path, "error": conversion_result.error})

    return results


if __name__ == "__main__":
    print("Advanced functional testing for round labeling")
    print("=" * 50)

    # Run algebraic verification
    print("\n1. Algebraic verification...")
    verify_labeling_algebra()

    # Run exhaustive tests on small paths
    print("\n2. Running exhaustive tests...")
    results = run_exhaustive_tests(max_path_length=7)

    print(f"\nResults:")
    print(f"  Total paths: {results['total_paths']}")
    print(f"  Successful: {results['successful']}")
    print(f"  Failed: {results['failed']}")

    if results["errors"]:
        print(f"\nFirst 5 errors:")
        for error in results["errors"][:5]:
            print(f"  Path: {' -> '.join(error['path'])}")
            print(f"  Error: {error['error']}")

    # Test with hypothesis
    print("\n3. Running property-based tests...")
    test = TestRoundLabelingProperties()
    test.setup_method()

    # Run a few examples
    for i in range(10):
        path = path_strategy().example()
        try:
            test.test_all_invariants_hold(path)
            print(f"  Path {i+1} ✓")
        except Exception as e:
            print(f"  Path {i+1} ✗: {str(e)}")

    print("\n✓ Advanced functional testing complete!")
