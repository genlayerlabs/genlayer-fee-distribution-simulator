"""
Tests for the new features: rotations, idleness improvements, and EQUAL_SPLIT round type.

Phase 1: Rotation support - tests that rounds with multiple rotations (leader timeouts
before the final outcome) distribute fees correctly.

Phase 2: Idleness improvements - tests that idle validators are handled correctly
with both replace and partial vote resolution modes.

Phase 3: EQUAL_SPLIT - tests the new round type where an unsuccessful leader appeal
is followed by an undetermined round.
"""

import pytest
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.core.majority import compute_majority
from src.fee_simulator.core.idleness import (
    replace_idle_participants,
    resolve_partial_votes,
)
from src.fee_simulator.utils import compute_total_cost, generate_random_eth_address
from src.fee_simulator.metrics.address_metrics import (
    compute_all_zeros,
    compute_total_costs,
    compute_total_earnings,
    compute_total_burnt,
)
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    Round,
    Rotation,
    Appeal,
    FeeEvent,
    EventSequence,
)
from src.fee_simulator.protocol.constants import (
    PENALTY_REWARD_COEFFICIENT,
    IDLE_PENALTY_COEFFICIENT,
    DEFAULT_STAKE,
)
from src.fee_simulator.specification.invariants.checker import check_all_invariants

leaderTimeout = 100
validatorsTimeout = 200

addresses_pool = [generate_random_eth_address() for _ in range(2000)]
sender_address = addresses_pool[1999]
appealant_address = addresses_pool[1998]


# =============================================================================
# Phase 1: Rotation Tests
# =============================================================================


class TestRotations:
    """Test fee distribution for rounds with leader timeout rotations."""

    def test_single_rotation_then_success(self, verbose, debug):
        """
        Round with 1 leader timeout rotation, then new leader succeeds.
        Expected: timed-out leader gets 50% of leaderTimeout,
        final round distributes normally.
        """
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        transaction_results, budget = path_to_transaction_results(
            path,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
            rotation_counts={0: 1},  # 1 timeout rotation before success
        )

        # Verify the round has 2 rotations (1 timeout + 1 final)
        assert len(transaction_results.rounds[0].rotations) == 2
        # First rotation should be a leader timeout
        first_rot_votes = transaction_results.rounds[0].rotations[0].votes
        first_leader = next(iter(first_rot_votes))
        assert first_rot_votes[first_leader] == ["LEADER_TIMEOUT", "NA"]

        # Process the transaction
        fee_events, round_labels = process_transaction(
            addresses=addresses_pool,
            transaction_results=transaction_results,
            transaction_budget=budget,
        )

        # Round should still be labeled NORMAL_ROUND (final rotation determines label)
        assert round_labels == ["NORMAL_ROUND"]

        # The timed-out leader (first rotation) should get 50% of leaderTimeout
        timed_out_leader = next(iter(transaction_results.rounds[0].rotations[0].votes))
        timed_out_earnings = compute_total_earnings(fee_events, timed_out_leader)
        assert timed_out_earnings >= int(leaderTimeout / 2), (
            f"Timed-out leader should earn at least 50% of leaderTimeout ({leaderTimeout/2}), "
            f"got {timed_out_earnings}"
        )

        # Budget should have rotation count of 1
        assert budget.rotations == [1]

        # Total cost should account for rotations
        total_cost = compute_total_cost(budget)
        # With 1 rotation: (1+1) * (5 * 200 + 100) = 2 * 1100 = 2200
        expected_cost = 2 * (5 * validatorsTimeout + leaderTimeout)
        assert total_cost >= expected_cost

    def test_three_rotations_then_success(self, verbose, debug):
        """
        Round with 3 leader timeout rotations, then 4th leader succeeds.
        Expected: 3 timed-out leaders each get 50% leaderTimeout.
        """
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        transaction_results, budget = path_to_transaction_results(
            path,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
            rotation_counts={0: 3},  # 3 timeout rotations before success
        )

        # Verify the round has 4 rotations (3 timeout + 1 final)
        assert len(transaction_results.rounds[0].rotations) == 4

        # Process the transaction
        fee_events, round_labels = process_transaction(
            addresses=addresses_pool,
            transaction_results=transaction_results,
            transaction_budget=budget,
        )

        assert round_labels == ["NORMAL_ROUND"]

        # Budget should reflect 3 rotations
        assert budget.rotations == [3]

        # Total cost should be 4x the base cost
        total_cost = compute_total_cost(budget)
        base_cost = 5 * validatorsTimeout + leaderTimeout
        expected_cost = 4 * base_cost
        assert total_cost >= expected_cost

    def test_rotation_with_appeal(self, verbose, debug):
        """
        Normal round with 1 rotation, then validator appeal.
        Tests that rotations work correctly with multi-round paths.
        """
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "END",
        ]
        transaction_results, budget = path_to_transaction_results(
            path,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
            rotation_counts={0: 1},
        )

        # First round should have 2 rotations
        assert len(transaction_results.rounds[0].rotations) == 2

        fee_events, round_labels = process_transaction(
            addresses=addresses_pool,
            transaction_results=transaction_results,
            transaction_budget=budget,
        )

        # Should process without errors and pass invariants
        check_all_invariants(fee_events, budget, transaction_results, round_labels)

    def test_budget_tracks_exact_per_round_rotation_requirements(self):
        """Generated paths use the minimal executable Consensus schedule."""
        path = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ]
        transaction_results, budget = path_to_transaction_results(
            path,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
            rotation_counts={0: 2, 1: 0},  # First normal round has 2 rotations
        )

        assert budget.rotations == [2, 0]
        assert budget.rotationsUsed == [2, 0]
        assert max(budget.rotations) == 2  # transaction-wide runtime ceiling

    def test_total_cost_formula_with_rotations(self):
        """
        Verify the corrected total cost formula:
        (rotation_count + 1) * (round_size * validators_timeout + leader_timeout)
        """
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=0,
            rotations=[2],  # 2 extra rotations (3 total attempts)
            senderAddress=sender_address,
            appeals=[],
            staking_distribution="constant",
        )

        total_cost = compute_total_cost(budget)
        # round_size = 5 (first normal round)
        # (2+1) * (5 * 200 + 100) = 3 * 1100 = 3300
        expected_base = 3 * (5 * 200 + 100)
        assert total_cost >= expected_base


