import pytest
from typing import List, Dict, Set
from src.fee_simulator.core.round_labeling import (
    label_rounds,
    get_leader_action,
    extract_rounds_data,
)
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    Round,
    Rotation,
    TransactionBudget,
    Appeal,
)
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.utils import generate_random_eth_address
from src.fee_simulator.protocol.types import RoundLabel, Vote
from src.fee_simulator.specification.state_machine.path_analysis.round_combinations import (
    generate_all_paths,
    PathConstraints,
    TRANSACTION_GRAPH,
)
from collections import defaultdict
import itertools


# Generate address pool for tests
addresses_pool = [generate_random_eth_address() for _ in range(2000)]


class TestRoundLabelingInvariants:
    """Test invariants that must hold for all round labelings."""

    def test_every_round_has_label(self):
        """Every round must receive exactly one label."""
        # Create various transaction results
        test_cases = [
            # Single round
            TransactionRoundResults(
                rounds=[
                    Round(
                        rotations=[
                            Rotation(
                                votes={
                                    addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                    addresses_pool[1]: "AGREE",
                                }
                            )
                        ]
                    )
                ]
            ),
            # Multiple rounds
            TransactionRoundResults(
                rounds=[
                    Round(
                        rotations=[
                            Rotation(
                                votes={
                                    addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                    addresses_pool[1]: "DISAGREE",
                                }
                            )
                        ]
                    ),
                    Round(
                        rotations=[
                            Rotation(
                                votes={
                                    addresses_pool[2]: "NA",
                                    addresses_pool[3]: "NA",
                                }
                            )
                        ]
                    ),
                    Round(
                        rotations=[
                            Rotation(
                                votes={
                                    addresses_pool[4]: ["LEADER_RECEIPT", "AGREE"],
                                    addresses_pool[5]: "AGREE",
                                }
                            )
                        ]
                    ),
                ]
            ),
        ]

        for transaction_results in test_cases:
            labels = label_rounds(transaction_results)
            assert len(labels) == len(transaction_results.rounds)
            assert all(isinstance(label, str) for label in labels)
            assert all(label != "" for label in labels)

    def test_appeal_rounds_detected_by_pattern(self):
        """Appeal rounds must be detected based on vote patterns, not indices."""
        # Create transaction with appeals at various positions
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Normal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "DISAGREE",
                                addresses_pool[2]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 1: Appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[3]: "NA",
                                addresses_pool[4]: "NA",
                            }
                        )
                    ]
                ),
                # Round 2: Normal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[5]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[6]: "AGREE",
                            }
                        )
                    ]
                ),
                # Round 3: Appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[7]: "NA",
                                addresses_pool[8]: "NA",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)

        # Check that appeals are correctly identified based on vote patterns
        # Round 1 and 3 should be appeals because they have NA votes
        assert (
            "APPEAL" in labels[1]
        ), f"Round 1 with NA votes should be appeal, got {labels[1]}"
        assert (
            "APPEAL" in labels[3]
        ), f"Round 3 with NA votes should be appeal, got {labels[3]}"

        # Rounds 0 and 2 should be normal rounds (have leader receipts)
        assert (
            "APPEAL" not in labels[0]
        ), f"Round 0 with leader receipt should not be appeal, got {labels[0]}"
        assert (
            "APPEAL" not in labels[2]
        ), f"Round 2 with leader receipt should not be appeal, got {labels[2]}"

    def test_deterministic_labeling(self):
        """Same input must always produce same output."""
        transaction_results = TransactionRoundResults(
            rounds=[
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_TIMEOUT", "NA"],
                                addresses_pool[1]: "NA",
                            }
                        )
                    ]
                ),
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[2]: "NA",
                                addresses_pool[3]: "NA",
                            }
                        )
                    ]
                ),
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[4]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[5]: "AGREE",
                            }
                        )
                    ]
                ),
            ]
        )

        # Run labeling multiple times
        results = []
        for _ in range(10):
            labels = label_rounds(transaction_results)
            results.append(labels)

        # All results should be identical
        assert all(result == results[0] for result in results)


