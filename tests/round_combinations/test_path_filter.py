#!/usr/bin/env python3
"""Test suite for path_filter.py"""

import pytest
from src.fee_simulator.specification.state_machine.path_analysis.path_filter import (
    is_valid_path,
    filter_valid_paths,
    get_path_statistics,
    find_max_appeal_chain_length,
    analyze_path_distribution,
    AddressAllocationState,
    get_normal_round_size,
    get_appeal_round_size,
)


class TestPathFilter:
    """Test the path filtering logic."""

    def test_simple_valid_path(self):
        """Test a simple valid path."""
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        assert is_valid_path(path) is True

        stats = get_path_statistics(path)
        assert stats is not None
        assert stats["total_addresses_used"] == 5  # First normal round uses 5
        assert stats["normal_rounds"] == 1
        assert stats["appeal_rounds"] == 0

    def test_path_with_single_appeal(self):
        """Test path with one appeal."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]
        assert is_valid_path(path) is True

        stats = get_path_statistics(path)
        assert stats is not None
        assert stats["total_addresses_used"] == 5 + 7  # Normal(5) + Appeal(7)
        assert stats["normal_rounds"] == 2
        assert stats["appeal_rounds"] == 1

    def test_consecutive_unsuccessful_appeals(self):
        """Test consecutive unsuccessful appeals with size reduction."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "END",
        ]
        assert is_valid_path(path) is True

        stats = get_path_statistics(path)
        assert stats is not None

        # Check round sizes
        rounds = stats["round_details"]
        assert rounds[0]["size"] == 5  # Normal
        assert rounds[1]["size"] == 7  # Appeal 0
        assert rounds[2]["size"] == 11  # Appeal 1 after unsuccessful (13-2)
        assert rounds[3]["size"] == 23  # Appeal 2 after unsuccessful (25-2)

        total_expected = 5 + 7 + 11 + 23
        assert stats["total_addresses_used"] == total_expected

    def test_maximum_appeal_chain(self):
        """Test finding the maximum consecutive appeal chain."""
        max_chain = find_max_appeal_chain_length()

        # With 1000 addresses, we should be able to do quite a few appeals
        assert max_chain >= 7  # Should handle at least 7 consecutive appeals

        # Verify that max_chain appeals work
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE"]
        path.extend(["VALIDATOR_APPEAL_UNSUCCESSFUL"] * max_chain)
        path.append("END")
        assert is_valid_path(path) is True

        # But one more should fail
        path_too_long = ["START", "LEADER_RECEIPT_MAJORITY_AGREE"]
        path_too_long.extend(["VALIDATOR_APPEAL_UNSUCCESSFUL"] * (max_chain + 1))
        path_too_long.append("END")
        assert is_valid_path(path_too_long) is False

    def test_normal_round_leader_exclusion(self):
        """Test that normal rounds exclude previous leaders."""
        # Valid path: normal -> appeal -> normal -> appeal -> normal
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]
        assert is_valid_path(path) is True

        stats = get_path_statistics(path)
        assert stats is not None
        assert stats["normal_rounds"] == 3
        assert stats["appeal_rounds"] == 2

        # Check normal round sizes
        rounds = stats["round_details"]
        normal_rounds = [r for r in rounds if r["type"] == "normal"]
        assert normal_rounds[0]["size"] == 5  # normal round 0
        assert normal_rounds[1]["size"] == 11  # normal round 1
        assert normal_rounds[2]["size"] == 23  # normal round 2

    def test_mixed_appeals_and_normals(self):
        """Test alternating normal and appeal rounds."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]
        assert is_valid_path(path) is True

        stats = get_path_statistics(path)
        assert stats is not None
        assert stats["normal_rounds"] == 3
        assert stats["appeal_rounds"] == 2

        # Check sizes
        rounds = stats["round_details"]
        assert rounds[0]["size"] == 5  # Normal 0
        assert rounds[1]["size"] == 7  # Appeal 0
        assert rounds[2]["size"] == 11  # Normal 1
        assert rounds[3]["size"] == 13  # Appeal 1
        assert rounds[4]["size"] == 23  # Normal 2

    def test_filter_valid_paths(self):
        """Test filtering a list of paths."""
        paths = [
            ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"],
            ["START", "LEADER_RECEIPT_MAJORITY_AGREE"]
            + ["VALIDATOR_APPEAL_UNSUCCESSFUL"] * 10
            + ["END"],  # Too many appeals
            ["START", "LEADER_TIMEOUT", "LEADER_APPEAL_TIMEOUT_SUCCESSFUL", "END"],
        ]

        valid = filter_valid_paths(paths)
        assert len(valid) == 2  # First and third paths should be valid
        assert paths[1] not in valid  # The path with 10 appeals should be filtered out

    def test_small_address_pool(self):
        """Test with a smaller address pool."""
        # With only 50 addresses, we can't do as many appeals
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "END",
        ]

        # Should work with 50 addresses (5 + 7 + 11 = 23)
        assert is_valid_path(path, max_addresses=50) is True

        # But adding one more appeal should fail
        path_longer = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "END",
        ]
        # Would need 5 + 7 + 11 + 23 = 46, which fits in 50
        assert is_valid_path(path_longer, max_addresses=50) is True

        # But adding one more appeal should fail
        path_even_longer = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "END",
        ]
        # Would need 5 + 7 + 11 + 23 + 47 = 93, which exceeds 50
        assert is_valid_path(path_even_longer, max_addresses=50) is False

    def test_path_statistics_details(self):
        """Test detailed path statistics."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]

        stats = get_path_statistics(path)
        assert stats is not None

        # Check round details
        rounds = stats["round_details"]
        assert len(rounds) == 4

        # First round: normal
        assert rounds[0]["node"] == "LEADER_RECEIPT_MAJORITY_AGREE"
        assert rounds[0]["type"] == "normal"
        assert rounds[0]["size"] == 5
        assert rounds[0]["new_addresses"] == 5

        # Second round: unsuccessful appeal
        assert rounds[1]["node"] == "VALIDATOR_APPEAL_UNSUCCESSFUL"
        assert rounds[1]["type"] == "appeal"
        assert rounds[1]["size"] == 7
        assert rounds[1]["is_unsuccessful"] is True

        # Third round: successful appeal after unsuccessful
        assert rounds[2]["node"] == "VALIDATOR_APPEAL_SUCCESSFUL"
        assert rounds[2]["type"] == "appeal"
        assert rounds[2]["size"] == 11  # 13-2 due to previous unsuccessful
        assert rounds[2]["is_unsuccessful"] is False

        # Fourth round: normal
        assert rounds[3]["node"] == "LEADER_RECEIPT_MAJORITY_AGREE"
        assert rounds[3]["type"] == "normal"
        # This is the second normal round, so size should be 11
        assert rounds[3]["size"] == 11
        # It reuses addresses from cumulative pool (excluding first leader), so new_addresses might be 0
        assert rounds[3]["new_addresses"] >= 0

    def test_analyze_path_distribution(self):
        """Test path distribution analysis."""
        paths = [
            ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"],
            [
                "START",
                "LEADER_RECEIPT_MAJORITY_AGREE",
                "VALIDATOR_APPEAL_SUCCESSFUL",
                "END",
            ],
            ["START", "LEADER_RECEIPT_MAJORITY_AGREE"]
            + ["VALIDATOR_APPEAL_UNSUCCESSFUL"] * 20
            + ["END"],  # Invalid
            ["START", "LEADER_TIMEOUT", "END"],
        ]

        analysis = analyze_path_distribution(paths)

        assert analysis["total_paths"] == 4
        assert analysis["valid_paths"] == 3
        assert analysis["invalid_paths"] == 1
        assert analysis["validity_rate"] == 0.75

        # Check distribution by length
        assert 2 in analysis["valid_by_length"]  # Paths with 2 edges
        assert 3 in analysis["valid_by_length"]  # Paths with 3 edges

        # Check address usage stats
        assert analysis["address_usage"]["min"] == 5  # Minimum from simple path
        assert analysis["address_usage"]["max"] >= 5  # At least 5
        assert analysis["address_usage"]["average"] > 0

    def test_edge_cases(self):
        """Test various edge cases."""
        # Empty path
        assert is_valid_path([]) is True

        # Just START
        assert is_valid_path(["START"]) is True

        # Just START and END
        assert is_valid_path(["START", "END"]) is True

        # Path without START (should still work)
        assert is_valid_path(["LEADER_RECEIPT_MAJORITY_AGREE", "END"]) is True

    def test_all_appeal_types(self):
        """Test different types of appeals."""
        appeal_types = [
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "LEADER_APPEAL_SUCCESSFUL",
            "LEADER_APPEAL_UNSUCCESSFUL",
            "LEADER_APPEAL_TIMEOUT_SUCCESSFUL",
            "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL",
        ]

        for appeal in appeal_types:
            path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", appeal, "END"]
            assert is_valid_path(path) is True, f"Path with {appeal} should be valid"

            stats = get_path_statistics(path)
            assert stats is not None
            assert stats["appeal_rounds"] == 1

    def test_round_size_functions(self):
        """Test the round size calculation functions."""
        state = AddressAllocationState()

        # Test normal round sizes
        assert get_normal_round_size(state) == 5
        state.normal_count = 1
        assert get_normal_round_size(state) == 11
        state.normal_count = 2
        assert get_normal_round_size(state) == 23

        # Test appeal round sizes
        state = AddressAllocationState()
        assert get_appeal_round_size(state, False) == 7
        assert get_appeal_round_size(state, True) == 5  # 7-2

        state.appeal_count = 1
        assert get_appeal_round_size(state, False) == 13
        assert get_appeal_round_size(state, True) == 11  # 13-2

        state.appeal_count = 2
        assert get_appeal_round_size(state, False) == 25
        assert get_appeal_round_size(state, True) == 23  # 25-2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
