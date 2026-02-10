from typing import List, Dict, Optional, Tuple
from src.fee_simulator.protocol.models import TransactionRoundResults
from src.fee_simulator.protocol.types import RoundLabel, Vote
from src.fee_simulator.core.majority import compute_majority


# Data extraction functions
def extract_rounds_data(
    transaction_results: TransactionRoundResults,
) -> Tuple[List[Dict[str, Vote]], List[Optional[str]]]:
    """Extract vote dictionaries and leader addresses from transaction results."""
    rounds = []
    leader_addresses = []

    for round_obj in transaction_results.rounds:
        if round_obj.rotations:
            votes = round_obj.rotations[-1].votes
            rounds.append(votes)
            leader_addresses.append(next(iter(votes.keys())) if votes else None)
        else:
            rounds.append({})
            leader_addresses.append(None)

    return rounds, leader_addresses


def get_leader_action(
    votes: Dict[str, Vote], leader_address: Optional[str]
) -> Optional[str]:
    """Extract the leader's action from their vote."""
    if not leader_address or leader_address not in votes:
        return None

    vote = votes[leader_address]
    if isinstance(vote, list) and len(vote) >= 2:
        return vote[0]
    return None


# Round classification functions
def is_single_leader_timeout(
    round_index: int, total_rounds: int, leader_action: Optional[str]
) -> bool:
    """Check if this is the only round and the leader timed out."""
    return round_index == 0 and total_rounds == 1 and leader_action == "LEADER_TIMEOUT"


def is_appeal_round_label(label: RoundLabel) -> bool:
    """Check if a round label indicates an appeal round."""
    return label.startswith("APPEAL_")


def is_likely_appeal_round(
    votes: Dict[str, Vote], leader_address: Optional[str]
) -> bool:
    """
    Determine if a round is likely an appeal based on vote patterns.

    Appeal rounds have distinct patterns:
    - Leader appeals: All participants have "NA" votes (but not LEADER_TIMEOUT)
    - Validator appeals: No leader receipt, just AGREE/DISAGREE votes
    - Normal rounds: Have a leader receipt (["LEADER_RECEIPT", vote]) or leader timeout
    """
    if not votes:
        return False

    # Check if there's a LEADER_TIMEOUT - this is NOT an appeal
    if leader_address and leader_address in votes:
        vote = votes[leader_address]
        if isinstance(vote, list) and len(vote) >= 1 and vote[0] == "LEADER_TIMEOUT":
            return False  # Leader timeout is a normal round, not an appeal

    # Check if all votes are NA (leader appeal pattern)
    all_na = all(
        vote == "NA" or (isinstance(vote, list) and vote[1] == "NA")
        for vote in votes.values()
    )
    if all_na:
        return True

    # Check if there's a leader receipt (normal round pattern)
    has_leader_receipt = False
    if leader_address and leader_address in votes:
        vote = votes[leader_address]
        if isinstance(vote, list) and len(vote) >= 1 and vote[0] == "LEADER_RECEIPT":
            has_leader_receipt = True

    # If no leader receipt and votes are AGREE/DISAGREE, likely validator appeal
    if not has_leader_receipt:
        vote_types = set()
        for vote in votes.values():
            if isinstance(vote, str) and vote in ["AGREE", "DISAGREE"]:
                vote_types.add(vote)
            elif isinstance(vote, list):
                for v in vote:
                    if v in ["AGREE", "DISAGREE"]:
                        vote_types.add(v)

        # If we have AGREE/DISAGREE votes without leader receipt, it's likely a validator appeal
        if vote_types:
            return True

    return False


def classify_normal_round(
    leader_action: Optional[str], is_only_round: bool
) -> RoundLabel:
    """Classify a non-appeal round based on leader action."""
    if leader_action == "LEADER_TIMEOUT":
        if is_only_round:
            return "LEADER_TIMEOUT_50_PERCENT"
        return "LEADER_TIMEOUT"
    return "NORMAL_ROUND"


# Appeal classification functions
def classify_leader_timeout_appeal(
    round_index: int,
    rounds: List[Dict[str, Vote]],
    leader_addresses: List[Optional[str]],
) -> RoundLabel:
    """Classify an appeal that follows a leader timeout."""
    # Check if there's a next round
    if round_index + 1 >= len(rounds):
        return "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL"

    # Check next round's leader action
    next_leader_action = get_leader_action(
        rounds[round_index + 1], leader_addresses[round_index + 1]
    )

    if next_leader_action == "LEADER_TIMEOUT":
        return "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL"
    else:
        return "APPEAL_LEADER_TIMEOUT_SUCCESSFUL"


