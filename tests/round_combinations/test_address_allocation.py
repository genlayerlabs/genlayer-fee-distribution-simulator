#!/usr/bin/env python3
"""Test address allocation logic for path_to_transaction with the new algorithm."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fee_simulator.core.path_to_transaction import path_to_transaction_results
from fee_simulator.utils import generate_random_eth_address
from fee_simulator.constants import NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES
from fee_simulator.core.round_labeling import label_rounds


class TestAddressAllocation:
    """Test the new address allocation algorithm."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data."""
        # Generate a pool of real addresses
        self.addresses = [generate_random_eth_address() for i in range(1000)]
        # For debugging, create a mapping to simple indices
        self.address_to_index = {addr: i for i, addr in enumerate(self.addresses)}
        self.sender_address = self.addresses[-1]
        self.appealant_address = self.addresses[-2]

    def get_round_indices(self, round_obj):
        """Get the indices of addresses used in a round."""
        if not round_obj.rotations:
            return []
        votes = round_obj.rotations[0].votes
        return sorted([self.address_to_index[addr] for addr in votes.keys()])

    def get_leader_index(self, round_obj):
        """Get the leader index for a round."""
        if not round_obj.rotations:
            return None
        votes = round_obj.rotations[0].votes
        for addr, vote in votes.items():
            if isinstance(vote, list) and (
                "LEADER_RECEIPT" in vote or "LEADER_TIMEOUT" in vote
            ):
                return self.address_to_index[addr]
        return None

    def test_simple_path_normal_appeal_normal(self):
        """Test: Normal → Appeal → Normal"""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]

        result, _ = path_to_transaction_results(
            path=path,
            addresses=self.addresses,
            sender_address=self.sender_address,
            appealant_address=self.appealant_address,
        )

        # Round 0: Normal, size 5, addresses [0-4]
        round0_indices = self.get_round_indices(result.rounds[0])
        assert len(round0_indices) == 5, f"Round 0 should have 5 addresses"
        assert min(round0_indices) == 0 and max(round0_indices) == 4
        leader0 = self.get_leader_index(result.rounds[0])

        # Round 1: Appeal, size 7, new addresses
        round1_indices = self.get_round_indices(result.rounds[1])
        assert len(round1_indices) == 7, f"Round 1 should have 7 addresses"
        assert all(
            idx not in round0_indices for idx in round1_indices
        ), "Appeal should use new addresses"

        # Round 2: Normal, size 11, cumulative minus previous leaders
        round2_indices = self.get_round_indices(result.rounds[2])
        assert len(round2_indices) == 11, f"Round 2 should have 11 addresses"
        assert (
            leader0 not in round2_indices
        ), f"Round 2 should exclude leader from round 0"

        # Check cumulative usage
        all_used = set(round0_indices + round1_indices)
        assert all(
            idx in all_used or idx >= max(all_used) for idx in round2_indices
        ), "Round 2 should use cumulative addresses or new ones"

    def test_consecutive_unsuccessful_appeals(self):
        """Test: Normal → Unsuccessful Appeal → Unsuccessful Appeal → Successful Appeal"""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "END",
        ]

        result, _ = path_to_transaction_results(
            path=path,
            addresses=self.addresses,
            sender_address=self.sender_address,
            appealant_address=self.appealant_address,
        )

        # Round 0: Normal, size 5
        assert len(self.get_round_indices(result.rounds[0])) == 5

        # Round 1: Appeal 0, size 7
        assert len(self.get_round_indices(result.rounds[1])) == 7

        # Round 2: Appeal 1 after unsuccessful, size 13-2=11
        assert len(self.get_round_indices(result.rounds[2])) == 11

        # Round 3: Appeal 2 after unsuccessful, size 25-2=23
        assert len(self.get_round_indices(result.rounds[3])) == 23

        # All appeals should use fresh addresses
        all_indices = set()
        for i in range(4):
            round_indices = set(self.get_round_indices(result.rounds[i]))
            # Check no overlap with previous rounds
            assert len(round_indices & all_indices) == 0, f"Round {i} reuses addresses"
            all_indices.update(round_indices)

    def test_normal_rounds_leader_rotation(self):
        """Test: Multiple normal rounds with leader rotation"""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]

        result, _ = path_to_transaction_results(
            path=path,
            addresses=self.addresses,
            sender_address=self.sender_address,
            appealant_address=self.appealant_address,
        )

        # Check that each round has a leader and leaders are different
        leaders = []
        for i in range(4):
            leader = self.get_leader_index(result.rounds[i])
            assert leader is not None, f"Round {i} should have a leader"
            leaders.append(leader)

        # All leaders should be different
        assert len(set(leaders)) == len(
            leaders
        ), "Each round should have a different leader"

        # Check that previous leaders are excluded from subsequent rounds
        for i in range(1, 4):
            round_indices = self.get_round_indices(result.rounds[i])
            # Previous leaders should not be in the round
            for prev_leader in leaders[:i]:
                assert (
                    prev_leader not in round_indices
                ), f"Round {i} includes previous leader {prev_leader}"

    def test_address_pool_exhaustion(self):
        """Test: 8 consecutive unsuccessful appeals (should exhaust pool)"""
        path = (
            ["START", "LEADER_RECEIPT_MAJORITY_AGREE"]
            + ["VALIDATOR_APPEAL_UNSUCCESSFUL"] * 7
            + ["VALIDATOR_APPEAL_SUCCESSFUL", "END"]
        )

        result, _ = path_to_transaction_results(
            path=path,
            addresses=self.addresses,
            sender_address=self.sender_address,
            appealant_address=self.appealant_address,
        )

        # Calculate expected sizes
        expected_sizes = [
            5,  # Normal
            7,  # Appeal 0
            11,  # Appeal 1 (13-2)
            23,  # Appeal 2 (25-2)
            47,  # Appeal 3 (49-2)
            95,  # Appeal 4 (97-2)
            191,  # Appeal 5 (193-2)
            383,  # Appeal 6 (385-2)
            # Appeal 7 should be 767 (769-2) but pool might be exhausted
        ]

        total_used = 0
        for i in range(len(expected_sizes)):
            round_size = len(self.get_round_indices(result.rounds[i]))
            total_used += round_size
            assert round_size == expected_sizes[i], f"Round {i} size mismatch"

        # Last appeal should use remaining addresses
        last_round_size = len(self.get_round_indices(result.rounds[8]))
        assert (
            last_round_size <= 1000 - total_used
        ), "Last round exceeds available addresses"
        assert last_round_size > 0, "Last round should have some addresses"

    def test_normal_after_exhaustive_appeals(self):
        """Test: Normal round after appeals consume most addresses"""
        path = (
            ["START", "LEADER_RECEIPT_MAJORITY_AGREE"]
            + ["VALIDATOR_APPEAL_UNSUCCESSFUL"] * 7
            + ["VALIDATOR_APPEAL_SUCCESSFUL", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        )

        result, _ = path_to_transaction_results(
            path=path,
            addresses=self.addresses,
            sender_address=self.sender_address,
            appealant_address=self.appealant_address,
        )

        # Last round should be normal
        last_round = result.rounds[-1]
        last_indices = self.get_round_indices(last_round)

        # Should exclude the first leader
        first_leader = self.get_leader_index(result.rounds[0])
        assert (
            first_leader not in last_indices
        ), "Final normal round should exclude first leader"

        # Size should be appropriate for the blockchain index
        # After 8 appeals, blockchain index is 16, so size should be min(1000, available)
        assert len(last_indices) > 0, "Final round should have participants"

    def test_mixed_pattern_with_alternating(self):
        """Test: N → A → N → A → N (alternating pattern)"""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]

        result, _ = path_to_transaction_results(
            path=path,
            addresses=self.addresses,
            sender_address=self.sender_address,
            appealant_address=self.appealant_address,
        )

        # Round 0: Normal, size 5
        assert len(self.get_round_indices(result.rounds[0])) == 5
        leader0 = self.get_leader_index(result.rounds[0])

        # Round 1: Appeal 0, size 7, new addresses
        assert len(self.get_round_indices(result.rounds[1])) == 7

        # Round 2: Normal, size 11 (blockchain index 2)
        round2_indices = self.get_round_indices(result.rounds[2])
        assert len(round2_indices) == 11
        assert leader0 not in round2_indices, "Should exclude first leader"

        # Round 3: Appeal 1, size 13, new addresses
        assert len(self.get_round_indices(result.rounds[3])) == 13

        # Round 4: Normal, size 23 (blockchain index 4)
        round4_indices = self.get_round_indices(result.rounds[4])
        assert len(round4_indices) == 23
        # Should exclude both previous leaders
        leader2 = self.get_leader_index(result.rounds[2])
        assert leader0 not in round4_indices and leader2 not in round4_indices

    def test_removed_addresses_handling(self):
        """Test: Address allocation with removed (slashed/idle) addresses"""
        # Simulate some addresses being removed
        removed = set(self.addresses[2:5])  # Remove indices 2, 3, 4

        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]

        result, _ = path_to_transaction_results(
            path=path,
            addresses=self.addresses,
            sender_address=self.sender_address,
            appealant_address=self.appealant_address,
            removed_addresses=removed,
        )

        # Round 0: Should skip removed addresses
        round0_indices = self.get_round_indices(result.rounds[0])
        assert 2 not in round0_indices
        assert 3 not in round0_indices
        assert 4 not in round0_indices
        assert len(round0_indices) == 5  # Should still have 5 addresses

        # Round 1: Should also skip removed addresses
        round1_indices = self.get_round_indices(result.rounds[1])
        for idx in [2, 3, 4]:
            assert idx not in round1_indices

    def test_edge_case_small_address_pool(self):
        """Test: Edge case with very small address pool"""
        # Use a small address pool to test edge cases
        small_addresses = self.addresses[:50]  # Only 50 addresses

        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "END",
        ]

        result, _ = path_to_transaction_results(
            path=path,
            addresses=small_addresses,
            sender_address=small_addresses[-1],
            appealant_address=small_addresses[-2],
        )

        # Check that rounds have appropriate sizes
        # Round 0: Normal, size 5
        assert len(self.get_round_indices(result.rounds[0])) == 5

        # Round 1: Appeal, size 7
        assert len(self.get_round_indices(result.rounds[1])) == 7

        # Round 2: Appeal after unsuccessful, size 11
        assert len(self.get_round_indices(result.rounds[2])) == 11

        # Total used: 5 + 7 + 11 = 23, which is less than 48 available (50 - 2 for sender/appealant)
        total_used = sum(
            len(self.get_round_indices(result.rounds[i])) for i in range(3)
        )
        assert total_used <= 48, "Should not exceed available addresses"

    def test_all_appeal_types(self):
        """Test: Different appeal types (leader vs validator, successful vs unsuccessful)"""
        paths = [
            # Leader appeals
            ["START", "LEADER_TIMEOUT", "LEADER_APPEAL_TIMEOUT_SUCCESSFUL", "END"],
            ["START", "LEADER_TIMEOUT", "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL", "END"],
            # Validator appeals
            [
                "START",
                "LEADER_RECEIPT_MAJORITY_AGREE",
                "VALIDATOR_APPEAL_SUCCESSFUL",
                "END",
            ],
            [
                "START",
                "LEADER_RECEIPT_MAJORITY_AGREE",
                "VALIDATOR_APPEAL_UNSUCCESSFUL",
                "END",
            ],
        ]

        for path in paths:
            result, _ = path_to_transaction_results(
                path=path,
                addresses=self.addresses,
                sender_address=self.sender_address,
                appealant_address=self.appealant_address,
            )

            # All should create valid rounds
            assert len(result.rounds) == len(path) - 2

            # Appeals should use new addresses
            if len(result.rounds) > 1:
                round0_indices = set(self.get_round_indices(result.rounds[0]))
                round1_indices = set(self.get_round_indices(result.rounds[1]))
                assert (
                    len(round0_indices & round1_indices) == 0
                ), f"Appeal reuses addresses for path {path}"

    def test_blockchain_index_calculation(self):
        """Test: Verify blockchain index calculation affects round sizes correctly"""
        # Path with specific appeal pattern to test blockchain indices
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",  # Round 0, blockchain index 0
            "VALIDATOR_APPEAL_SUCCESSFUL",  # Round 1, blockchain index 1
            "VALIDATOR_APPEAL_SUCCESSFUL",  # Round 2, blockchain index 3
            "LEADER_RECEIPT_MAJORITY_AGREE",  # Round 3, blockchain index 4
            "END",
        ]

        result, _ = path_to_transaction_results(
            path=path,
            addresses=self.addresses,
            sender_address=self.sender_address,
            appealant_address=self.appealant_address,
        )

        # Check sizes match blockchain indices
        sizes = [len(self.get_round_indices(result.rounds[i])) for i in range(4)]

        # Round 0: blockchain index 0 → size 5
        assert sizes[0] == NORMAL_ROUND_SIZES[0]  # 5

        # Round 1: appeal 0 → size 7
        assert sizes[1] == APPEAL_ROUND_SIZES[0]  # 7

        # Round 2: appeal 1 → size 13
        assert sizes[2] == APPEAL_ROUND_SIZES[1]  # 13

        # Round 3: blockchain index 4 → size 23
        assert sizes[3] == NORMAL_ROUND_SIZES[2]  # 23


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