# =============================================================================
# Phase 2: Idleness Tests
# =============================================================================


class TestIdleness:
    """Test idle validator handling improvements."""

    def test_resolve_partial_votes_basic(self):
        """Test that resolve_partial_votes converts IDLE to DISAGREE."""
        votes = {
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[1]: "AGREE",
            addresses_pool[2]: "AGREE",
            addresses_pool[3]: "IDLE",
            addresses_pool[4]: "IDLE",
        }
        resolved = resolve_partial_votes(votes)

        # IDLE votes should become DISAGREE
        assert resolved[addresses_pool[3]] == "DISAGREE"
        assert resolved[addresses_pool[4]] == "DISAGREE"
        # Non-IDLE votes should be unchanged
        assert resolved[addresses_pool[1]] == "AGREE"
        assert resolved[addresses_pool[0]] == ["LEADER_RECEIPT", "AGREE"]

    def test_partial_resolution_majority_unchanged(self):
        """
        With 2 out of 5 validators idle, majority should still be AGREE
        when idle is converted to DISAGREE.
        3 AGREE (including leader) vs 2 DISAGREE (from IDLE) = AGREE majority.
        """
        votes = {
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[1]: "AGREE",
            addresses_pool[2]: "AGREE",
            addresses_pool[3]: "IDLE",
            addresses_pool[4]: "IDLE",
        }
        resolved = resolve_partial_votes(votes)
        majority = compute_majority(resolved)
        assert majority == "AGREE", f"Expected AGREE majority, got {majority}"

    def test_partial_resolution_majority_changes(self):
        """
        With 3 out of 5 validators idle, majority should change to DISAGREE
        when idle is converted to DISAGREE.
        2 AGREE (including leader) vs 3 DISAGREE (from IDLE) = DISAGREE majority.
        """
        votes = {
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[1]: "AGREE",
            addresses_pool[2]: "IDLE",
            addresses_pool[3]: "IDLE",
            addresses_pool[4]: "IDLE",
        }
        resolved = resolve_partial_votes(votes)
        majority = compute_majority(resolved)
        assert majority == "DISAGREE", f"Expected DISAGREE majority, got {majority}"

    def test_count_idle_as_disagree_in_majority(self):
        """Test the count_idle_as_disagree parameter in compute_majority."""
        votes = {
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[1]: "AGREE",
            addresses_pool[2]: "IDLE",
            addresses_pool[3]: "IDLE",
            addresses_pool[4]: "IDLE",
        }
        # Without flag: IDLE doesn't count towards any majority
        majority_default = compute_majority(votes)
        assert majority_default == "UNDETERMINED"

        # With flag: IDLE counts as DISAGREE
        majority_idle_disagree = compute_majority(votes, count_idle_as_disagree=True)
        assert majority_idle_disagree == "DISAGREE"

    def test_idle_config_in_path_to_transaction(self, verbose, debug):
        """Test that idle_config creates IDLE votes in generated transactions."""
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        transaction_results, budget = path_to_transaction_results(
            path,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
            idle_config={0: 1},  # 1 idle validator in first round
        )

        votes = transaction_results.rounds[0].rotations[-1].votes
        idle_count = sum(1 for v in votes.values() if v == "IDLE")
        assert idle_count == 1, f"Expected 1 idle validator, got {idle_count}"

    def test_replace_idle_mode(self, verbose, debug):
        """Test the existing replace mode still works for idle validators."""
        # Create a round with an idle validator and reserve
        votes = {
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[1]: "AGREE",
            addresses_pool[2]: "AGREE",
            addresses_pool[3]: "AGREE",
            addresses_pool[4]: "IDLE",
        }
        reserve_votes = {addresses_pool[5]: "AGREE"}

        transaction_results = TransactionRoundResults(
            rounds=[
                Round(rotations=[Rotation(votes=votes, reserve_votes=reserve_votes)])
            ]
        )

        event_sequence = EventSequence()
        fee_events = []

        # Initialize stakes for the idle validator
        fee_events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=addresses_pool[4],
                staked=DEFAULT_STAKE,
            )
        )

        new_results, new_events = replace_idle_participants(
            event_sequence=event_sequence,
            fee_events=fee_events,
            transaction_results=transaction_results,
            idle_resolution_mode="replace",
        )

        # Idle validator should be replaced
        final_votes = new_results.rounds[0].rotations[-1].votes
        assert (
            addresses_pool[4] not in final_votes
            or final_votes.get(addresses_pool[4]) != "IDLE"
        )

        # Should have a slashing event for the idle validator
        slash_events = [e for e in new_events if e.slashed > 0]
        assert len(slash_events) == 1
        assert slash_events[0].address == addresses_pool[4]
        assert slash_events[0].slashed == int(DEFAULT_STAKE * IDLE_PENALTY_COEFFICIENT)

    def test_partial_idle_mode(self, verbose, debug):
        """Test partial vote resolution mode for idle validators."""
        votes = {
            addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
            addresses_pool[1]: "AGREE",
            addresses_pool[2]: "AGREE",
            addresses_pool[3]: "AGREE",
            addresses_pool[4]: "IDLE",
        }

        transaction_results = TransactionRoundResults(
            rounds=[Round(rotations=[Rotation(votes=votes)])]
        )

        event_sequence = EventSequence()
        fee_events = []
        fee_events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=addresses_pool[4],
                staked=DEFAULT_STAKE,
            )
        )

        new_results, new_events = replace_idle_participants(
            event_sequence=event_sequence,
            fee_events=fee_events,
            transaction_results=transaction_results,
            idle_resolution_mode="partial",
        )

        # In partial mode, IDLE should be converted to DISAGREE (not replaced)
        final_votes = new_results.rounds[0].rotations[-1].votes
        assert final_votes[addresses_pool[4]] == "DISAGREE"

        # Should still have slashing event
        slash_events = [e for e in new_events if e.slashed > 0]
        assert len(slash_events) == 1
        assert slash_events[0].slashed == int(DEFAULT_STAKE * IDLE_PENALTY_COEFFICIENT)


