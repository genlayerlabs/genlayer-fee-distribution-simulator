"""
Invariant: Griefing Amplification Check

An appellant in a failed appeal should not be able to cause more damage to the
network than the cost they paid for the appeal. This prevents "griefing
amplification" attacks, where an attacker pays a small cost to inflict a large
amount of damage on other participants.
"""
from typing import List
from fee_simulator.models import FeeEvent
from fee_simulator.types import RoundLabel
from .common import InvariantViolation

def check_griefing_amplification(
    fee_events: List[FeeEvent], round_labels: List[RoundLabel]
) -> None:
    """
    Checks that the damage caused by a failed appeal does not exceed the
    appellant's bond for that appeal.
    """
    # Find all unsuccessful appeal rounds
    unsuccessful_appeal_rounds = [
        i for i, label in enumerate(round_labels) if "UNSUCCESSFUL" in label
    ]

    if not unsuccessful_appeal_rounds:
        return

    for round_index in unsuccessful_appeal_rounds:
        # Find the appellant and their cost for this specific appeal
        appellant_events = [
            e for e in fee_events
            if e.round_index == round_index and e.role == "APPEALANT" and e.cost > 0
        ]

        if not appellant_events:
            continue

        appellant_event = appellant_events[0]
        appellant_address = appellant_event.address
        appellant_cost = appellant_event.cost

        # Determine the rounds affected by this contention.
        affected_rounds = {round_index}
        current_round_label = round_labels[round_index]

        # For unsuccessful leader appeals, the bond is split in the *next* round.
        if current_round_label == "APPEAL_LEADER_UNSUCCESSFUL":
            next_round_index = round_index + 1
            if (
                next_round_index < len(round_labels) and
                round_labels[next_round_index] == "SPLIT_PREVIOUS_APPEAL_BOND"
            ):
                affected_rounds.add(next_round_index)

        # For unsuccessful validator appeals, all consequences are in the same round.

        # Calculate the total damage (slashed + burned) to OTHER participants
        # in the affected rounds.
        damage_to_others = sum(
            (e.slashed + e.burned)
            for e in fee_events
            if e.address != appellant_address and e.round_index in affected_rounds
        )

        # The damage caused to others should not be greater than the appellant's cost.
        if damage_to_others > appellant_cost:
            griefing_factor = damage_to_others / appellant_cost if appellant_cost > 0 else float('inf')
            raise InvariantViolation(
                "griefing_amplification",
                f"Griefing amplification detected in round {round_index} ({current_round_label}). "
                f"Appellant {appellant_address} paid {appellant_cost} but caused "
                f"{damage_to_others} in damage to others (amplification factor: {griefing_factor:.2f}x)."
            )