class TestSpecificPatterns:
    """Test specific patterns that should result in specific labels."""

    def test_single_leader_timeout(self):
        """Single leader timeout should be labeled LEADER_TIMEOUT_50_PERCENT."""
        transaction_results = TransactionRoundResults(
            rounds=[
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_TIMEOUT", "NA"],
                                addresses_pool[1]: "NA",
                            }
                        )
                    ]
                )
            ]
        )

        labels = label_rounds(transaction_results)
        assert labels == ["LEADER_TIMEOUT_50_PERCENT"]

    def test_skip_round_pattern(self):
        """Normal round before successful appeal should become SKIP_ROUND."""
        # Pattern: NORMAL_ROUND -> APPEAL_LEADER_SUCCESSFUL -> NORMAL_ROUND
        transaction_results = TransactionRoundResults(
            rounds=[
                # Normal round (undetermined)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "DISAGREE",
                                addresses_pool[3]: "DISAGREE",
                                addresses_pool[4]: "TIMEOUT",
                            }
                        )
                    ]
                ),
                # Appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[5]: "NA",
                                addresses_pool[6]: "NA",
                            }
                        )
                    ]
                ),
                # Normal round with majority
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[7]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[8]: "AGREE",
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "DISAGREE",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)
        assert labels[0] == "SKIP_ROUND"
        assert labels[1] == "APPEAL_LEADER_SUCCESSFUL"
        assert labels[2] == "NORMAL_ROUND"

    def test_leader_timeout_150_pattern(self):
        """Leader timeout + successful appeal + normal should trigger special labeling."""
        transaction_results = TransactionRoundResults(
            rounds=[
                # Leader timeout
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_TIMEOUT", "NA"],
                                addresses_pool[1]: "NA",
                            }
                        )
                    ]
                ),
                # Appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[2]: "NA",
                                addresses_pool[3]: "NA",
                            }
                        )
                    ]
                ),
                # Normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[4]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)
        assert labels[0] == "SKIP_ROUND"
        assert labels[1] == "APPEAL_LEADER_TIMEOUT_SUCCESSFUL"
        assert labels[2] == "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND"

    def test_split_appeal_bond_pattern(self):
        """Unsuccessful appeal followed by undetermined round should split bond."""
        transaction_results = TransactionRoundResults(
            rounds=[
                # Normal round (majority agree)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Appeal (validators still agree)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[4]: "AGREE",
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Normal round (undetermined)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[8]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "DISAGREE",
                                addresses_pool[11]: "DISAGREE",
                                addresses_pool[12]: "TIMEOUT",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)
        assert labels[0] == "NORMAL_ROUND"
        assert labels[1] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert labels[2] == "SPLIT_PREVIOUS_APPEAL_BOND"


class TestChainedUnsuccessfulAppeals:
    """Test cases for chained unsuccessful appeals - critical edge case."""

    def test_double_unsuccessful_validator_appeals(self):
        """Test that consecutive unsuccessful validator appeals are labeled correctly."""
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Normal round with majority
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 1: First unsuccessful appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[4]: "AGREE",
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 2: Normal round (not split because not undetermined)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[8]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "AGREE",
                                addresses_pool[11]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 3: Second unsuccessful appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[12]: "AGREE",
                                addresses_pool[13]: "AGREE",
                                addresses_pool[14]: "AGREE",
                                addresses_pool[15]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 4: Normal round undetermined (should trigger split)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[16]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[17]: "AGREE",
                                addresses_pool[18]: "DISAGREE",
                                addresses_pool[19]: "DISAGREE",
                                addresses_pool[20]: "TIMEOUT",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)

        assert labels[0] == "NORMAL_ROUND"
        assert labels[1] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert labels[2] == "NORMAL_ROUND"
        assert labels[3] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
        assert labels[4] == "SPLIT_PREVIOUS_APPEAL_BOND"

    def test_chained_leader_timeout_appeals(self):
        """Test chained unsuccessful leader timeout appeals."""
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Leader timeout
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_TIMEOUT", "NA"],
                                addresses_pool[1]: "NA",
                            }
                        )
                    ]
                ),
                # Round 1: Unsuccessful appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[2]: "NA",
                                addresses_pool[3]: "NA",
                            }
                        )
                    ]
                ),
                # Round 2: Another leader timeout
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[4]: ["LEADER_TIMEOUT", "NA"],
                                addresses_pool[5]: "NA",
                            }
                        )
                    ]
                ),
            ]
        )

        labels = label_rounds(transaction_results)

        assert labels[0] == "LEADER_TIMEOUT_50_PERCENT"  # First leader timeout gets 50%
        assert labels[1] == "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL"
        assert labels[2] == "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND"


