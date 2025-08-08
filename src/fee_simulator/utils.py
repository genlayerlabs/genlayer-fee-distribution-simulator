import random
import string
import hashlib
from typing import Union
from decimal import Decimal, ROUND_DOWN
from typing import List
from src.fee_simulator.protocol.models import (
    FeeEvent,
    TransactionBudget,
    EventSequence,
)
from src.fee_simulator.protocol.constants import (
    DEFAULT_STAKE,
    NORMAL_ROUND_SIZES,
    APPEAL_ROUND_SIZES,
)
from src.fee_simulator.protocol.types import RoundLabel


def generate_random_eth_address() -> str:
    seed = "".join(random.choices(string.ascii_letters + string.digits, k=32))
    hashed = hashlib.sha256(seed.encode()).hexdigest()
    return "0x" + hashed[:40]


def initialize_constant_stakes(
    event_sequence: EventSequence, addresses: List[str]
) -> List[FeeEvent]:
    events = []
    for addr in addresses:
        events.append(
            FeeEvent(
                sequence_id=event_sequence.next_id(),
                address=addr,
                staked=DEFAULT_STAKE,
            )
        )
    return events


def compute_total_cost(transaction_budget: TransactionBudget) -> int:
    max_round_price = 0

    # Calculate costs for normal rounds
    num_normal_rounds = transaction_budget.appealRounds + 1
    for i in range(num_normal_rounds):
        round_size = (
            NORMAL_ROUND_SIZES[i]
            if i < len(NORMAL_ROUND_SIZES)
            else NORMAL_ROUND_SIZES[-1]
        )
        rotation_count = (
            transaction_budget.rotations[i]
            if i < len(transaction_budget.rotations)
            else 0
        )
        max_round_price += (
            round_size * (rotation_count + 1) * transaction_budget.validatorsTimeout
            + transaction_budget.leaderTimeout
        )

    # Calculate costs for appeal rounds
    for i in range(transaction_budget.appealRounds):
        round_size = (
            APPEAL_ROUND_SIZES[i]
            if i < len(APPEAL_ROUND_SIZES)
            else APPEAL_ROUND_SIZES[-1]
        )
        max_round_price += (
            round_size * transaction_budget.validatorsTimeout
            + transaction_budget.leaderTimeout
        )

    # Calculate appeal rewards (50% return on appeal bonds)
    total_appeal_rewards = 0
    for i in range(transaction_budget.appealRounds):
        round_size = (
            APPEAL_ROUND_SIZES[i]
            if i < len(APPEAL_ROUND_SIZES)
            else APPEAL_ROUND_SIZES[-1]
        )
        appeal_bond = (
            round_size * transaction_budget.validatorsTimeout
            + transaction_budget.leaderTimeout
        )
        appeal_reward = int(appeal_bond * 0.5)  # 50% additional return
        total_appeal_rewards += appeal_reward

    total_cost = max_round_price + total_appeal_rewards
    return total_cost


def to_wei(value: Union[int, float, str, Decimal], decimals: int = 18) -> int:
    try:
        d = Decimal(str(value))
        return int(d * (10**decimals))
    except (ValueError, TypeError) as e:
        raise ValueError(f"Cannot convert {value} to Wei: {e}")


def from_wei(value: int, decimals: int = 18) -> Decimal:
    return Decimal(value) / (10**decimals)


def split_amount(amount: int, num_recipients: int, decimals: int = 18) -> int:
    if num_recipients == 0:
        raise ValueError("Number of recipients cannot be zero")

    d_amount = from_wei(amount, decimals)
    per_recipient = (d_amount / num_recipients).quantize(
        Decimal("0." + "0" * (decimals - 1) + "1"), rounding=ROUND_DOWN
    )
    return to_wei(per_recipient, decimals)


def compute_round_size_indices(round_types: List[RoundLabel]) -> List[int]:
    """
    DEPRECATED: This function is kept for backward compatibility.
    Use get_round_size() with the new split structure instead.
    """
    if not round_types:
        return []

    indices = []
    next_normal_index = 0
    consecutive_appeals = 0

    for round_type in round_types:
        is_appeal = is_appeal_round(round_type)

        if is_appeal:
            consecutive_appeals += 1
            # First appeal uses the odd index after the last normal
            # Subsequent appeals skip even indices
            appeal_index = next_normal_index + (2 * consecutive_appeals - 1)
            indices.append(appeal_index)
        else:
            # Normal round resets the appeal counter
            consecutive_appeals = 0
            indices.append(next_normal_index)
            next_normal_index += 2

    return indices


def get_round_size(round_index: int, round_types: List[RoundLabel]) -> int:
    """
    Get the size of a round based on its index and type.

    With the new split structure, this is much simpler:
    - Count how many normal rounds came before this one
    - Count how many appeal rounds came before this one
    - Use the appropriate list (NORMAL_ROUND_SIZES or APPEAL_ROUND_SIZES)
    """
    if round_index >= len(round_types):
        raise IndexError(
            f"Round index {round_index} out of bounds for {len(round_types)} rounds"
        )

    # Count normal and appeal rounds up to this index
    normal_count = 0
    appeal_count = 0

    for i in range(round_index + 1):
        if i < len(round_types):
            if is_appeal_round(round_types[i]):
                appeal_count += 1
            else:
                normal_count += 1

    # Get the size based on the round type
    if is_appeal_round(round_types[round_index]):
        # This is an appeal round
        appeal_index = appeal_count - 1  # 0-based index
        if appeal_index < len(APPEAL_ROUND_SIZES):
            return APPEAL_ROUND_SIZES[appeal_index]
        else:
            return APPEAL_ROUND_SIZES[
                -1
            ]  # Use the last size for rounds beyond the list
    else:
        # This is a normal round
        normal_index = normal_count - 1  # 0-based index
        if normal_index < len(NORMAL_ROUND_SIZES):
            return NORMAL_ROUND_SIZES[normal_index]
        else:
            return NORMAL_ROUND_SIZES[
                -1
            ]  # Use the last size for rounds beyond the list


def is_appeal_round(round_label: RoundLabel) -> bool:
    return round_label.startswith("APPEAL_")
