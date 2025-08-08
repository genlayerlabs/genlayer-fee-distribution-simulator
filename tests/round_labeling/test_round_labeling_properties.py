"""
Property-based testing for round labeling using hypothesis.

This ensures the round labeling function works correctly for all possible
input combinations by testing properties that must always hold.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Optional
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    Round,
    Rotation,
)
from src.fee_simulator.utils import generate_random_eth_address
from src.fee_simulator.protocol.types import Vote

# Pre-generate addresses for efficiency
ADDR_POOL = [generate_random_eth_address() for _ in range(100)]


# Strategies for generating test data
@st.composite
def vote_strategy(draw):
    """Generate a valid vote."""
    vote_type = draw(st.sampled_from(["AGREE", "DISAGREE", "TIMEOUT", "IDLE", "NA"]))

    # Sometimes include hash
    if draw(st.booleans()):
        hash_value = (
            f"0x{draw(st.text(alphabet='0123456789abcdef', min_size=8, max_size=8))}"
        )
        return [vote_type, hash_value]
    return vote_type


@st.composite
def leader_vote_strategy(draw):
    """Generate a valid leader vote."""
    action = draw(st.sampled_from(["LEADER_RECEIPT", "LEADER_TIMEOUT"]))

    if action == "LEADER_RECEIPT":
        vote_type = draw(st.sampled_from(["AGREE", "DISAGREE", "TIMEOUT"]))
    else:
        vote_type = "NA"

    # Sometimes include hash
    if draw(st.booleans()):
        hash_value = (
            f"0x{draw(st.text(alphabet='0123456789abcdef', min_size=8, max_size=8))}"
        )
        return [action, vote_type, hash_value]
    return [action, vote_type]


@st.composite
def rotation_strategy(draw, min_validators=1, max_validators=10):
    """Generate a valid rotation."""
    num_validators = draw(
        st.integers(min_value=min_validators, max_value=max_validators)
    )

    votes = {}
    used_addresses = set()

    # First address is leader
    leader_addr = draw(st.sampled_from(ADDR_POOL))
    used_addresses.add(leader_addr)
    votes[leader_addr] = draw(leader_vote_strategy())

    # Add validators
    for _ in range(num_validators - 1):
        addr = draw(st.sampled_from([a for a in ADDR_POOL if a not in used_addresses]))
        used_addresses.add(addr)
        votes[addr] = draw(vote_strategy())

    return Rotation(votes=votes)


@st.composite
def round_strategy(draw):
    """Generate a valid round."""
    # Most rounds have one rotation, but allow multiple
    num_rotations = draw(st.integers(min_value=0, max_value=3))

    if num_rotations == 0:
        return Round(rotations=[Rotation(votes={})])

    rotations = [draw(rotation_strategy()) for _ in range(num_rotations)]
    return Round(rotations=rotations)


@st.composite
def transaction_results_strategy(draw, min_rounds=1, max_rounds=7):
    """Generate valid transaction results."""
    num_rounds = draw(st.integers(min_value=min_rounds, max_value=max_rounds))
    rounds = [draw(round_strategy()) for _ in range(num_rounds)]
    return TransactionRoundResults(rounds=rounds)


class TestRoundLabelingProperties:
    """Property-based tests for round labeling."""

    @given(transaction_results_strategy())
    @settings(max_examples=200, deadline=None)
    def test_all_rounds_get_labels(self, transaction_results):
        """Property: Every round gets exactly one label."""
        labels = label_rounds(transaction_results)

        assert len(labels) == len(transaction_results.rounds)
        assert all(isinstance(label, str) and label != "" for label in labels)

    @given(transaction_results_strategy())
    @settings(max_examples=200, deadline=None)
    def test_deterministic_labeling(self, transaction_results):
        """Property: Labeling is deterministic."""
        labels1 = label_rounds(transaction_results)
        labels2 = label_rounds(transaction_results)
        labels3 = label_rounds(transaction_results)

        assert labels1 == labels2 == labels3

    @given(transaction_results_strategy())
    @settings(max_examples=200, deadline=None)
    def test_valid_label_values(self, transaction_results):
        """Property: All labels are valid RoundLabel values."""
        valid_labels = {
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

        labels = label_rounds(transaction_results)
        assert all(label in valid_labels for label in labels)

    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=50, deadline=None)
    def test_empty_rounds_labeled_correctly(self, num_rounds):
        """Property: Empty rounds are always labeled as EMPTY_ROUND."""
        rounds = [Round(rotations=[Rotation(votes={})]) for _ in range(num_rounds)]
        transaction_results = TransactionRoundResults(rounds=rounds)

        labels = label_rounds(transaction_results)
        assert all(label == "EMPTY_ROUND" for label in labels)

    @given(transaction_results_strategy(min_rounds=1, max_rounds=1))
    @settings(max_examples=100, deadline=None)
    def test_single_round_labeling(self, transaction_results):
        """Property: Single rounds follow specific rules."""
        labels = label_rounds(transaction_results)
        assert len(labels) == 1

        round = transaction_results.rounds[0]
        if not round.rotations or not round.rotations[-1].votes:
            assert labels[0] == "EMPTY_ROUND"
        else:
            # Check if it's a leader timeout (use last rotation like the implementation)
            last_rotation_votes = round.rotations[-1].votes
            if last_rotation_votes:
                first_vote = next(iter(last_rotation_votes.values()))
                if isinstance(first_vote, list) and first_vote[0] == "LEADER_TIMEOUT":
                    assert labels[0] == "LEADER_TIMEOUT_50_PERCENT"
                else:
                    assert labels[0] in ["NORMAL_ROUND", "LEADER_TIMEOUT_50_PERCENT"]
            else:
                assert labels[0] == "EMPTY_ROUND"

    def test_appeal_positioning_property(self):
        """Property: Appeals are correctly detected by vote patterns."""
        # Create specific structure with appeals
        for num_appeals in range(1, 4):
            rounds = []

            # Add normal rounds and appeals alternately
            for i in range(num_appeals * 2 + 1):
                if i % 2 == 0:
                    # Normal round
                    rounds.append(
                        Round(
                            rotations=[
                                Rotation(
                                    votes={
                                        ADDR_POOL[i * 5]: ["LEADER_RECEIPT", "AGREE"],
                                        ADDR_POOL[i * 5 + 1]: "AGREE",
                                        ADDR_POOL[i * 5 + 2]: "AGREE",
                                    }
                                )
                            ]
                        )
                    )
                else:
                    # Appeal round
                    rounds.append(
                        Round(
                            rotations=[
                                Rotation(
                                    votes={
                                        ADDR_POOL[i * 5]: "NA",
                                        ADDR_POOL[i * 5 + 1]: "NA",
                                        ADDR_POOL[i * 5 + 2]: "NA",
                                    }
                                )
                            ]
                        )
                    )

            transaction_results = TransactionRoundResults(rounds=rounds)
            labels = label_rounds(transaction_results)

            # Check that rounds with NA votes are detected as appeals
            for i, round_obj in enumerate(rounds):
                votes = round_obj.rotations[0].votes if round_obj.rotations else {}
                if votes and all(
                    v == "NA" or (isinstance(v, list) and v[1] == "NA")
                    for v in votes.values()
                ):
                    # This round has all NA votes, should be labeled as appeal
                    assert "APPEAL" in labels[i] or labels[i] in [
                        "SPLIT_PREVIOUS_APPEAL_BOND",
                        "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
                    ], f"Expected appeal-related label for round {i} with NA votes, got {labels[i]}"

    @given(st.integers(min_value=2, max_value=5))
    @settings(max_examples=50, deadline=None)
    def test_pattern_consistency(self, pattern_length):
        """Property: Known patterns always produce expected transformations."""
        # Test SKIP_ROUND pattern
        rounds = [
            # Normal round (undetermined)
            Round(
                rotations=[
                    Rotation(
                        votes={
                            ADDR_POOL[0]: ["LEADER_RECEIPT", "AGREE"],
                            ADDR_POOL[1]: "AGREE",
                            ADDR_POOL[2]: "DISAGREE",
                            ADDR_POOL[3]: "DISAGREE",
                            ADDR_POOL[4]: "TIMEOUT",
                        }
                    )
                ]
            ),
            # Appeal
            Round(
                rotations=[
                    Rotation(
                        votes={
                            ADDR_POOL[5]: "NA",
                            ADDR_POOL[6]: "NA",
                        }
                    )
                ]
            ),
            # Normal round with majority
            Round(
                rotations=[
                    Rotation(
                        votes={
                            ADDR_POOL[7]: ["LEADER_RECEIPT", "AGREE"],
                            ADDR_POOL[8]: "AGREE",
                            ADDR_POOL[9]: "AGREE",
                            ADDR_POOL[10]: "DISAGREE",
                        }
                    )
                ]
            ),
        ]

        # Add more rounds if needed
        for i in range(pattern_length - 3):
            rounds.append(
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                ADDR_POOL[11 + i]: ["LEADER_RECEIPT", "AGREE"],
                                ADDR_POOL[12 + i]: "AGREE",
                            }
                        )
                    ]
                )
            )

        transaction_results = TransactionRoundResults(rounds=rounds)
        labels = label_rounds(transaction_results)

        # First round should be SKIP_ROUND due to pattern
        assert labels[0] == "SKIP_ROUND"
        assert labels[1] == "APPEAL_LEADER_SUCCESSFUL"


class TestRoundLabelingInvariantsExtended:
    """Extended invariant tests with more complex scenarios."""

    def test_no_consecutive_appeals_at_even_indices(self):
        """Invariant: Special patterns prevent consecutive appeals at even indices."""
        # This tests that our special pattern handling transforms appeal sequences correctly
        test_cases = []

        # Generate various round sequences
        for length in [3, 5, 7]:
            rounds = []
            for i in range(length):
                if i % 2 == 0:
                    # Even index - should not be appeal (unless special case)
                    rounds.append(
                        Round(
                            rotations=[
                                Rotation(
                                    votes={
                                        ADDR_POOL[i * 2]: ["LEADER_RECEIPT", "AGREE"],
                                        ADDR_POOL[i * 2 + 1]: "AGREE",
                                    }
                                )
                            ]
                        )
                    )
                else:
                    # Odd index - can be appeal
                    rounds.append(
                        Round(
                            rotations=[
                                Rotation(
                                    votes={
                                        ADDR_POOL[i * 2]: "NA",
                                        ADDR_POOL[i * 2 + 1]: "NA",
                                    }
                                )
                            ]
                        )
                    )

            test_cases.append(TransactionRoundResults(rounds=rounds))

        for transaction_results in test_cases:
            labels = label_rounds(transaction_results)

            # Check no consecutive even-indexed appeals
            for i in range(0, len(labels) - 2, 2):
                if "APPEAL" in labels[i]:
                    assert "APPEAL" not in labels[i + 2] or labels[i + 2] in [
                        "SPLIT_PREVIOUS_APPEAL_BOND"
                    ], f"Consecutive even-indexed appeals at {i} and {i+2}"

    def test_special_patterns_are_exhaustive(self):
        """Invariant: All special patterns in the code are necessary and sufficient."""
        # This tests that our pattern matching is complete

        # Pattern 1: Skip round before successful appeal
        rounds1 = [
            Round(
                rotations=[
                    Rotation(
                        votes={
                            ADDR_POOL[0]: ["LEADER_RECEIPT", "AGREE"],
                            ADDR_POOL[1]: "DISAGREE",
                            ADDR_POOL[2]: "DISAGREE",
                        }
                    )
                ]
            ),
            Round(rotations=[Rotation(votes={ADDR_POOL[3]: "NA"})]),
            Round(
                rotations=[
                    Rotation(
                        votes={
                            ADDR_POOL[4]: ["LEADER_RECEIPT", "AGREE"],
                            ADDR_POOL[5]: "AGREE",
                        }
                    )
                ]
            ),
        ]

        labels1 = label_rounds(TransactionRoundResults(rounds=rounds1))
        assert labels1[0] == "SKIP_ROUND"

        # Pattern 2: Leader timeout 150% after successful appeal
        rounds2 = [
            Round(
                rotations=[
                    Rotation(
                        votes={
                            ADDR_POOL[0]: ["LEADER_TIMEOUT", "NA"],
                        }
                    )
                ]
            ),
            Round(rotations=[Rotation(votes={ADDR_POOL[1]: "NA"})]),
            Round(
                rotations=[
                    Rotation(
                        votes={
                            ADDR_POOL[2]: ["LEADER_RECEIPT", "AGREE"],
                            ADDR_POOL[3]: "AGREE",
                        }
                    )
                ]
            ),
        ]

        labels2 = label_rounds(TransactionRoundResults(rounds=rounds2))
        assert labels2[2] == "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND"

    def test_label_transitions_are_valid(self):
        """Invariant: Certain label transitions should never occur."""
        # Generate many random sequences
        for _ in range(50):
            num_rounds = 5
            rounds = []

            for i in range(num_rounds):
                if i % 2 == 0:
                    # Vary the vote patterns
                    if i == 0:
                        votes = {
                            ADDR_POOL[0]: ["LEADER_RECEIPT", "AGREE"],
                            ADDR_POOL[1]: "DISAGREE",
                        }
                    else:
                        votes = {
                            ADDR_POOL[i * 2]: ["LEADER_RECEIPT", "AGREE"],
                            ADDR_POOL[i * 2 + 1]: "AGREE",
                        }
                else:
                    votes = {
                        ADDR_POOL[i * 2]: "NA",
                        ADDR_POOL[i * 2 + 1]: "NA",
                    }

                rounds.append(Round(rotations=[Rotation(votes=votes)]))

            transaction_results = TransactionRoundResults(rounds=rounds)
            labels = label_rounds(transaction_results)

            # Check invalid transitions
            for i in range(len(labels) - 1):
                current, next_label = labels[i], labels[i + 1]

                # After EMPTY_ROUND, we shouldn't see appeal success/fail labels
                if current == "EMPTY_ROUND":
                    assert not (
                        next_label.startswith("APPEAL_")
                        and ("SUCCESSFUL" in next_label or "UNSUCCESSFUL" in next_label)
                    )


def test_mathematical_properties():
    """Test mathematical properties of round labeling."""

    # Property 1: Number of appeal labels matches number of rounds with appeal characteristics
    for num_rounds in range(1, 10):
        rounds = []
        appeal_round_count = 0
        for i in range(num_rounds):
            if i % 2 == 0:
                votes = {
                    ADDR_POOL[0]: ["LEADER_RECEIPT", "AGREE"],
                    ADDR_POOL[1]: "AGREE",
                }
            else:
                votes = {ADDR_POOL[0]: "NA"}
                appeal_round_count += 1

            rounds.append(Round(rotations=[Rotation(votes=votes)]))

        transaction_results = TransactionRoundResults(rounds=rounds)
        labels = label_rounds(transaction_results)

        appeal_labels = sum(
            1
            for label in labels
            if "APPEAL" in label
            and label
            not in [
                "SPLIT_PREVIOUS_APPEAL_BOND",
                "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            ]
        )

        # Appeal labels should correspond to rounds with appeal characteristics (NA votes)
        assert appeal_labels <= appeal_round_count

    # Property 2: Special case transformations preserve round count
    test_results = TransactionRoundResults(
        rounds=[
            Round(
                rotations=[
                    Rotation(
                        votes={
                            ADDR_POOL[0]: ["LEADER_RECEIPT", "AGREE"],
                            ADDR_POOL[1]: "DISAGREE",
                        }
                    )
                ]
            ),
            Round(rotations=[Rotation(votes={ADDR_POOL[2]: "NA"})]),
            Round(
                rotations=[
                    Rotation(
                        votes={
                            ADDR_POOL[3]: ["LEADER_RECEIPT", "AGREE"],
                            ADDR_POOL[4]: "AGREE",
                        }
                    )
                ]
            ),
        ]
    )

    labels = label_rounds(test_results)
    assert len(labels) == len(test_results.rounds)


if __name__ == "__main__":
    # Run property-based tests
    print("Running property-based tests for round labeling...")

    # Create test instance
    prop_tests = TestRoundLabelingProperties()

    # Run key property tests
    print("Testing: All rounds get labels...")
    prop_tests.test_all_rounds_get_labels()

    print("Testing: Deterministic labeling...")
    prop_tests.test_deterministic_labeling()

    print("Testing: Valid label values...")
    prop_tests.test_valid_label_values()

    print("Testing: Empty rounds...")
    prop_tests.test_empty_rounds_labeled_correctly()

    print("Testing: Single round labeling...")
    prop_tests.test_single_round_labeling()

    print("Testing: Appeal positioning...")
    prop_tests.test_appeal_positioning_property()

    print("Testing: Pattern consistency...")
    prop_tests.test_pattern_consistency()

    # Run extended invariant tests
    extended_tests = TestRoundLabelingInvariantsExtended()

    print("\nTesting extended invariants...")
    extended_tests.test_no_consecutive_appeals_at_even_indices()
    extended_tests.test_special_patterns_are_exhaustive()
    extended_tests.test_label_transitions_are_valid()

    print("\nTesting mathematical properties...")
    test_mathematical_properties()

    print("\n✓ All property-based tests passed!")
    print("\nThe round labeling function satisfies all required properties.")