class TestRoundCombinations:
    """Test round labeling with various combinations generated from the transaction graph."""

    def create_transaction_from_path(self, path: List[str]) -> TransactionRoundResults:
        """Convert a path from the transaction graph into TransactionRoundResults."""
        rounds = []
        appeal_count = 0
        address_offset = 0

        for i in range(len(path)):
            node = path[i]

            if node in ["START", "END"]:
                continue

            # Create rotation based on node type
            if "LEADER_TIMEOUT" in node and "APPEAL" not in node:
                # Leader timeout round
                rotation = Rotation(
                    votes={
                        addresses_pool[address_offset]: ["LEADER_TIMEOUT", "NA"],
                        addresses_pool[address_offset + 1]: "NA",
                        addresses_pool[address_offset + 2]: "NA",
                        addresses_pool[address_offset + 3]: "NA",
                        addresses_pool[address_offset + 4]: "NA",
                    }
                )
                rounds.append(Round(rotations=[rotation]))
                address_offset += 5

            elif "APPEAL" in node:
                # Appeal round
                appeal_count += 1
                num_validators = 5 + appeal_count * 2  # Grows with each appeal
                votes = {}

                # Determine votes based on appeal type
                if "VALIDATOR_APPEAL" in node:
                    vote_type = "DISAGREE" if "SUCCESSFUL" in node else "AGREE"
                else:  # LEADER_APPEAL
                    vote_type = "NA"

                for j in range(num_validators):
                    votes[addresses_pool[address_offset + j]] = vote_type

                rotation = Rotation(votes=votes)
                rounds.append(Round(rotations=[rotation]))
                address_offset += num_validators

            else:
                # Normal round
                votes = {}

                # First address is leader
                if "MAJORITY_AGREE" in node:
                    votes[addresses_pool[address_offset]] = ["LEADER_RECEIPT", "AGREE"]
                    for j in range(1, 5):
                        votes[addresses_pool[address_offset + j]] = "AGREE"

                elif "MAJORITY_DISAGREE" in node:
                    votes[addresses_pool[address_offset]] = ["LEADER_RECEIPT", "AGREE"]
                    votes[addresses_pool[address_offset + 1]] = "AGREE"
                    for j in range(2, 5):
                        votes[addresses_pool[address_offset + j]] = "DISAGREE"

                elif "MAJORITY_TIMEOUT" in node:
                    votes[addresses_pool[address_offset]] = ["LEADER_RECEIPT", "AGREE"]
                    votes[addresses_pool[address_offset + 1]] = "AGREE"
                    for j in range(2, 5):
                        votes[addresses_pool[address_offset + j]] = "TIMEOUT"

                elif "UNDETERMINED" in node:
                    votes[addresses_pool[address_offset]] = ["LEADER_RECEIPT", "AGREE"]
                    votes[addresses_pool[address_offset + 1]] = "AGREE"
                    votes[addresses_pool[address_offset + 2]] = "DISAGREE"
                    votes[addresses_pool[address_offset + 3]] = "DISAGREE"
                    votes[addresses_pool[address_offset + 4]] = "TIMEOUT"

                else:
                    # Default case
                    votes[addresses_pool[address_offset]] = ["LEADER_RECEIPT", "AGREE"]
                    for j in range(1, 5):
                        votes[addresses_pool[address_offset + j]] = "AGREE"

                rotation = Rotation(votes=votes)
                rounds.append(Round(rotations=[rotation]))
                address_offset += 5

        return TransactionRoundResults(rounds=rounds)

    def test_sample_paths_from_graph(self):
        """Test labeling with sample paths from the transaction graph."""
        constraints = PathConstraints(
            min_length=3, max_length=7, source_node="START", target_node="END"
        )

        # Generate sample paths
        paths = generate_all_paths(TRANSACTION_GRAPH, constraints)

        # Test a subset of paths
        sample_size = min(50, len(paths))
        sample_paths = paths[:sample_size]

        label_counts = defaultdict(int)
        pattern_counts = defaultdict(int)

        for path in sample_paths:
            # Convert path to transaction results
            transaction_results = self.create_transaction_from_path(path)

            # Label rounds
            labels = label_rounds(transaction_results)

            # Verify basic invariants
            assert len(labels) == len(transaction_results.rounds)

            # Count label occurrences
            for label in labels:
                label_counts[label] += 1

            # Count patterns
            label_str = " -> ".join(labels)
            pattern_counts[label_str] += 1

            # Verify that appeal labels correspond to appeal rounds in the transaction
            for i, label in enumerate(labels):
                if "APPEAL" in label and label not in [
                    "SPLIT_PREVIOUS_APPEAL_BOND",
                    "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
                ]:
                    # Verify this round has appeal characteristics (NA votes, etc)
                    round_obj = transaction_results.rounds[i]
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
                        assert (
                            has_na_votes or not has_leader_receipt
                        ), f"Appeal label {label} at index {i} but round doesn't have appeal characteristics"

        # Ensure we've seen various label types
        assert len(label_counts) > 5, "Should see variety of labels"
        assert "NORMAL_ROUND" in label_counts or "SKIP_ROUND" in label_counts

        # Print statistics for debugging
        print(f"\nTested {sample_size} paths")
        print(f"Unique labels seen: {sorted(label_counts.keys())}")
        print(
            f"Most common patterns: {sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:5]}"
        )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_rounds(self):
        """Test handling of empty rounds."""
        transaction_results = TransactionRoundResults(
            rounds=[
                Round(rotations=[Rotation(votes={})]),
            ]
        )

        labels = label_rounds(transaction_results)
        assert labels == ["EMPTY_ROUND"]

    def test_mixed_empty_and_normal_rounds(self):
        """Test mix of empty and normal rounds."""
        transaction_results = TransactionRoundResults(
            rounds=[
                Round(rotations=[Rotation(votes={})]),
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                            }
                        )
                    ]
                ),
                Round(rotations=[Rotation(votes={})]),
            ]
        )

        labels = label_rounds(transaction_results)
        assert labels[0] == "EMPTY_ROUND"
        assert labels[1] in [
            "NORMAL_ROUND",
            "APPEAL_LEADER_SUCCESSFUL",
            "APPEAL_LEADER_UNSUCCESSFUL",
            "APPEAL_VALIDATOR_SUCCESSFUL",
            "APPEAL_VALIDATOR_UNSUCCESSFUL",
        ]
        assert labels[2] == "EMPTY_ROUND"

    def test_complex_vote_formats(self):
        """Test handling of complex vote formats with hashes."""
        transaction_results = TransactionRoundResults(
            rounds=[
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: [
                                    "LEADER_RECEIPT",
                                    "AGREE",
                                    "0x1234567890abcdef",  # Valid hex format
                                ],
                                addresses_pool[1]: ["AGREE", "0x1234567890abcdef"],
                                addresses_pool[2]: ["DISAGREE", "0xfedcba9876543210"],
                            }
                        )
                    ]
                )
            ]
        )

        labels = label_rounds(transaction_results)
        assert len(labels) == 1
        assert labels[0] == "NORMAL_ROUND"


