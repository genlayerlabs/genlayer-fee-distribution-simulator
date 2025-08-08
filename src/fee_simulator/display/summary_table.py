from typing import List
from tabulate import tabulate
from src.fee_simulator.protocol.models import (
    TransactionRoundResults,
    FeeEvent,
    TransactionBudget,
    RoundLabel,
)
from src.fee_simulator.display.utils import (
    Colors,
    ROUND_LABEL_COLORS,
    ROLE_COLORS,
    format_address,
    create_table,
    _create_table_rows,
    colorize_financial,
    format_vote,
    VOTE_TYPE_COLORS,
)
from src.fee_simulator.metrics.address_metrics import (
    compute_total_costs,
    compute_total_earnings,
    compute_total_burnt,
    compute_total_slashed,
    compute_current_stake,
    compute_all_zeros,
)
from src.fee_simulator.protocol.constants import DEFAULT_STAKE


def display_summary_table(
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults,
    transaction_budget: TransactionBudget,
    round_labels: List[RoundLabel],
    verbose: bool = False,
) -> None:
    """
    Display a summary table of fee events with votes per round, and transaction budget and round labels side by side below.

    Args:
        fee_events: List of FeeEvent objects.
        transaction_results: Transaction round results.
        transaction_budget: Transaction budget parameters.
        round_labels: List of round labels.
        verbose: Enable detailed logging if True (currently unused).
    """
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== SUMMARY TABLE ==={Colors.ENDC}\n")

    # Collect active addresses
    active_addresses = {
        event.address
        for event in fee_events
        if not compute_all_zeros(fee_events, event.address)
    }

    # Collect votes per address from transaction_results
    votes_per_address = {}
    for addr in active_addresses:
        votes_per_address[addr] = {}

    # Step 1: Collect votes from transaction_results
    for round_idx, round_obj in enumerate(transaction_results.rounds):
        for rotation in round_obj.rotations:
            for addr, vote in rotation.votes.items():
                if addr not in active_addresses:
                    continue
                is_leader = isinstance(vote, list) and vote[0] in [
                    "LEADER_RECEIPT",
                    "LEADER_TIMEOUT",
                ]
                vote_display, vote_type = format_vote(vote, is_leader)
                vote_color = VOTE_TYPE_COLORS.get(vote_type, Colors.ENDC)
                if is_leader:
                    vote_color = Colors.CYAN
                votes_per_address[addr][round_idx] = Colors.colorize(
                    vote_display, vote_color
                )

    # Step 2: Collect votes from fee_events (merge with transaction_results votes)
    for addr in active_addresses:
        for event in fee_events:
            if (
                event.address == addr
                and event.round_index is not None
                and event.vote is not None
            ):
                round_idx = event.round_index
                is_leader = event.role == "LEADER"
                vote_display, vote_type = format_vote(event.vote, is_leader)
                vote_color = VOTE_TYPE_COLORS.get(vote_type, Colors.ENDC)
                if is_leader:
                    vote_color = Colors.CYAN
                votes_per_address[addr][round_idx] = Colors.colorize(
                    vote_display, vote_color
                )

    # Main summary table
    headers = [
        "ADDRESS",
        "ROLE",
        "COST",
        "EARNED",
        "SLASHED",
        "BURNED",
        "STAKED",
        "NET",
        "ROUNDS",
        "VOTES PER ROUND",
    ]
    table_data = []
    totals = {
        "cost": 0,
        "earned": 0,
        "slashed": 0,
        "burned": 0,
        "staked": 0,
        "net": 0,
    }

    for addr in sorted(active_addresses):
        addr_short = format_address(addr)
        roles = {
            event.role
            for event in fee_events
            if event.address == addr and event.role is not None
        }
        role_display = (
            ", ".join(
                Colors.colorize(role, ROLE_COLORS.get(role, Colors.ENDC))
                for role in sorted(roles)
            )
            if roles
            else "NONE"
        )
        cost = compute_total_costs(fee_events, addr)
        earned = compute_total_earnings(fee_events, addr)
        slashed = compute_total_slashed(fee_events, addr)
        burned = compute_total_burnt(fee_events, addr)
        staked = compute_current_stake(addr, fee_events)
        net = earned - cost - slashed - burned
        rounds = sorted(
            {
                event.round_index
                for event in fee_events
                if event.address == addr and event.round_index is not None
            }
        )

        if staked < (DEFAULT_STAKE * 0.99):
            addr_short += Colors.colorize(" [SLASHED]", Colors.RED)

        # Format votes per round
        votes_display = []
        for round_idx in sorted(votes_per_address[addr].keys()):
            vote = votes_per_address[addr][round_idx]
            votes_display.append(f"Round {round_idx}: {vote}")
        votes_str = ", ".join(votes_display) if votes_display else "-"

        table_data.append(
            [
                addr_short,
                role_display,
                colorize_financial(cost, negative_color=Colors.RED),
                colorize_financial(earned, positive_color=Colors.GREEN),
                colorize_financial(slashed, negative_color=Colors.RED),
                colorize_financial(burned, negative_color=Colors.RED),
                colorize_financial(staked, positive_color=Colors.BLUE),
                colorize_financial(net),
                ", ".join(str(r) for r in rounds) if rounds else "-",
                votes_str,
            ]
        )

        totals["cost"] += cost
        totals["earned"] += earned
        totals["slashed"] += slashed
        totals["burned"] += burned
        totals["staked"] += staked
        totals["net"] += net

    # Add totals row
    table_data.append(
        [
            Colors.BOLD + "TOTAL" + Colors.ENDC,
            "-",
            colorize_financial(totals["cost"], negative_color=Colors.RED),
            colorize_financial(totals["earned"], positive_color=Colors.GREEN),
            colorize_financial(totals["slashed"], negative_color=Colors.RED),
            colorize_financial(totals["burned"], negative_color=Colors.RED),
            colorize_financial(totals["staked"], positive_color=Colors.BLUE),
            colorize_financial(totals["net"]),
            "-",
            "-",
        ]
    )

    # Display the main summary table using the original create_table
    create_table(headers=headers, data=table_data)

    # Budget summary table
    budget_data = [
        [
            "Leader Timeout",
            Colors.colorize(str(transaction_budget.leaderTimeout), Colors.CYAN),
        ],
        [
            "Validators Timeout",
            Colors.colorize(str(transaction_budget.validatorsTimeout), Colors.CYAN),
        ],
        [
            "Appeal Rounds",
            Colors.colorize(str(transaction_budget.appealRounds), Colors.CYAN),
        ],
        ["Sender Address", format_address(transaction_budget.senderAddress)],
    ]
    if transaction_budget.appeals:
        budget_data.append(
            [
                "Appeals",
                ", ".join(
                    format_address(a.appealantAddress)
                    for a in transaction_budget.appeals
                ),
            ]
        )
    budget_table = _create_table_rows(
        headers=["PARAMETER", "VALUE"],
        data=budget_data,
        title="Transaction Budget Summary",
    )

    # Round labels table
    round_data = [
        [i, Colors.colorize(label, ROUND_LABEL_COLORS.get(label, Colors.YELLOW))]
        for i, label in enumerate(round_labels)
    ]
    round_table = _create_table_rows(
        headers=["ROUND", "LABEL"], data=round_data, title="Round Labels"
    )

    # Remove the title rows from budget_table and round_table for alignment
    budget_table_rows = (
        budget_table[1:]
        if budget_table
        and budget_table[0].startswith(f"{Colors.BOLD}Transaction Budget Summary:")
        else budget_table
    )
    round_table_rows = (
        round_table[1:]
        if round_table and round_table[0].startswith(f"{Colors.BOLD}Round Labels:")
        else round_table
    )

    # Print titles side by side
    titles = [f"{Colors.BOLD}Transaction Budget Summary:{Colors.ENDC}"]
    titles.append(" " * 5 + f"{Colors.BOLD}Round Labels:{Colors.ENDC}")
    print("\n" + "".join(titles))

    # Determine the maximum height of the tables
    max_height = max(len(budget_table_rows), len(round_table_rows))

    # Pad shorter tables with empty strings to align them
    budget_width = len(budget_table_rows[0]) if budget_table_rows else 0
    budget_table_rows.extend(
        [" " * budget_width] * (max_height - len(budget_table_rows))
    )

    round_width = len(round_table_rows[0]) if round_table_rows else 0
    round_table_rows.extend([" " * round_width] * (max_height - len(round_table_rows)))

    # Print tables side by side
    for i in range(max_height):
        row_parts = [budget_table_rows[i]]
        row_parts.append(" " * 5)  # Separator between tables
        row_parts.append(round_table_rows[i])
        print("".join(row_parts))
