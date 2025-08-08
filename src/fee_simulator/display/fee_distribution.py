from typing import List
from src.fee_simulator.protocol.models import FeeEvent
from src.fee_simulator.display.utils import (
    Colors,
    ROUND_LABEL_COLORS,
    ROLE_COLORS,
    VOTE_TYPE_COLORS,
    format_address,
    format_vote,
    create_table,
    colorize_financial,
)
from src.fee_simulator.metrics.address_metrics import (
    compute_total_costs,
    compute_total_earnings,
    compute_total_burnt,
    compute_total_slashed,
    compute_current_stake,
)


def display_fee_distribution(fee_events: List[FeeEvent], verbose: bool = False) -> None:
    """
    Display a formatted table of fee events with a summary of totals, excluding initial staking events.

    Args:
        fee_events: List of FeeEvent objects to display.
        verbose: Enable detailed logging if True (currently unused).
    """
    print(
        f"\n{Colors.BOLD}{Colors.HEADER}=== DEBUG: FEE EVENT DISTRIBUTION ==={Colors.ENDC}\n"
    )

    # Prepare table headers
    headers = [
        "SEQ_ID",
        "ADDRESS",
        "ROUND",
        "LABEL",
        "ROLE",
        "VOTE",
        "COST",
        "EARNED",
        "SLASHED",
        "BURNED",
        "STAKED",
        "NET",
    ]

    # Filter out initial staking events (staked > 0, all other financials 0, round_index=None)
    display_events = [
        event
        for event in fee_events
        if not (
            event.staked > 0
            and event.cost == 0
            and event.earned == 0
            and event.slashed == 0
            and event.burned == 0
            and event.round_index is None
        )
    ]

    # Prepare table data
    table_data = []
    for event in sorted(display_events, key=lambda e: e.sequence_id):
        net = event.earned - event.cost - event.slashed - event.burned
        vote = event.vote if event.vote is not None else "NA"
        is_leader = event.role == "LEADER"
        vote_display, vote_type = format_vote(vote, is_leader)
        vote_color = VOTE_TYPE_COLORS.get(vote_type, Colors.ENDC)
        if is_leader:
            vote_color = Colors.CYAN
        round_index = event.round_index if event.round_index is not None else "-"
        round_label = event.round_label if event.round_label is not None else "NONE"
        role = event.role if event.role is not None else "NONE"
        table_data.append(
            [
                event.sequence_id,
                format_address(event.address),
                round_index,
                Colors.colorize(
                    round_label, ROUND_LABEL_COLORS.get(round_label, Colors.ENDC)
                ),
                Colors.colorize(role, ROLE_COLORS.get(role, Colors.ENDC)),
                Colors.colorize(vote_display, vote_color),
                colorize_financial(event.cost, negative_color=Colors.RED),
                colorize_financial(event.earned, positive_color=Colors.GREEN),
                colorize_financial(event.slashed, negative_color=Colors.RED),
                colorize_financial(event.burned, negative_color=Colors.RED),
                colorize_financial(event.staked, positive_color=Colors.BLUE),
                colorize_financial(net),
            ]
        )

    create_table(headers=headers, data=table_data)

    # Summary of totals (includes all events, even filtered ones)
    active_addresses = {event.address for event in fee_events}
    totals = {
        "cost": sum(compute_total_costs(fee_events, addr) for addr in active_addresses),
        "earned": sum(
            compute_total_earnings(fee_events, addr) for addr in active_addresses
        ),
        "slashed": sum(
            compute_total_slashed(fee_events, addr) for addr in active_addresses
        ),
        "burned": sum(
            compute_total_burnt(fee_events, addr) for addr in active_addresses
        ),
        "staked": sum(
            compute_current_stake(addr, fee_events) for addr in active_addresses
        ),
    }
    net_total = totals["earned"] - totals["cost"] - totals["slashed"] - totals["burned"]
    summary_data = [
        ["Cost", colorize_financial(totals["cost"], negative_color=Colors.RED)],
        ["Earned", colorize_financial(totals["earned"], positive_color=Colors.GREEN)],
        ["Slashed", colorize_financial(totals["slashed"], negative_color=Colors.RED)],
        ["Burned", colorize_financial(totals["burned"], negative_color=Colors.RED)],
        ["Staked", colorize_financial(totals["staked"], positive_color=Colors.BLUE)],
        ["Net", colorize_financial(net_total)],
    ]
    create_table(headers=["METRIC", "VALUE"], data=summary_data, title="Summary Totals")