class TestIntegrationWithFeeDistribution:
    """Test that labeled rounds work correctly with fee distribution."""

    def test_labeled_rounds_process_correctly(self):
        """Ensure labeled rounds can be processed by fee distribution system."""
        # Create a complex scenario
        sender_address = addresses_pool[1999]
        appealant_address = addresses_pool[1998]

        transaction_budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=1,
            rotations=[0, 0],
            senderAddress=sender_address,
            appeals=[Appeal(appealantAddress=appealant_address)],
            staking_distribution="constant",
        )

        transaction_results = TransactionRoundResults(
            rounds=[
                # Normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "DISAGREE",
                                addresses_pool[3]: "DISAGREE",
                                addresses_pool[4]: "TIMEOUT",
                            }
                        )
                    ]
                ),
                # Appeal
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[5]: "NA",
                                addresses_pool[6]: "NA",
                                addresses_pool[7]: "NA",
                            }
                        )
                    ]
                ),
                # Normal round
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[8]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "AGREE",
                                addresses_pool[11]: "DISAGREE",
                            }
                        )
                    ]
                ),
            ]
        )

        # Process transaction (this will call label_rounds internally)
        fee_events, round_labels = process_transaction(
            addresses_pool, transaction_results, transaction_budget
        )

        # Verify labeling
        assert len(round_labels) == 3
        assert round_labels[0] in ["SKIP_ROUND", "NORMAL_ROUND"]
        assert "APPEAL" in round_labels[1]
        assert round_labels[2] in [
            "NORMAL_ROUND",
            "SPLIT_PREVIOUS_APPEAL_BOND",
            "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND",
        ]

        # Verify fee events were created for each round
        round_indices = {
            event.round_index for event in fee_events if event.round_index is not None
        }
        assert 0 in round_indices or round_labels[0] == "SKIP_ROUND"
        assert 1 in round_indices
        assert 2 in round_indices


