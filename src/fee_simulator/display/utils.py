from typing import Union, List, Dict, Tuple
from tabulate import tabulate
from src.fee_simulator.protocol.types import Vote


# Terminal colors
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

    @classmethod
    def colorize(cls, text: str, color: str) -> str:
        return f"{color}{text}{cls.ENDC}" if color else text


# Common color mappings
ROUND_LABEL_COLORS = {
    "NORMAL_ROUND": Colors.GREEN,
    "EMPTY_ROUND": Colors.YELLOW,
    "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL": Colors.RED,
    "APPEAL_LEADER_TIMEOUT_SUCCESSFUL": Colors.CYAN,
    "APPEAL_LEADER_SUCCESSFUL": Colors.BLUE,
    "APPEAL_LEADER_UNSUCCESSFUL": Colors.RED,
    "APPEAL_VALIDATOR_SUCCESSFUL": Colors.BLUE,
    "APPEAL_VALIDATOR_UNSUCCESSFUL": Colors.RED,
    "LEADER_TIMEOUT": Colors.YELLOW,
    "SKIP_ROUND": Colors.YELLOW,
    "LEADER_TIMEOUT_50_PERCENT": Colors.CYAN,
    "SPLIT_PREVIOUS_APPEAL_BOND": Colors.CYAN,
    "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND": Colors.BLUE,
    "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND": Colors.GREEN,
}

ROLE_COLORS = {
    "LEADER": Colors.CYAN,
    "VALIDATOR": Colors.GREEN,
    "SENDER": Colors.BLUE,
    "APPEALANT": Colors.YELLOW,
    "TOPPER": Colors.RED,
}

VOTE_TYPE_COLORS = {
    "AGREE": Colors.GREEN,
    "DISAGREE": Colors.RED,
    "TIMEOUT": Colors.YELLOW,
    "IDLE": Colors.BLUE,
    "NA": Colors.CYAN,
    "LEADER_RECEIPT": Colors.CYAN,
    "LEADER_TIMEOUT": Colors.CYAN,
}


def format_address(addr: str, max_len: int = 20) -> str:
    """Format an address to show first 8 and last 6 characters if too long."""
    return f"{addr[:8]}...{addr[-6:]}" if len(addr) > max_len else addr


def format_vote(vote: Vote, is_leader: bool = False) -> Tuple[str, str]:
    """Format a vote and determine its type.

    Returns:
        Tuple of (display string, vote type).
    """
    if isinstance(vote, list):
        vote_display = ", ".join(str(v) for v in vote)
        vote_type = vote[1] if is_leader else vote[0]
    else:
        vote_display = vote
        vote_type = vote

    return vote_display, vote_type


def colorize_financial(
    value: float, positive_color: str = Colors.GREEN, negative_color: str = Colors.RED
) -> str:
    """Colorize a financial value based on whether it's positive or negative."""
    color = (
        positive_color if value > 0 else negative_color if value < 0 else Colors.ENDC
    )
    return Colors.colorize(str(value), color)


def create_table(headers: List[str], data: List[List[str]], title: str = "") -> None:
    """Create and print a formatted table with an optional title."""
    if title:
        print(f"\n{Colors.BOLD}{title}:{Colors.ENDC}")
    if not data:
        print(f"{Colors.YELLOW}No data to display.{Colors.ENDC}")
        return
    print(tabulate(data, headers=headers, tablefmt="fancy_grid"))


def _create_table_rows(
    headers: List[str], data: List[List[str]], title: str = ""
) -> List[str]:
    """
    Create a table and return its rows as a list of strings, without printing.

    Args:
        headers: List of column headers.
        data: List of rows, where each row is a list of column values.
        title: Optional title for the table.

    Returns:
        List of strings representing each row of the table, including the title if provided.
    """
    table_rows = []
    if title:
        table_rows.append(f"{Colors.BOLD}{title}:{Colors.ENDC}")
    if not data:
        table_rows.append(f"{Colors.YELLOW}No data to display.{Colors.ENDC}")
        return table_rows

    # Use tabulate to generate the table as a string, then split into rows
    table_str = tabulate(data, headers=headers, tablefmt="fancy_grid")
    table_rows.extend(table_str.split("\n"))
    return table_rows


def get_vote_summary(votes: Dict[str, Vote]) -> List[List[str]]:
    """Summarize votes by type and count."""
    vote_counts = {
        "AGREE": 0,
        "DISAGREE": 0,
        "TIMEOUT": 0,
        "IDLE": 0,
        "NA": 0,
    }
    for vote in votes.values():
        is_leader = isinstance(vote, list) and vote[0] in [
            "LEADER_RECEIPT",
            "LEADER_TIMEOUT",
        ]
        _, vote_type = format_vote(vote, is_leader)
        if vote_type in vote_counts:
            vote_counts[vote_type] += 1

    return [
        [
            vote_type,
            Colors.colorize(str(count), VOTE_TYPE_COLORS.get(vote_type, Colors.ENDC)),
        ]
        for vote_type, count in vote_counts.items()
        if count > 0
    ]


def display_test_description(test_name: str, test_description: str) -> None:
    print("\n\n\n\n\n\n\n\n")
    print(f"{Colors.CYAN}{'====' * 20}{Colors.ENDC}")
    print(f"\n{Colors.BOLD}{Colors.CYAN}=== TEST DESCRIPTION ==={Colors.ENDC}")
    print(f"{Colors.BOLD}Test:{Colors.ENDC} {test_name}")
    print(f"{Colors.BOLD}Description:{Colors.ENDC} {test_description}\n")
    print(f"{Colors.CYAN}{'====' * 20}{Colors.ENDC}")