def classify_vote_appeal(
    round_index: int,
    rounds: List[Dict[str, Vote]],
    leader_addresses: List[Optional[str]],
    prev_majority: str,
) -> RoundLabel:
    """Classify an appeal based on vote majorities."""
    # Get appeal round majority
    appeal_votes = rounds[round_index]
    appeal_majority = compute_majority(appeal_votes) if appeal_votes else "UNDETERMINED"

    # Leader appeal: previous round had no clear majority
    if prev_majority in ["UNDETERMINED", "DISAGREE"]:
        # If this is the last round, check if appeal reached a clear majority
        if round_index + 1 >= len(rounds):
            if appeal_majority not in ["UNDETERMINED", "DISAGREE"]:
                return "APPEAL_LEADER_SUCCESSFUL"
            else:
                return "APPEAL_LEADER_UNSUCCESSFUL"

        # Otherwise check next round
        next_votes = rounds[round_index + 1]
        next_leader_addr = (
            leader_addresses[round_index + 1]
            if round_index + 1 < len(leader_addresses)
            else None
        )
        next_leader_action = get_leader_action(next_votes, next_leader_addr)

        # Special case: if next round is LEADER_TIMEOUT, consider it successful
        # because the timeout is not related to the appeal outcome
        if next_leader_action == "LEADER_TIMEOUT":
            return "APPEAL_LEADER_SUCCESSFUL"

        next_majority = compute_majority(rounds[round_index + 1])
        if next_majority not in ["UNDETERMINED", "DISAGREE"]:
            return "APPEAL_LEADER_SUCCESSFUL"
        else:
            return "APPEAL_LEADER_UNSUCCESSFUL"

    # Validator appeal: previous round had a clear majority
    else:
        # Successful if validators changed the outcome
        if appeal_majority != prev_majority and appeal_majority != "UNDETERMINED":
            return "APPEAL_VALIDATOR_SUCCESSFUL"
        else:
            return "APPEAL_VALIDATOR_UNSUCCESSFUL"


def classify_appeal_round(
    round_index: int,
    rounds: List[Dict[str, Vote]],
    leader_addresses: List[Optional[str]],
) -> RoundLabel:
    """Classify an appeal round based on the previous round's outcome."""
    if round_index == 0:  # Safety check
        return "EMPTY_ROUND"

    # For consecutive appeals, we need to find the original normal round being appealed
    # Look back to find the most recent non-appeal round
    original_round_index = round_index - 1
    while original_round_index > 0:
        # Check if the previous round is likely an appeal
        prev_votes = rounds[original_round_index]
        prev_leader_addr = (
            leader_addresses[original_round_index]
            if original_round_index < len(leader_addresses)
            else None
        )
        if is_likely_appeal_round(prev_votes, prev_leader_addr):
            # Keep looking back
            original_round_index -= 1
        else:
            # Found a non-appeal round
            break

    # Now classify based on the original normal round
    orig_round = rounds[original_round_index]
    orig_leader_action = get_leader_action(
        orig_round, leader_addresses[original_round_index]
    )

    if orig_leader_action == "LEADER_TIMEOUT":
        return classify_leader_timeout_appeal(round_index, rounds, leader_addresses)
    else:
        orig_majority = compute_majority(orig_round)
        return classify_vote_appeal(
            round_index, rounds, leader_addresses, orig_majority
        )


