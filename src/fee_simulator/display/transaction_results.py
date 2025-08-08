from typing import List, Dict
from tabulate import tabulate
from src.fee_simulator.protocol.models import TransactionRoundResults, RoundLabel, Round, Rotation
from src.fee_simulator.display.utils import (
    Colors,
    ROUND_LABEL_COLORS,
    VOTE_TYPE_COLORS,
    format_address,
    format_vote,
    _create_table_rows,
    get_vote_summary,
)
from src.fee_simulator.core.majority import compute_majority, normalize_vote


def display_transaction_results(
    transaction_results: TransactionRoundResults,
    round_labels: List[RoundLabel],
    verbose: bool = False,
) -> None:
    """
    Display transaction results with formatted tables for rounds, rotations, and votes side by side.

    Args:
        transaction_results: Transaction round results to display.
        round_labels: List of round labels.
        verbose: Enable detailed logging if True (currently unused).
    """
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== TRANSACTION RESULTS ==={Colors.ENDC}\n")

    for round_idx, round_obj in enumerate(transaction_results.rounds):
        # Display round header with label
        label = (
            round_labels[round_idx]
            if round_idx < len(round_labels)
            else f"Round {round_idx}"
        )
        label_color = ROUND_LABEL_COLORS.get(label, Colors.CYAN)
        print()  # Add a small space after each rotation
        print(
            f"{Colors.BOLD}{Colors.CYAN}Distribution Label {round_idx}{Colors.ENDC} -- {Colors.colorize(label, label_color)}:"
        )

        # Display majority
        majority = compute_majority(round_obj.rotations[0].votes)
        print()  # Add a small space after each rotation
        majority_color = Colors.GREEN if majority != "UNDETERMINED" else Colors.YELLOW
        print(
            f"    {Colors.BOLD}Majority:{Colors.ENDC} {Colors.colorize(majority, majority_color)}"
        )
        print()  # Add a small space after each rotation

        if not round_obj.rotations:
            print(f"  {Colors.YELLOW}Empty round - no rotations{Colors.ENDC}")
            continue

        for rotation_idx, rotation in enumerate(round_obj.rotations):
            print(f"  {Colors.BOLD}Rotation {rotation_idx}:{Colors.ENDC}")

            if not rotation.votes:
                print(f"    {Colors.YELLOW}No votes in this rotation{Colors.ENDC}")
                continue

            # Votes table
            vote_data = []
            for addr, vote in rotation.votes.items():
                is_leader = isinstance(vote, list) and vote[0] in [
                    "LEADER_RECEIPT",
                    "LEADER_TIMEOUT",
                ]
                vote_display, vote_type = format_vote(vote, is_leader)
                vote_color = VOTE_TYPE_COLORS.get(vote_type, Colors.ENDC)
                if is_leader:
                    vote_color = Colors.CYAN
                vote_data.append(
                    [
                        format_address(addr),
                        Colors.colorize(vote_display, vote_color),
                    ]
                )
            votes_table = _create_table_rows(
                headers=["ADDRESS", "VOTE"], data=vote_data, title="Votes"
            )

            # Reserve votes table
            reserve_table = []
            if rotation.reserve_votes:
                reserve_data = []
                for addr, vote in rotation.reserve_votes.items():
                    vote_display, _ = format_vote(vote)
                    reserve_data.append(
                        [
                            format_address(addr),
                            Colors.colorize(vote_display, Colors.BLUE),
                        ]
                    )
                reserve_table = _create_table_rows(
                    headers=["ADDRESS", "RESERVE VOTE"],
                    data=reserve_data,
                    title="Reserve Votes",
                )

            # Vote summary table
            summary_data = get_vote_summary(rotation.votes)
            summary_table = _create_table_rows(
                headers=["VOTE TYPE", "COUNT"], data=summary_data, title="Vote Summary"
            )

            # Remove the title rows from votes_table, reserve_table, and summary_table for alignment
            votes_table_rows = (
                votes_table[1:]
                if votes_table and votes_table[0].startswith(f"{Colors.BOLD}Votes:")
                else votes_table
            )
            reserve_table_rows = (
                reserve_table[1:]
                if reserve_table
                and reserve_table[0].startswith(f"{Colors.BOLD}Reserve Votes:")
                else reserve_table
            )
            summary_table_rows = (
                summary_table[1:]
                if summary_table
                and summary_table[0].startswith(f"{Colors.BOLD}Vote Summary:")
                else summary_table
            )

            # Print titles side by side
            # titles = [f"{Colors.BOLD}Votes:{Colors.ENDC}"]
            # if reserve_table:
            #     titles.append(" " * 5 + f"{Colors.BOLD}Reserve Votes:{Colors.ENDC}")
            # titles.append(" " * 5 + f"{Colors.BOLD}Vote Summary:{Colors.ENDC}")
            # print("".join(titles))

            # Determine the maximum height of the tables
            max_height = max(
                len(votes_table_rows),
                len(reserve_table_rows) if reserve_table_rows else 0,
                len(summary_table_rows),
            )

            # Pad shorter tables with empty strings to align them
            votes_width = len(votes_table_rows[0]) if votes_table_rows else 0
            votes_table_rows.extend(
                [" " * votes_width] * (max_height - len(votes_table_rows))
            )

            reserve_width = len(reserve_table_rows[0]) if reserve_table_rows else 0
            if reserve_table_rows:
                reserve_table_rows.extend(
                    [" " * reserve_width] * (max_height - len(reserve_table_rows))
                )
            else:
                reserve_table_rows = [""] * max_height

            summary_width = len(summary_table_rows[0]) if summary_table_rows else 0
            summary_table_rows.extend(
                [" " * summary_width] * (max_height - len(summary_table_rows))
            )

            # Print tables side by side
            for i in range(max_height):
                row_parts = [votes_table_rows[i]]
                if reserve_table_rows[i].strip():
                    row_parts.append(" " * 5)  # Separator between tables
                    row_parts.append(reserve_table_rows[i])
                row_parts.append(" " * 5)
                row_parts.append(summary_table_rows[i])
                print("".join(row_parts))
