from typing import List

from src.fee_simulator.protocol.models import FeeEvent


def compute_current_stake(address: str, fee_events: List[FeeEvent]) -> float:
    current_stake = 0
    for event in fee_events:
        if event.address == address:
            current_stake += event.staked
            current_stake -= event.slashed
    return current_stake


def compute_total_costs(fee_events: List[FeeEvent], address: str) -> float:
    total_costs = 0
    for event in fee_events:
        if event.address == address:
            total_costs += event.cost
    return total_costs


def compute_total_earnings(fee_events: List[FeeEvent], address: str) -> float:
    total_earnings = 0
    for event in fee_events:
        if event.address == address:
            total_earnings += event.earned
    return total_earnings


def compute_total_burnt(fee_events: List[FeeEvent], address: str) -> float:
    total_burnt = 0
    for event in fee_events:
        if event.address == address:
            total_burnt += event.burned
    return total_burnt


def compute_total_slashed(fee_events: List[FeeEvent], address: str) -> float:
    total_slashed = 0
    for event in fee_events:
        if event.address == address:
            total_slashed += event.slashed
    return total_slashed


def compute_all_zeros(fee_events: List[FeeEvent], address: str) -> bool:
    return (
        compute_total_costs(fee_events, address) == 0
        and compute_total_earnings(fee_events, address) == 0
        and compute_total_burnt(fee_events, address) == 0
        and compute_total_slashed(fee_events, address) == 0
    )


def compute_total_balance(fee_events: List[FeeEvent], address: str) -> float:
    costs = compute_total_costs(fee_events, address)
    earnings = compute_total_earnings(fee_events, address)
    return earnings - costs


def compute_txn_costs(fee_events: List[FeeEvent]) -> float:
    return sum(event.cost for event in fee_events)


def compute_txn_earnings(fee_events: List[FeeEvent]) -> float:
    return sum(event.earned for event in fee_events)


def compute_txn_burnt(fee_events: List[FeeEvent]) -> float:
    return sum(event.burned for event in fee_events)


def compute_txn_slashed(fee_events: List[FeeEvent]) -> float:
    return sum(event.slashed for event in fee_events)


def compute_txn_balance(fee_events: List[FeeEvent]) -> float:
    return compute_txn_earnings(fee_events) - compute_txn_costs(fee_events)


def compute_txn_appealants_burnt(fee_events: List[FeeEvent]) -> float:
    return sum(event.burned for event in fee_events if event.role == "APPEALANT")
