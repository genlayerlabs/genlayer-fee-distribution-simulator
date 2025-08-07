"""Invariant 16: A coalition of validators who consistently dissent against the
majority should not make a net profit."""

from typing import List, Dict
from collections import defaultdict
from fee_simulator.models import FeeEvent, TransactionRoundResults
from fee_simulator.types import RoundLabel
from fee_simulator.core.majority import compute_majority, normalize_vote
from .common import InvariantViolation


def check_no_profit_from_griefing(
    fee_events: List[FeeEvent],
    transaction_results: TransactionRoundResults,
    round_labels: List[RoundLabel],
) -> None:
    """
    A validator is considered part of a griefing coalition if they vote with the
    minority more often than the majority. This invariant checks that the total
    net profit of this coalition over the entire transaction is not positive.
    Dissent that leads to a successful appeal is not considered griefing.
    """
    # Step 1: Tally all votes as majority or minority
    vote_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    undetermined_rounds = set()
    round_majority_outcomes = {}

    for i, round_obj in enumerate(transaction_results.rounds):
        if not round_obj.rotations or not any(r.votes for r in round_obj.rotations):
            undetermined_rounds.add(i)
            continue

        all_votes_in_round = {
            addr: vote
            for rotation in round_obj.rotations
            for addr, vote in rotation.votes.items()
        }
        majority_outcome = compute_majority(all_votes_in_round)
        round_majority_outcomes[i] = majority_outcome

        if majority_outcome == "UNDETERMINED":
            undetermined_rounds.add(i)
            continue

        for addr, vote_details in all_votes_in_round.items():
            validator_vote = normalize_vote(vote_details)
            if validator_vote == majority_outcome:
                vote_counts[addr]["majority"] += 1
            else:
                vote_counts[addr]["minority"] += 1

    # Step 2: Correct the tally for successful appellants.
    # A successful appeal means the appellant's original dissenting vote was correct.
    for event in fee_events:
        if event.role == "APPEALANT" and event.earned > 0:
            appellant_addr = event.address
            appeal_round_index = event.round_index

            # An appeal in round `i` pertains to actions in round `i-1`.
            original_dissent_round = appeal_round_index - 1
            if original_dissent_round < 0:
                continue

            # Check if the original vote was indeed a minority vote
            original_round_votes = {
                addr: vote
                for r in transaction_results.rounds[original_dissent_round].rotations
                for addr, vote in r.votes.items()
            }
            if appellant_addr in original_round_votes:
                appellant_original_vote = normalize_vote(
                    original_round_votes[appellant_addr]
                )
                majority_outcome = round_majority_outcomes.get(original_dissent_round)

                if (
                    majority_outcome
                    and majority_outcome != "UNDETERMINED"
                    and appellant_original_vote != majority_outcome
                ):
                    # This was a minority vote that was proven correct.
                    # Retroactively change it from minority to majority.
                    if vote_counts[appellant_addr].get("minority", 0) > 0:
                        vote_counts[appellant_addr]["minority"] -= 1
                        vote_counts[appellant_addr]["majority"] += 1

    # Step 3: Identify the true griefing coalition from the corrected tally
    griefing_coalition = {
        addr
        for addr, counts in vote_counts.items()
        if counts.get("minority", 0) > counts.get("majority", 0)
    }

    if not griefing_coalition:
        return

    # Step 4: Calculate the coalition's total net profit
    coalition_net_profit = 0
    for addr in griefing_coalition:
        earnings = sum(
            e.earned
            for e in fee_events
            if e.address == addr and e.round_index not in undetermined_rounds
        )
        costs = sum(
            e.cost
            for e in fee_events
            if e.address == addr and e.round_index not in undetermined_rounds
        )
        penalties = sum(
            (e.burned + e.slashed)
            for e in fee_events
            if e.address == addr and e.round_index not in undetermined_rounds
        )
        address_net_profit = earnings - costs - penalties
        coalition_net_profit += address_net_profit

    # Step 5: Assert that the coalition did not profit
    if coalition_net_profit > 10:  # Allow a small tolerance
        raise InvariantViolation(
            "no_profit_from_griefing",
            f"A coalition of {len(griefing_coalition)} validators who consistently "
            f"voted with the minority made a collective profit of {coalition_net_profit}. "
            f"Coalition members: {griefing_coalition}",
        )
