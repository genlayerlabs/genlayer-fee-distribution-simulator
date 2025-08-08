"""Invariant 12: Hash mismatch validators slashed correctly"""

from typing import List
from collections import defaultdict
from src.fee_simulator.protocol.models import FeeEvent
from src.fee_simulator.protocol.constants import IDLE_PENALTY_COEFFICIENT
from .common import InvariantViolation


def check_deterministic_violation_slashing(fee_events: List[FeeEvent]) -> None:
    """Invariant 12: Hash mismatch validators slashed correctly"""
    # Group events by round to analyze hash mismatches
    events_by_round = defaultdict(list)
    for event in fee_events:
        if event.round_index is not None:
            events_by_round[event.round_index].append(event)

    # For each round, check if slashing was applied correctly
    for round_index, round_events in events_by_round.items():
        # Find slashing events (those with slashed > 0)
        slash_events = [e for e in round_events if e.slashed and e.slashed > 0]

        if not slash_events:
            continue

        for slash_event in slash_events:
            # Calculate the stake at the time of slashing
            stake_at_slash = 0
            for event in fee_events:
                if event.sequence_id > slash_event.sequence_id:
                    break
                if event.address == slash_event.address:
                    if event.staked:
                        stake_at_slash += event.staked
                    if event.slashed:
                        stake_at_slash -= event.slashed

            # Check if this matches deterministic violation slashing patterns
            # Leader: loses 5% of stake
            # Validator: loses 1% of stake
            expected_leader_slash = stake_at_slash * 0.05
            expected_validator_slash = stake_at_slash * 0.01
            expected_idle_slash = stake_at_slash * IDLE_PENALTY_COEFFICIENT

            slash_amount = slash_event.slashed

            # Allow small floating point differences (< 1)
            is_leader_violation = abs(slash_amount - expected_leader_slash) < 1
            is_validator_violation = abs(slash_amount - expected_validator_slash) < 1
            is_idle_penalty = abs(slash_amount - expected_idle_slash) < 1

            # Skip idle penalties - they're checked in another invariant
            if is_idle_penalty:
                continue

            # Verify deterministic violation slashing amounts
            if not (is_leader_violation or is_validator_violation):
                # This slash doesn't match any expected pattern
                raise InvariantViolation(
                    "deterministic_violation_slashing",
                    f"Unexpected slash amount for {slash_event.address} in round {round_index}: "
                    f"slashed={slash_amount}, stake_at_slash={stake_at_slash}, "
                    f"expected_leader={expected_leader_slash:.2f}, "
                    f"expected_validator={expected_validator_slash:.2f}",
                )
