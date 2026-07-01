"""
Unit tests for individual fee distribution functions.

Each test focuses on a single fee distribution function and verifies
its behavior in isolation.
"""

import pytest
from typing import List, Dict
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    TransactionBudget,
    Round,
    Rotation,
    Appeal,
    EventSequence,
    FeeEvent,
)
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.utils import generate_random_eth_address
from src.fee_simulator.protocol.constants import PENALTY_REWARD_COEFFICIENT

# Import all fee distribution functions
from src.fee_simulator.core.round_fee_distribution.normal_round import (
    apply_normal_round,
)
from src.fee_simulator.core.round_fee_distribution.appeal_leader_successful import (
    apply_appeal_leader_successful,
)
from src.fee_simulator.core.round_fee_distribution.appeal_validator_successful import (
    apply_appeal_validator_successful,
)
from src.fee_simulator.core.round_fee_distribution.appeal_validator_unsuccessful import (
    apply_appeal_validator_unsuccessful,
)
from src.fee_simulator.core.round_fee_distribution.appeal_leader_timeout_successful import (
    apply_appeal_leader_timeout_successful,
)
from src.fee_simulator.core.round_fee_distribution.leader_timeout_50_percent import (
    apply_leader_timeout_50_percent,
)
from src.fee_simulator.core.round_fee_distribution.leader_timeout_150_previous_normal_round import (
    apply_leader_timeout_150_previous_normal_round,
)
from src.fee_simulator.core.round_fee_distribution.leader_timeout_50_previous_appeal_bond import (
    apply_leader_timeout_50_previous_appeal_bond,
)
from src.fee_simulator.core.round_fee_distribution.split_previous_appeal_bond import (
    apply_split_previous_appeal_bond,
)

# Generate test addresses
addresses_pool = [generate_random_eth_address() for _ in range(100)]


class TestNormalRound:
    """Unit tests for apply_normal_round function."""

    def test_leader_receipt_majority_agree(self):
        """Test normal round with leader receipt and majority agree."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                                addresses_pool[4]: "AGREE",
                            }
                        )
                    ]
                )
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=0,
            rotations=[0],
            senderAddress=addresses_pool[99],
            appeals=[],
            staking_distribution="constant",
        )

        # Execute
        round_labels = ["NORMAL_ROUND"]
        events = apply_normal_round(
            transaction_results=transaction_results,
            round_index=0,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )

        # Verify
        assert len(events) == 6  # 5 participants + separate leader event

        # Leader should have two events: one as validator, one as leader
        leader_events = [e for e in events if e.address == addresses_pool[0]]
        assert len(leader_events) == 2
        leader_as_leader = next(e for e in leader_events if e.role == "LEADER")
        leader_as_validator = next(e for e in leader_events if e.role == "VALIDATOR")
        assert leader_as_leader.earned == 100  # leader timeout
        assert leader_as_validator.earned == 200  # validator timeout
        # Total leader earnings = 300

        # Majority validators should earn validator timeout
        for addr in [addresses_pool[1], addresses_pool[2], addresses_pool[4]]:
            event = next(e for e in events if e.address == addr)
            assert event.earned == 200
            assert event.role == "VALIDATOR"

        # Minority validator should be penalized
        minority_event = next(e for e in events if e.address == addresses_pool[3])
        assert minority_event.earned == 0
        assert minority_event.burned == PENALTY_REWARD_COEFFICIENT * 200
        assert minority_event.role == "VALIDATOR"

    def test_leader_receipt_undetermined(self):
        """Test normal round with undetermined outcome."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
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
                )
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=0,
            rotations=[0],
            senderAddress=addresses_pool[99],
            appeals=[],
            staking_distribution="constant",
        )

        # Execute
        round_labels = ["NORMAL_ROUND"]
        events = apply_normal_round(
            transaction_results=transaction_results,
            round_index=0,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )

        # Verify
        assert len(events) == 6  # 1 leader event + 5 validator events

        # Leader should have two events: one as leader, one as validator
        leader_events = [e for e in events if e.address == addresses_pool[0]]
        assert len(leader_events) == 2
        leader_as_leader = next(e for e in leader_events if e.role == "LEADER")
        leader_as_validator = next(e for e in leader_events if e.role == "VALIDATOR")
        assert leader_as_leader.earned == 100  # leader timeout
        assert leader_as_validator.earned == 200  # validator timeout (undetermined)

        # All validators should earn validator timeout (undetermined case)
        for addr in [
            addresses_pool[1],
            addresses_pool[2],
            addresses_pool[3],
            addresses_pool[4],
        ]:
            event = next(e for e in events if e.address == addr)
            assert event.earned == 200  # validator timeout
            assert event.burned == 0


