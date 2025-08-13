"""
Utility functions for working with round sizes.
This module helps transition from the old ROUND_SIZES to the new split structure.
"""

from typing import List, Optional
from src.fee_simulator.protocol.constants import NORMAL_ROUND_SIZES, APPEAL_ROUND_SIZES
from src.fee_simulator.protocol.types import RoundLabel
from src.fee_simulator.utils import is_appeal_round


def get_round_size(round_index: int, round_labels: List[RoundLabel] = None) -> int:
    """
    Get the size of a round based on its index and label.
    
    Implements the -2 rule for consecutive unsuccessful appeals.

    Args:
        round_index: The index of the round (0-based)
        round_labels: Optional list of round labels to determine if it's an appeal

    Returns:
        The number of participants in the round
    """
    if round_labels and round_index < len(round_labels):
        # Use the label to determine if it's an appeal round
        if is_appeal_round(round_labels[round_index]):
            appeal_index = get_appeal_index(round_index, round_labels)
            
            # Check if previous round was an unsuccessful appeal
            prev_was_unsuccessful = False
            if round_index > 0:
                prev_label = round_labels[round_index - 1]
                prev_was_unsuccessful = (
                    is_appeal_round(prev_label) and "UNSUCCESSFUL" in prev_label
                )
            
            return get_appeal_round_size(appeal_index, prev_was_unsuccessful)
        else:
            normal_index = get_normal_round_index(round_index, round_labels)
            return get_normal_round_size(normal_index)
    else:
        # Without labels, we cannot determine round type
        # This should not happen in the new architecture
        raise ValueError(
            f"Cannot determine round size for index {round_index} without round labels. "
            "The system now requires round labels to determine round types."
        )


def get_normal_round_size(normal_round_index: int) -> int:
    """
    Get the size of a normal round based on its index in the sequence of normal rounds.

    Args:
        normal_round_index: The index in the sequence of normal rounds (0, 1, 2, ...)

    Returns:
        The number of participants in the normal round
    """
    if normal_round_index < len(NORMAL_ROUND_SIZES):
        return NORMAL_ROUND_SIZES[normal_round_index]
    else:
        return NORMAL_ROUND_SIZES[-1]  # Use the last size for rounds beyond the list


def get_appeal_round_size(appeal_index: int, prev_was_unsuccessful: bool = False) -> int:
    """
    Get the size of an appeal round based on its index in the sequence of appeals.
    
    Implements the -2 rule: If the previous round was an unsuccessful appeal,
    reduce the size by 2 to act as a mechanical brake on escalation.

    Args:
        appeal_index: The index in the sequence of appeals (0, 1, 2, ...)
        prev_was_unsuccessful: True if the previous round was an unsuccessful appeal

    Returns:
        The number of participants in the appeal round
    """
    base_size = (
        APPEAL_ROUND_SIZES[appeal_index]
        if appeal_index < len(APPEAL_ROUND_SIZES)
        else APPEAL_ROUND_SIZES[-1]
    )
    
    # Apply -2 rule for consecutive unsuccessful appeals
    if prev_was_unsuccessful:
        return max(1, base_size - 2)  # Ensure at least 1 participant
    return base_size


def get_appeal_index(round_index: int, round_labels: List[RoundLabel]) -> int:
    """
    Get the appeal sequence index for a given round.

    Args:
        round_index: The absolute round index
        round_labels: List of round labels

    Returns:
        The index in the sequence of appeals (0 for first appeal, 1 for second, etc.)
    """
    appeal_count = 0
    for i in range(round_index):
        if i < len(round_labels) and is_appeal_round(round_labels[i]):
            appeal_count += 1
    return appeal_count


def get_normal_round_index(round_index: int, round_labels: List[RoundLabel]) -> int:
    """
    Get the normal round sequence index for a given round.

    Args:
        round_index: The absolute round index
        round_labels: List of round labels

    Returns:
        The index in the sequence of normal rounds (0 for first normal, 1 for second, etc.)
    """
    normal_count = 0
    for i in range(round_index + 1):
        if i < len(round_labels) and not is_appeal_round(round_labels[i]):
            normal_count += 1
    return (
        normal_count - 1
    )  # Subtract 1 because we counted up to and including current round


def get_round_size_for_bond(
    appeal_round_index: int, round_labels: List[RoundLabel]
) -> int:
    """
    Get the round size for appeal bond calculation.
    
    Implements the -2 rule for consecutive unsuccessful appeals.

    Args:
        appeal_round_index: The index of the appeal round
        round_labels: List of round labels

    Returns:
        The size of the appeal round for bond calculation
    """
    appeal_index = get_appeal_index(appeal_round_index, round_labels)
    
    # Check if previous round was an unsuccessful appeal
    prev_was_unsuccessful = False
    if appeal_round_index > 0:
        prev_label = round_labels[appeal_round_index - 1]
        prev_was_unsuccessful = (
            is_appeal_round(prev_label) and "UNSUCCESSFUL" in prev_label
        )
    
    return get_appeal_round_size(appeal_index, prev_was_unsuccessful)


def find_previous_normal_round(
    current_round_index: int, round_labels: List[RoundLabel]
) -> Optional[int]:
    """
    Find the index of the most recent normal (non-appeal) round before the given round.
    
    This utility function eliminates duplicated logic across multiple files.
    
    Args:
        current_round_index: The index of the current round
        round_labels: List of round labels
    
    Returns:
        The index of the most recent normal round, or None if no normal round exists before
    """
    for i in range(current_round_index - 1, -1, -1):
        if i < len(round_labels) and not is_appeal_round(round_labels[i]):
            return i
    return None
