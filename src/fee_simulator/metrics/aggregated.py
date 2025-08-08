from src.fee_simulator.protocol.models import FeeEvent
from typing import List


def compute_agg_costs(fee_events: List[FeeEvent]) -> float:
    return sum(event.cost for event in fee_events)


def compute_agg_earnings(fee_events: List[FeeEvent]) -> float:
    return sum(event.earned for event in fee_events)


def compute_agg_burnt(fee_events: List[FeeEvent]) -> float:
    return sum(event.burned for event in fee_events)


def compute_agg_appealant_burnt(fee_events: List[FeeEvent]) -> float:
    return sum(event.burned for event in fee_events if event.role == "APPEALANT")