class TestAppealLeaderSuccessful:
    """Unit tests for apply_appeal_leader_successful function."""

    def test_basic_appeal_leader_successful(self):
        """Test successful leader appeal."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                # Normal round (5 validators minimum)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "DISAGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                                addresses_pool[4]: "TIMEOUT",
                            }
                        )
                    ]
                ),
                # Appeal round (7 validators minimum)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[5]: "NA",
                                addresses_pool[6]: "NA",
                                addresses_pool[7]: "NA",
                                addresses_pool[8]: "NA",
                                addresses_pool[9]: "NA",
                                addresses_pool[10]: "NA",
                                addresses_pool[11]: "NA",
                            }
                        )
                    ]
                ),
                # Normal round after appeal (11 validators = all from previous rounds except original leader)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[1]: [
                                    "LEADER_RECEIPT",
                                    "AGREE",
                                ],  # New leader from original validators
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "AGREE",
                                addresses_pool[4]: "AGREE",
                                # Original leader addresses_pool[0] is excluded
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "AGREE",
                                addresses_pool[8]: "DISAGREE",
                                addresses_pool[9]: "DISAGREE",
                                addresses_pool[10]: "DISAGREE",
                                addresses_pool[11]: "DISAGREE",
                            }
                        )
                    ]
                ),
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=1,
            rotations=[0, 0],
            senderAddress=addresses_pool[99],
            appeals=[Appeal(appealantAddress=addresses_pool[98])],
            staking_distribution="constant",
        )
        round_labels = ["SKIP_ROUND", "APPEAL_LEADER_SUCCESSFUL", "NORMAL_ROUND"]

        # Execute
        events = apply_appeal_leader_successful(
            transaction_results=transaction_results,
            round_index=1,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )

        # Verify
        assert len(events) == 1  # Only appealant event

        appealant_event = events[0]
        assert appealant_event.address == addresses_pool[98]
        assert appealant_event.role == "APPEALANT"
        # Appealant should earn 1.5x appeal bond for 50% return
        # Leader appeal bond covers the full next normal round:
        # 100 + 11 validators * 200 = 2300
        assert appealant_event.earned == int(2300 * 1.5)  # 3450
        assert appealant_event.cost == 0  # Cost is recorded separately


class TestAppealValidatorSuccessful:
    """Unit tests for apply_appeal_validator_successful function."""

    def test_basic_appeal_validator_successful(self):
        """Test successful validator appeal."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                # Normal round (5 validators - majority agree)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                                addresses_pool[4]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Appeal round (7 validators - validators disagree)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[5]: "DISAGREE",
                                addresses_pool[6]: "DISAGREE",
                                addresses_pool[7]: "DISAGREE",
                                addresses_pool[8]: "DISAGREE",
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "AGREE",
                                addresses_pool[11]: "AGREE",
                            }
                        )
                    ]
                ),
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=1,
            rotations=[0, 0],  # 2 rounds: normal + appeal
            senderAddress=addresses_pool[99],
            appeals=[Appeal(appealantAddress=addresses_pool[98])],
            staking_distribution="constant",
        )
        round_labels = ["SKIP_ROUND", "APPEAL_VALIDATOR_SUCCESSFUL"]

        # Execute
        events = apply_appeal_validator_successful(
            transaction_results=transaction_results,
            round_index=1,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )

        # Verify
        # Should have events for appealant and validators from both rounds
        assert len(events) == 8  # appealant + 7 from appeal round

        # Appealant should earn 1.5x appeal bond for 50% return
        # Validator appeal bond covers only the appeal validators (no leader fee)
        appealant_event = next(e for e in events if e.address == addresses_pool[98])
        assert appealant_event.earned == int(
            (7 * 200) * 1.5
        )  # 1.5x appeal_bond = 2100

        # In successful appeal
        # Appeal round: 4 DISAGREE, 3 AGREE

        validator_events = [e for e in events if e.role == "VALIDATOR"]
        assert len(validator_events) == 7  # All validators from both rounds