# Special case patterns
SPECIAL_CASE_PATTERNS = [
    {
        "name": "Skip round before successful appeal",
        "pattern": [
            "NORMAL_ROUND",
            ["APPEAL_LEADER_SUCCESSFUL", "APPEAL_VALIDATOR_SUCCESSFUL"],
            "NORMAL_ROUND",
        ],
        "changes": {0: "SKIP_ROUND"},
    },
    {
        "name": "Leader timeout 150% after successful appeal",
        "pattern": [
            "LEADER_TIMEOUT",
            "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
            "NORMAL_ROUND",
        ],
        "changes": {0: "SKIP_ROUND", 2: "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND"},
    },
    {
        "name": "Equal split after unsuccessful leader appeal with undetermined outcome",
        "pattern": [
            "NORMAL_ROUND",
            "APPEAL_LEADER_UNSUCCESSFUL",
            "NORMAL_ROUND",
        ],
        "condition": lambda rounds, i: i + 2 < len(rounds)
        and rounds[i + 2]
        and compute_majority(rounds[i + 2]) == "UNDETERMINED",
        "changes": {2: "EQUAL_SPLIT"},
    },
    {
        "name": "Split appeal bond after unsuccessful appeal",
        "pattern": [
            "NORMAL_ROUND",
            ["APPEAL_LEADER_UNSUCCESSFUL", "APPEAL_VALIDATOR_UNSUCCESSFUL"],
            "NORMAL_ROUND",
        ],
        "condition": lambda rounds, i: i + 2 < len(rounds)
        and rounds[i + 2]
        and compute_majority(rounds[i + 2]) in ["UNDETERMINED", "DISAGREE"],
        "changes": {2: "SPLIT_PREVIOUS_APPEAL_BOND"},
    },
    {
        "name": "Leader timeout 50% after unsuccessful appeal",
        "pattern": [
            "LEADER_TIMEOUT_50_PERCENT",
            "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
            "LEADER_TIMEOUT",
        ],
        "changes": {
            2: "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        },
    },
    {
        "name": "Chained leader timeout 50% after unsuccessful appeal",
        "pattern": [
            "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
            "LEADER_TIMEOUT",
        ],
        "changes": {
            2: "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        },
    },
    {
        "name": "Any leader timeout after unsuccessful leader appeal",
        "pattern": [
            "LEADER_TIMEOUT",
            "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
            "LEADER_TIMEOUT",
        ],
        "changes": {
            0: "LEADER_TIMEOUT_50_PERCENT",
            2: "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        },
    },
    {
        "name": "Leader timeout after chained unsuccessful appeals",
        "pattern": [
            "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
            "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL",
            "LEADER_TIMEOUT",
        ],
        "changes": {
            2: "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND",
        },
    },
]


def matches_pattern(labels: List[RoundLabel], start_idx: int, pattern: List) -> bool:
    """Check if labels match a pattern starting at the given index."""
    if start_idx + len(pattern) > len(labels):
        return False

    for i, expected in enumerate(pattern):
        actual = labels[start_idx + i]

        # Handle list of possible values
        if isinstance(expected, list):
            if actual not in expected:
                return False
        # Handle single value
        elif actual != expected:
            return False

    return True


def apply_special_cases(
    labels: List[RoundLabel], rounds: List[Dict[str, Vote]]
) -> List[RoundLabel]:
    """Apply special case transformations based on patterns."""
    new_labels = labels.copy()
    processed_indices = set()

    # Try to match each pattern
    for pattern_config in SPECIAL_CASE_PATTERNS:
        pattern = pattern_config["pattern"]

        # Look for this pattern in the labels
        for i in range(len(new_labels) - len(pattern) + 1):
            # Skip if the indices we want to change are already processed
            changes_to_make = pattern_config["changes"]
            if any((i + offset) in processed_indices for offset in changes_to_make):
                continue

            # Check if pattern matches
            if not matches_pattern(new_labels, i, pattern):
                continue

            # Check additional condition if present
            if "condition" in pattern_config:
                if not pattern_config["condition"](rounds, i):
                    continue

            # Apply changes
            for offset, new_label in pattern_config["changes"].items():
                new_labels[i + offset] = new_label
                # Mark only the changed indices as processed
                processed_indices.add(i + offset)

    return new_labels


# Main function
def label_rounds(transaction_results: TransactionRoundResults) -> List[RoundLabel]:
    """
    Label each round based on its characteristics and relationships with other rounds.

    The labeling process:
    1. Extract round data from transaction results
    2. Classify each round individually
    3. Apply special case patterns that depend on round sequences
    """
    # Extract data
    rounds, leader_addresses = extract_rounds_data(transaction_results)

    # Initial classification
    labels = []
    total_rounds = len(rounds)

    for i, round_votes in enumerate(rounds):
        # Handle empty rounds
        if not round_votes:
            labels.append("EMPTY_ROUND")
            continue

        # Get leader action
        leader_action = get_leader_action(round_votes, leader_addresses[i])

        # Special case: single leader timeout
        if is_single_leader_timeout(i, total_rounds, leader_action):
            labels.append("LEADER_TIMEOUT_50_PERCENT")
            continue

        # Check for the specific pattern: LEADER_TIMEOUT -> APPEAL -> LEADER_TIMEOUT
        # where the appeal will be unsuccessful
        if i == 0 and leader_action == "LEADER_TIMEOUT" and i + 2 < total_rounds:
            # Check if next round looks like an appeal and round after that is leader timeout
            next_round_votes = rounds[i + 1] if i + 1 < total_rounds else {}
            next_leader_addr = leader_addresses[i + 1] if i + 1 < total_rounds else None
            next_leader_action = get_leader_action(
                rounds[i + 2], leader_addresses[i + 2]
            )

            if (
                is_likely_appeal_round(next_round_votes, next_leader_addr)
                and next_leader_action == "LEADER_TIMEOUT"
            ):
                # This matches the pattern, so first timeout gets 50%
                labels.append("LEADER_TIMEOUT_50_PERCENT")
                continue

        # Classify based on round type - check vote patterns instead of index
        if is_likely_appeal_round(round_votes, leader_addresses[i]):
            label = classify_appeal_round(i, rounds, leader_addresses)
        else:
            is_only_round = total_rounds == 1
            label = classify_normal_round(leader_action, is_only_round)

        labels.append(label)

    # Apply special case transformations
    labels = apply_special_cases(labels, rounds)

    # Post-processing: Handle last round LEADER_TIMEOUT that didn't match any pattern
    if labels and labels[-1] == "LEADER_TIMEOUT":
        # Check if it's actually a leader timeout (not misclassified)
        last_round_votes = rounds[-1] if rounds else {}
        last_leader_addr = leader_addresses[-1] if leader_addresses else None
        last_leader_action = get_leader_action(last_round_votes, last_leader_addr)

        if last_leader_action == "LEADER_TIMEOUT":
            # This is a genuine leader timeout at the end that didn't match any pattern
            # It should get 50% distribution
            labels[-1] = "LEADER_TIMEOUT_50_PERCENT"

    return labels
