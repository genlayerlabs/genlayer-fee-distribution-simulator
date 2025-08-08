from typing import Dict, List, Tuple, Optional
from src.fee_simulator.protocol.types import Vote, MajorityOutcome
from collections import Counter
from src.fee_simulator.protocol.constants import DEFAULT_HASH


def normalize_vote(vote_value: Vote) -> Vote:
    """
    Convert any vote value to a standard VoteType for comparison.

    Args:
        vote_value: A vote value which could be a simple VoteType or a list with LeaderAction

    Returns:
        The normalized VoteType
    """
    if isinstance(vote_value, list):
        # Return the vote type (second element for leader, first for validator)
        return (
            vote_value[1]
            if vote_value[0] in ["LEADER_RECEIPT", "LEADER_TIMEOUT"]
            else vote_value[0]
        )
    return vote_value


def extract_hash(vote_value: Vote) -> str:
    """
    Extract hash from a vote value if present.

    Args:
        vote_value: A vote value which could be a simple VoteType or a list with hash

    Returns:
        Hash value or DEFAULT_HASH if not present
    """
    if not isinstance(vote_value, list) or len(vote_value) < 2:
        return DEFAULT_HASH

    if vote_value[0] in ["LEADER_RECEIPT", "LEADER_TIMEOUT"]:
        # ["LeaderReceipt", "Vote", "Hash"]
        return vote_value[2] if len(vote_value) >= 3 else DEFAULT_HASH
    else:
        # ["Vote", "Hash"]
        return vote_value[1]


def compute_majority(rotation: Dict[str, Vote]) -> MajorityOutcome:
    """
    Compute the majority vote type.

    Args:
        rotation: Dictionary mapping addresses to votes

    Returns:
        Majority vote type or "UNDETERMINED" if no majority
    """
    if not rotation:
        return "UNDETERMINED"

    # Count votes by type
    vote_counts = {"AGREE": 0, "DISAGREE": 0, "TIMEOUT": 0, "IDLE": 0}
    for addr, vote in rotation.items():
        vote_type = normalize_vote(vote)
        if vote_type in vote_counts:
            vote_counts[vote_type] += 1

    # Determine if there's a majority
    total_votes = len(rotation)
    majority_threshold = (total_votes // 2) + 1

    if vote_counts["AGREE"] >= majority_threshold:
        return "AGREE"
    elif vote_counts["DISAGREE"] >= majority_threshold:
        return "DISAGREE"
    elif vote_counts["TIMEOUT"] >= majority_threshold:
        return "TIMEOUT"
    else:
        return "UNDETERMINED"


def compute_majority_hash(rotation: Dict[str, Vote]) -> Optional[str]:
    """
    Compute the majority hash, regardless of vote type.

    Args:
        rotation: Dictionary mapping addresses to votes

    Returns:
        Majority hash or None if no majority
    """
    if not rotation:
        return None

    # Collect all hashes from all votes
    hashes = []
    for addr, vote in rotation.items():
        hash_value = extract_hash(vote)
        if hash_value != DEFAULT_HASH:
            hashes.append(hash_value)

    # If no hashes found, return None
    if not hashes:
        return None

    # Count hash occurrences
    hash_counter = Counter(hashes)
    most_common_hash, count = hash_counter.most_common(1)[0]

    # Check if this hash has a majority
    total_votes = len(rotation)
    majority_threshold = (total_votes // 2) + 1

    if count >= majority_threshold:
        return most_common_hash
    else:
        return None


def who_is_in_vote_majority(
    rotation: Dict[str, Vote], majority_vote: MajorityOutcome
) -> Tuple[List[str], List[str]]:
    """
    Determine which addresses voted for the majority vote type.

    Args:
        rotation: Dictionary mapping addresses to votes
        majority_vote: The majority vote type

    Returns:
        Lists of addresses in vote majority and minority
    """
    majority_addresses = []
    for addr, vote in rotation.items():
        if normalize_vote(vote) == majority_vote:
            majority_addresses.append(addr)

    minority_addresses = list(set(rotation.keys()) - set(majority_addresses))
    return majority_addresses, minority_addresses


def who_is_in_hash_majority(
    rotation: Dict[str, Vote], majority_hash: str
) -> Tuple[List[str], List[str]]:
    """
    Determine which addresses provided the majority hash.

    Args:
        rotation: Dictionary mapping addresses to votes
        majority_hash: The majority hash

    Returns:
        Lists of addresses in hash majority and minority
    """
    majority_addresses = []
    minority_addresses = []

    for addr, vote in rotation.items():
        hash_value = extract_hash(vote)
        if hash_value == majority_hash:
            majority_addresses.append(addr)
        else:
            minority_addresses.append(addr)

    return majority_addresses, minority_addresses