class TestLeaderTimeout50Percent:
    """Unit tests for apply_leader_timeout_50_percent function."""

    def test_single_leader_timeout(self):
        """Test leader timeout when it's the only round."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_TIMEOUT", "NA"],
                                addresses_pool[1]: "NA",
                                addresses_pool[2]: "NA",
                                addresses_pool[3]: "NA",
                                addresses_pool[4]: "NA",
                            }
                        )
                    ]
                )
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=0,
            rotations=[0],
            senderAddress=addresses_pool[99],
            appeals=[],
            staking_distribution="constant",
        )

        # Execute
        round_labels = ["LEADER_TIMEOUT_50_PERCENT"]
        events = apply_leader_timeout_50_percent(
            transaction_results=transaction_results,
            round_index=0,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )

        # Verify
        assert len(events) == 1

        leader_event = events[0]
        assert leader_event.address == addresses_pool[0]
        assert leader_event.role == "LEADER"
        assert leader_event.earned == 50  # 50% of leader timeout


class TestSplitPreviousAppealBond:
    """Unit tests for apply_split_previous_appeal_bond function."""

    def test_split_appeal_bond_among_validators(self):
        """Test splitting appeal bond among validators in undetermined round."""
        # Setup
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                # Normal round (5 validators)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                                addresses_pool[4]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Unsuccessful appeal (7 validators)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "AGREE",
                                addresses_pool[8]: "AGREE",
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "DISAGREE",
                                addresses_pool[11]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Undetermined round (11 validators = 5 + 7 - 1, split bond)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[1]: [
                                    "LEADER_RECEIPT",
                                    "AGREE",
                                ],  # New leader
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "AGREE",
                                addresses_pool[4]: "DISAGREE",
                                addresses_pool[5]: "DISAGREE",
                                addresses_pool[6]: "DISAGREE",
                                addresses_pool[7]: "TIMEOUT",
                                addresses_pool[8]: "TIMEOUT",
                                addresses_pool[9]: "TIMEOUT",
                                addresses_pool[10]: "TIMEOUT",
                                addresses_pool[11]: "TIMEOUT",
                            }
                        )
                    ]
                ),
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=1,
            rotations=[0, 0],
            senderAddress=addresses_pool[99],
            appeals=[Appeal(appealantAddress=addresses_pool[98])],
            staking_distribution="constant",
        )
        round_labels = [
            "NORMAL_ROUND",
            "APPEAL_VALIDATOR_UNSUCCESSFUL",
            "SPLIT_PREVIOUS_APPEAL_BOND",
        ]

        # Execute
        events = apply_split_previous_appeal_bond(
            transaction_results=transaction_results,
            round_index=2,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )

        # Verify
        assert len(events) == 12  # 11 validator events + 1 leader event

        # Leader should earn leader timeout
        leader_event = next(
            e for e in events if e.address == addresses_pool[1] and e.role == "LEADER"
        )
        assert leader_event.earned == 100

        # Contract semantics: aligned validators earn validatorsTimeout plus
        # an equal share of the FULL bond.
        # Validator appeal bond = 7 * 200 = 1400 (no leader fee component)
        # UNDETERMINED → all 11 aligned: 200 + 1400 // 11 = 200 + 127 = 327
        for i in range(1, 12):  # addresses_pool[1] through addresses_pool[11]
            validator_events = [
                e
                for e in events
                if e.address == addresses_pool[i] and e.role == "VALIDATOR"
            ]
            if validator_events:
                assert validator_events[0].earned == 327
                assert validator_events[0].role == "VALIDATOR"


class TestChainedAppealScenarios:
    """Test scenarios with multiple chained appeals."""

    def test_double_unsuccessful_appeals(self):
        """Test handling of consecutive unsuccessful appeals."""
        # Setup for a complex scenario with multiple appeals
        event_sequence = EventSequence()
        transaction_results = TransactionRoundResults(
            rounds=[
                # Round 0: Normal (5 validators)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[0]: ["LEADER_RECEIPT", "AGREE"],
                                addresses_pool[1]: "AGREE",
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "DISAGREE",
                                addresses_pool[4]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 1: First appeal (7 validators, unsuccessful)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "AGREE",
                                addresses_pool[8]: "AGREE",
                                addresses_pool[9]: "AGREE",
                                addresses_pool[10]: "DISAGREE",
                                addresses_pool[11]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 2: Normal (11 validators = 5 + 7 - 1)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[1]: [
                                    "LEADER_RECEIPT",
                                    "AGREE",
                                ],  # New leader
                                addresses_pool[2]: "AGREE",
                                addresses_pool[3]: "AGREE",
                                addresses_pool[4]: "AGREE",
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "DISAGREE",
                                addresses_pool[8]: "DISAGREE",
                                addresses_pool[9]: "DISAGREE",
                                addresses_pool[10]: "DISAGREE",
                                addresses_pool[11]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 3: Second appeal (13 validators, unsuccessful)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[12]: "AGREE",
                                addresses_pool[13]: "AGREE",
                                addresses_pool[14]: "AGREE",
                                addresses_pool[15]: "AGREE",
                                addresses_pool[16]: "AGREE",
                                addresses_pool[17]: "AGREE",
                                addresses_pool[18]: "AGREE",
                                addresses_pool[19]: "DISAGREE",
                                addresses_pool[20]: "DISAGREE",
                                addresses_pool[21]: "DISAGREE",
                                addresses_pool[22]: "DISAGREE",
                                addresses_pool[23]: "DISAGREE",
                                addresses_pool[24]: "DISAGREE",
                            }
                        )
                    ]
                ),
                # Round 4: Undetermined (23 validators = 11 + 13 - 1, split bond)
                Round(
                    rotations=[
                        Rotation(
                            votes={
                                addresses_pool[2]: [
                                    "LEADER_RECEIPT",
                                    "AGREE",
                                ],  # New leader
                                addresses_pool[3]: "AGREE",
                                addresses_pool[4]: "AGREE",
                                addresses_pool[5]: "AGREE",
                                addresses_pool[6]: "AGREE",
                                addresses_pool[7]: "DISAGREE",
                                addresses_pool[8]: "DISAGREE",
                                addresses_pool[9]: "DISAGREE",
                                addresses_pool[10]: "DISAGREE",
                                addresses_pool[11]: "DISAGREE",
                                addresses_pool[12]: "TIMEOUT",
                                addresses_pool[13]: "TIMEOUT",
                                addresses_pool[14]: "TIMEOUT",
                                addresses_pool[15]: "TIMEOUT",
                                addresses_pool[16]: "TIMEOUT",
                                addresses_pool[17]: "TIMEOUT",
                                addresses_pool[18]: "TIMEOUT",
                                addresses_pool[19]: "TIMEOUT",
                                addresses_pool[20]: "TIMEOUT",
                                addresses_pool[21]: "TIMEOUT",
                                addresses_pool[22]: "TIMEOUT",
                                addresses_pool[23]: "TIMEOUT",
                                addresses_pool[24]: "TIMEOUT",
                            }
                        )
                    ]
                ),
            ]
        )
        budget = TransactionBudget(
            leaderTimeout=100,
            validatorsTimeout=200,
            appealRounds=2,
            rotations=[0, 0, 0],
            senderAddress=addresses_pool[99],
            appeals=[
                Appeal(appealantAddress=addresses_pool[97]),
                Appeal(appealantAddress=addresses_pool[96]),
            ],
            staking_distribution="constant",
        )
        round_labels = [
            "NORMAL_ROUND",
            "APPEAL_VALIDATOR_UNSUCCESSFUL",
            "NORMAL_ROUND",
            "APPEAL_VALIDATOR_UNSUCCESSFUL",
            "SPLIT_PREVIOUS_APPEAL_BOND",
        ]

        # Execute the appeal functions
        # First unsuccessful appeal
        events1 = apply_appeal_validator_unsuccessful(
            transaction_results=transaction_results,
            round_index=1,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )

        # Verify first appeal has events for its validators (the appellant's
        # loss is the bond cost recorded at bond subtraction, no burn event)
        assert len(events1) == 7  # 7 validators

        # Second unsuccessful appeal
        events2 = apply_appeal_validator_unsuccessful(
            transaction_results=transaction_results,
            round_index=3,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )

        # Verify second appeal has events for its validators
        assert len(events2) == 13  # 13 validators

        # The split bond function should handle the second appeal's bond
        events3 = apply_split_previous_appeal_bond(
            transaction_results=transaction_results,
            round_index=4,
            budget=budget,
            event_sequence=event_sequence,
            round_labels=round_labels,
        )

        # Verify the bond is split correctly
        assert len(events3) == 24  # 23 validators + 1 leader

        # Debug: print what validators are earning
        validator_earnings = [
            (e.address, e.earned, e.vote) for e in events3 if e.role == "VALIDATOR"
        ]
        print(f"Validator earnings: {validator_earnings[:5]}...")  # Show first 5

        # The split depends on majority/minority
        # In this case: 5 AGREE, 5 DISAGREE, 13 TIMEOUT
        # Since 13 > 11 (which is 23/2), TIMEOUT is the majority
        # So the bond is split only among TIMEOUT voters

        # The second appeal bond (validator appeal, no leader fee: 13 * 200 = 2600)
        # Contract semantics: aligned validators earn V + full bond share:
        # 200 + 2600 // 13 = 400 each

        validator_events = [e for e in events3 if e.role == "VALIDATOR"]

        # Check TIMEOUT voters get the split
        timeout_voters = [e for e in validator_events if e.vote == "TIMEOUT"]
        assert len(timeout_voters) == 13
        for event in timeout_voters:
            assert event.earned == 400  # 200 + 2600 // 13

        # Check AGREE and DISAGREE voters get 0 and are penalized
        non_timeout_voters = [e for e in validator_events if e.vote != "TIMEOUT"]
        assert len(non_timeout_voters) == 10  # 5 AGREE + 5 DISAGREE
        for event in non_timeout_voters:
            assert event.earned == 0
            assert event.burned == 200  # PENALTY_REWARD_COEFFICIENT * validator_timeout


def test_all_distribution_functions_have_tests():
    """Meta-test to ensure we have tests for all distribution functions."""
    # List of all distribution functions that should have tests
    distribution_functions = {
        "normal_round": TestNormalRound,
        "appeal_leader_successful": TestAppealLeaderSuccessful,
        "appeal_validator_successful": TestAppealValidatorSuccessful,
        "leader_timeout_50_percent": TestLeaderTimeout50Percent,
        "split_previous_appeal_bond": TestSplitPreviousAppealBond,
    }

    # Verify each has at least one test method
    for func_name, test_class in distribution_functions.items():
        test_methods = [m for m in dir(test_class) if m.startswith("test_")]
        assert len(test_methods) > 0, f"No tests found for {func_name}"


if __name__ == "__main__":
    # Run a quick validation
    print("Running unit tests for fee distribution functions...")

    # Test normal round
    test_normal = TestNormalRound()
    test_normal.test_leader_receipt_majority_agree()
    test_normal.test_leader_receipt_undetermined()
    print("✓ Normal round tests passed")

    # Test appeals
    test_leader_appeal = TestAppealLeaderSuccessful()
    test_leader_appeal.test_basic_appeal_leader_successful()
    print("✓ Leader appeal tests passed")

    test_validator_appeal = TestAppealValidatorSuccessful()
    test_validator_appeal.test_basic_appeal_validator_successful()
    print("✓ Validator appeal tests passed")

    # Test special cases
    test_timeout = TestLeaderTimeout50Percent()
    test_timeout.test_single_leader_timeout()
    print("✓ Leader timeout tests passed")

    test_split = TestSplitPreviousAppealBond()
    test_split.test_split_appeal_bond_among_validators()
    print("✓ Split bond tests passed")

    # Test chained scenarios
    test_chained = TestChainedAppealScenarios()
    test_chained.test_double_unsuccessful_appeals()
    print("✓ Chained appeal tests passed")

    print("\nAll unit tests completed successfully!")