def test_all_valid_label_values():
    """Ensure all labels produced are valid RoundLabel values."""
    from src.fee_simulator.protocol.types import RoundLabel

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

    # Generate various test cases
    test_cases = []

    # Add specific patterns
    test_cases.extend(
        [
            # Single round cases
            TransactionRoundResults(
                rounds=[
                    Round(
                        rotations=[
                            Rotation(
                                votes={
                                    addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                    addresses_pool[1]: "AGREE",
                                }
                            )
                        ]
                    )
                ]
            ),
            TransactionRoundResults(
                rounds=[
                    Round(
                        rotations=[
                            Rotation(
                                votes={
                                    addresses_pool[0]: ["LEADER_TIMEOUT", "NA"],
                                    addresses_pool[1]: "NA",
                                }
                            )
                        ]
                    )
                ]
            ),
            # Multi-round cases
            TransactionRoundResults(
                rounds=[
                    Round(
                        rotations=[
                            Rotation(
                                votes={
                                    addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                    addresses_pool[1]: "DISAGREE",
                                }
                            )
                        ]
                    ),
                    Round(
                        rotations=[
                            Rotation(
                                votes={
                                    addresses_pool[2]: "NA",
                                }
                            )
                        ]
                    ),
                ]
            ),
        ]
    )

    # Test all cases
    for transaction_results in test_cases:
        labels = label_rounds(transaction_results)
        for label in labels:
            assert label in valid_labels, f"Invalid label produced: {label}"


if __name__ == "__main__":
    # Run a quick validation
    print("Running round labeling validation...")

    # Test basic invariants
    test_invariants = TestRoundLabelingInvariants()
    test_invariants.test_every_round_has_label()
    test_invariants.test_appeal_rounds_detected_by_pattern()
    test_invariants.test_deterministic_labeling()
    print("✓ Invariant tests passed")

    # Test specific patterns
    test_patterns = TestSpecificPatterns()
    test_patterns.test_single_leader_timeout()
    test_patterns.test_skip_round_pattern()
    test_patterns.test_leader_timeout_150_pattern()
    test_patterns.test_split_appeal_bond_pattern()
    print("✓ Pattern tests passed")

    # Test with generated combinations
    test_combinations = TestRoundCombinations()
    test_combinations.test_sample_paths_from_graph()
    print("✓ Combination tests passed")

    # Test edge cases
    test_edges = TestEdgeCases()
    test_edges.test_empty_rounds()
    test_edges.test_mixed_empty_and_normal_rounds()
    test_edges.test_complex_vote_formats()
    print("✓ Edge case tests passed")

    # Test integration
    test_integration = TestIntegrationWithFeeDistribution()
    test_integration.test_labeled_rounds_process_correctly()
    print("✓ Integration tests passed")

    # Test all valid labels
    test_all_valid_label_values()
    print("✓ Label validation passed")

    print("\nAll round labeling tests completed successfully!")
