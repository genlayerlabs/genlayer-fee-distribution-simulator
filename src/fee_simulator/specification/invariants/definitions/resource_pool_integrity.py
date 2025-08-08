"""Invariant 22: Address allocation respects global limits"""

from typing import List
from src.fee_simulator.protocol.models import FeeEvent, TransactionBudget, TransactionRoundResults
from .common import InvariantViolation


def check_resource_pool_integrity(
    transaction_results: TransactionRoundResults,
    fee_events: List[FeeEvent],
    transaction_budget: TransactionBudget,
) -> None:
    """
    Invariant 22: Address allocation respects global limits.
    Total unique addresses used should not exceed pool capacity.
    """
    # Collect all unique addresses used that are not just for staking
    all_addresses = set()

    # From transaction rounds (votes)
    for round_obj in transaction_results.rounds:
        if round_obj.rotations:
            for rotation in round_obj.rotations:
                all_addresses.update(rotation.votes.keys())

    # From fee events, excluding initial staking events
    for event in fee_events:
        # An initial staking event has a `staked` value but no role or other activity.
        is_staking_only_event = (
            event.staked > 0
            and event.role is None
            and event.cost == 0
            and event.earned == 0
            and event.burned == 0
            and event.slashed == 0
        )
        if event.address and not is_staking_only_event:
            all_addresses.add(event.address)

    # Check against maximum pool size
    MAX_ADDRESSES = (
        1100  # Standard pool size 1000 + imagine some idle, some replacements etc
    )

    if len(all_addresses) > MAX_ADDRESSES:
        raise InvariantViolation(
            "resource_pool_integrity",
            f"Total unique addresses used ({len(all_addresses)}) exceeds pool capacity ({MAX_ADDRESSES})",
        )