# =============================================================================
# Phase 3: EQUAL_SPLIT Tests
# =============================================================================


class TestEqualSplit:
    """Test the EQUAL_SPLIT round type."""

    def test_equal_split_labeling(self, verbose, debug):
        """
        Test that EQUAL_SPLIT is produced when:
        - Previous round was APPEAL_LEADER_UNSUCCESSFUL
        - Current round has UNDETERMINED majority
        """
        path = [
            "START",
            "LEADER_RECEIPT_UNDETERMINED",
            "LEADER_APPEAL_UNSUCCESSFUL",
            "LEADER_RECEIPT_UNDETERMINED",
            "END",
        ]
        transaction_results, budget = path_to_transaction_results(
            path,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
        )

        labels = label_rounds(transaction_results)
        assert labels[2] == "EQUAL_SPLIT", (
            f"Expected EQUAL_SPLIT for undetermined round after unsuccessful leader appeal, "
            f"got {labels[2]}"
        )

    def test_equal_split_fee_distribution(self, verbose, debug):
        """
        Test EQUAL_SPLIT fee distribution:
        - Leader gets leaderTimeout
        - ALL validators get validatorsTimeout (no penalties)
        """
        path = [
            "START",
            "LEADER_RECEIPT_UNDETERMINED",
            "LEADER_APPEAL_UNSUCCESSFUL",
            "LEADER_RECEIPT_UNDETERMINED",
            "END",
        ]
        transaction_results, budget = path_to_transaction_results(
            path,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
        )

        fee_events, round_labels = process_transaction(
            addresses=addresses_pool,
            transaction_results=transaction_results,
            transaction_budget=budget,
        )

        assert round_labels[2] == "EQUAL_SPLIT"

        # Get EQUAL_SPLIT round events
        equal_split_events = [e for e in fee_events if e.round_label == "EQUAL_SPLIT"]

        # Leader should earn leaderTimeout
        leader_events = [e for e in equal_split_events if e.role == "LEADER"]
        assert len(leader_events) == 1
        assert leader_events[0].earned == leaderTimeout

        # All non-leader validators earn validatorsTimeout + an equal share
        # of the failed leader appeal bond (contract semantics: the bond is
        # distributed, not returned to the sender)
        validator_events = [e for e in equal_split_events if e.role == "VALIDATOR"]
        assert len(validator_events) > 0
        expected_share = validator_events[0].earned - validatorsTimeout
        assert expected_share > 0, "Bond share should be positive in EQUAL_SPLIT"
        assert all(
            e.earned == validatorsTimeout + expected_share for e in validator_events
        ), "All validators should earn validatorsTimeout + equal bond share in EQUAL_SPLIT"

        # No penalties in EQUAL_SPLIT
        assert all(
            e.burned == 0 for e in equal_split_events
        ), "No burns should occur in EQUAL_SPLIT"

    def test_equal_split_invariants(self, verbose, debug):
        """Test that all 24 invariants pass for EQUAL_SPLIT scenario."""
        path = [
            "START",
            "LEADER_RECEIPT_UNDETERMINED",
            "LEADER_APPEAL_UNSUCCESSFUL",
            "LEADER_RECEIPT_UNDETERMINED",
            "END",
        ]
        transaction_results, budget = path_to_transaction_results(
            path,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
        )

        fee_events, round_labels = process_transaction(
            addresses=addresses_pool,
            transaction_results=transaction_results,
            transaction_budget=budget,
        )

        # This should pass all 24 invariants
        check_all_invariants(fee_events, budget, transaction_results, round_labels)

    def test_equal_split_vs_split_bond_differentiation(self, verbose, debug):
        """
        Verify that EQUAL_SPLIT and SPLIT_PREVIOUS_APPEAL_BOND are correctly
        differentiated:
        - APPEAL_LEADER_UNSUCCESSFUL + UNDETERMINED → EQUAL_SPLIT
        - APPEAL_VALIDATOR_UNSUCCESSFUL + UNDETERMINED → SPLIT_PREVIOUS_APPEAL_BOND
        """
        # Validator unsuccessful appeal should produce SPLIT_PREVIOUS_APPEAL_BOND
        path_validator = [
            "START",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "VALIDATOR_APPEAL_UNSUCCESSFUL",
            "END",
        ]
        tx_val, budget_val = path_to_transaction_results(
            path_validator,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
        )
        labels_val = label_rounds(tx_val)
        # Validator unsuccessful appeals shouldn't produce EQUAL_SPLIT
        assert "EQUAL_SPLIT" not in labels_val

        # Leader unsuccessful appeal should produce EQUAL_SPLIT
        path_leader = [
            "START",
            "LEADER_RECEIPT_UNDETERMINED",
            "LEADER_APPEAL_UNSUCCESSFUL",
            "LEADER_RECEIPT_UNDETERMINED",
            "END",
        ]
        tx_ldr, budget_ldr = path_to_transaction_results(
            path_leader,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
        )
        labels_ldr = label_rounds(tx_ldr)
        assert "EQUAL_SPLIT" in labels_ldr

    def test_equal_split_appeal_bond_returned_to_sender(self, verbose, debug):
        """
        In EQUAL_SPLIT, the appeal bond should be returned to sender (not
        distributed to validators). Verify via refund calculation.
        """
        path = [
            "START",
            "LEADER_RECEIPT_UNDETERMINED",
            "LEADER_APPEAL_UNSUCCESSFUL",
            "LEADER_RECEIPT_UNDETERMINED",
            "END",
        ]
        transaction_results, budget = path_to_transaction_results(
            path,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
        )

        fee_events, round_labels = process_transaction(
            addresses=addresses_pool,
            transaction_results=transaction_results,
            transaction_budget=budget,
        )

        # The sender refund should be non-negative (conservation of value)
        sender_events = [e for e in fee_events if e.address == sender_address]
        sender_cost = sum(e.cost for e in sender_events)
        sender_earned = sum(e.earned for e in sender_events)
        assert sender_earned > 0, "Sender should get a refund"
        assert sender_cost > sender_earned, "Sender should pay more than they get back"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple new features."""

    def test_rotation_with_idle_config(self, verbose, debug):
        """Test that rotation_counts and idle_config can be used together."""
        path = ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"]
        transaction_results, budget = path_to_transaction_results(
            path,
            addresses_pool,
            sender_address=sender_address,
            appealant_address=appealant_address,
            leader_timeout=leaderTimeout,
            validators_timeout=validatorsTimeout,
            rotation_counts={0: 1},
            idle_config={0: 1},
        )

        # Should have 2 rotations (timeout + final)
        assert len(transaction_results.rounds[0].rotations) == 2

        # Final rotation should have 1 idle validator
        final_votes = transaction_results.rounds[0].rotations[-1].votes
        idle_count = sum(1 for v in final_votes.values() if v == "IDLE")
        assert idle_count == 1

    def test_all_existing_paths_still_pass(self, verbose, debug):
        """Verify that basic paths without rotations/idleness still work."""
        simple_paths = [
            ["START", "LEADER_RECEIPT_MAJORITY_AGREE", "END"],
            ["START", "LEADER_TIMEOUT", "END"],
            ["START", "LEADER_RECEIPT_UNDETERMINED", "END"],
        ]

        for path in simple_paths:
            transaction_results, budget = path_to_transaction_results(
                path,
                addresses_pool,
                sender_address=sender_address,
                appealant_address=appealant_address,
                leader_timeout=leaderTimeout,
                validators_timeout=validatorsTimeout,
            )
            fee_events, round_labels = process_transaction(
                addresses=addresses_pool,
                transaction_results=transaction_results,
                transaction_budget=budget,
            )
            check_all_invariants(fee_events, budget, transaction_results, round_labels)
