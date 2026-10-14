"""Paper-facing payoff certificates over executable ``FeeEvent`` output.

This module deliberately does not distribute fees.  It observes events emitted
by the existing round transformers and checks them against an independent,
participant-by-participant statement of the preservation and correction
payoffs used by the endogenous-evaluator paper.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from src.fee_simulator.core.bond_computing import compute_appeal_bond
from src.fee_simulator.core.majority import compute_majority, normalize_vote
from src.fee_simulator.core.refunds import compute_sender_refund
from src.fee_simulator.protocol.constants import (
    APPEAL_REWARD_MULTIPLE,
    PENALTY_REWARD_COEFFICIENT,
)
from src.fee_simulator.protocol.models import (
    FeeEvent,
    TransactionBudget,
    TransactionRoundResults,
)
from src.fee_simulator.protocol.types import MajorityOutcome, RoundLabel
from src.fee_simulator.utils import is_appeal_round
from src.fee_simulator.utils_round_sizes import find_previous_normal_round


class PaperPropertyViolation(AssertionError):
    """An executable settlement contradicts a paper-facing payoff property."""

    def __init__(self, property_name: str, message: str):
        self.property_name = property_name
        super().__init__(f"{property_name}: {message}")


@dataclass(frozen=True)
class EconomicPayoff:
    """All economically relevant legs emitted for one participant."""

    earned: int = 0
    cost: int = 0
    burned: int = 0
    slashed: int = 0

    @property
    def net(self) -> int:
        return self.earned - self.cost - self.burned - self.slashed


@dataclass(frozen=True)
class PaperPayoffCertificate:
    """Certified payoff facts for one successful validator appeal."""

    original_majority: MajorityOutcome
    appeal_majority: MajorityOutcome
    original_size: int
    appeal_size: int
    vindicated_count: int
    maximum_vindicated_count: int
    vindication_payout: int
    added_sender_cost: int
    appellant_bond: int
    appellant_bond_debit: int
    appellant_gross_reward: int


def aggregate_payoff(
    fee_events: Iterable[FeeEvent],
    address: str,
    *,
    role: Optional[str] = None,
    round_index: Optional[int] = None,
) -> EconomicPayoff:
    """Aggregate event legs without importing settlement implementation logic."""

    earned = 0
    cost = 0
    burned = 0
    slashed = 0
    for event in fee_events:
        if event.address != address:
            continue
        if role is not None and event.role != role:
            continue
        if round_index is not None and event.round_index != round_index:
            continue
        earned += event.earned
        cost += event.cost
        burned += event.burned
        slashed += event.slashed
    return EconomicPayoff(
        earned=earned,
        cost=cost,
        burned=burned,
        slashed=slashed,
    )


def _require(condition: bool, property_name: str, message: str) -> None:
    if not condition:
        raise PaperPropertyViolation(property_name, message)


def _validator_payoffs(
    fee_events: Iterable[FeeEvent], round_index: int
) -> Dict[str, EconomicPayoff]:
    addresses = {
        event.address
        for event in fee_events
        if event.role == "VALIDATOR" and event.round_index == round_index
    }
    return {
        address: aggregate_payoff(
            fee_events,
            address,
            role="VALIDATOR",
            round_index=round_index,
        )
        for address in addresses
    }


def _assert_payoff(
    actual: EconomicPayoff,
    expected: EconomicPayoff,
    property_name: str,
    address: str,
) -> None:
    _require(
        actual == expected,
        property_name,
        f"validator {address} expected {expected}, got {actual}",
    )


def certify_normal_round(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    fee_events: List[FeeEvent],
) -> MajorityOutcome:
    """Certify the preservation payoff emitted by an ordinary final rotation."""

    round_obj = transaction_results.rounds[round_index]
    _require(bool(round_obj.rotations), "normal_round_shape", "round has no rotation")
    votes = round_obj.rotations[-1].votes
    majority = compute_majority(votes)
    actual_by_address = _validator_payoffs(fee_events, round_index)

    for address, vote in votes.items():
        if majority == "UNDETERMINED":
            expected = EconomicPayoff(earned=budget.validatorsTimeout)
        elif normalize_vote(vote) == majority:
            expected = EconomicPayoff(earned=budget.validatorsTimeout)
        else:
            expected = EconomicPayoff(
                burned=(PENALTY_REWARD_COEFFICIENT * budget.validatorsTimeout)
            )
        _assert_payoff(
            actual_by_address.get(address, EconomicPayoff()),
            expected,
            "normal_round_validator_payoff",
            address,
        )

    unexpected = set(actual_by_address) - set(votes)
    _require(
        not unexpected,
        "normal_round_participants",
        f"validator events emitted for nonparticipants: {sorted(unexpected)}",
    )
    return majority


def certify_successful_validator_appeal(
    transaction_results: TransactionRoundResults,
    round_index: int,
    budget: TransactionBudget,
    round_labels: List[RoundLabel],
    fee_events: List[FeeEvent],
) -> PaperPayoffCertificate:
    """Certify preservation, vindication, and user-cost facts for an appeal.

    Appeal and original committees are required to be identity-disjoint.  That
    is the first-rung protocol shape and lets the existing ``FeeEvent`` schema
    attribute retroactive credits without inventing a second fee model.
    """

    _require(
        round_labels[round_index] == "APPEAL_VALIDATOR_SUCCESSFUL",
        "appeal_shape",
        f"round {round_index} is {round_labels[round_index]}",
    )
    original_round_index = find_previous_normal_round(round_index, round_labels)
    _require(
        original_round_index is not None,
        "appeal_shape",
        "successful validator appeal has no preceding non-appeal round",
    )
    original_round = transaction_results.rounds[original_round_index]
    appeal_round = transaction_results.rounds[round_index]
    _require(
        bool(original_round.rotations) and bool(appeal_round.rotations),
        "appeal_shape",
        "original or appeal round has no final rotation",
    )

    original_votes = original_round.rotations[-1].votes
    appeal_votes = appeal_round.rotations[-1].votes
    original_addresses = set(original_votes)
    appeal_addresses = set(appeal_votes)
    _require(
        original_addresses.isdisjoint(appeal_addresses),
        "appeal_identity_separation",
        "original and appeal committees overlap",
    )

    original_majority = compute_majority(original_votes)
    appeal_majority = compute_majority(appeal_votes)
    _require(
        original_majority == "AGREE",
        "appeal_shape",
        "successful validator appeal must challenge an accepted outcome",
    )
    _require(
        appeal_majority != original_majority,
        "appeal_overturn_rule",
        "appeal result confirms the original result",
    )

    actual_by_address = _validator_payoffs(fee_events, round_index)
    penalty = PENALTY_REWARD_COEFFICIENT * budget.validatorsTimeout

    # The appeal committee continues to settle only from its own majority.
    for address, vote in appeal_votes.items():
        if appeal_majority == "UNDETERMINED":
            expected = EconomicPayoff(earned=budget.validatorsTimeout)
        elif normalize_vote(vote) == appeal_majority:
            expected = EconomicPayoff(earned=budget.validatorsTimeout)
        else:
            expected = EconomicPayoff(burned=penalty)
        _assert_payoff(
            actual_by_address.get(address, EconomicPayoff()),
            expected,
            "appeal_committee_payoff",
            address,
        )

    vindicated_addresses = {
        address
        for address, vote in original_votes.items()
        if appeal_majority != "UNDETERMINED" and normalize_vote(vote) == appeal_majority
    }

    # The skipped original committee has only the new vindication credit.  It
    # never receives a retroactive penalty, and NoMajority vindicates nobody.
    for address in original_addresses:
        expected = (
            EconomicPayoff(earned=budget.validatorsTimeout)
            if address in vindicated_addresses
            else EconomicPayoff()
        )
        _assert_payoff(
            actual_by_address.get(address, EconomicPayoff()),
            expected,
            "original_round_vindication",
            address,
        )

    unexpected = set(actual_by_address) - original_addresses - appeal_addresses
    _require(
        not unexpected,
        "appeal_participants",
        f"validator events emitted for nonparticipants: {sorted(unexpected)}",
    )

    maximum_vindicated_count = (len(original_addresses) - 1) // 2
    _require(
        len(vindicated_addresses) <= maximum_vindicated_count,
        "vindication_bound",
        f"{len(vindicated_addresses)} vindicated exceeds "
        f"{maximum_vindicated_count} for N={len(original_addresses)}",
    )

    normal_round_index = int(original_round_index)
    appeal_bond = compute_appeal_bond(
        normal_round_index=normal_round_index,
        leader_timeout=budget.leaderTimeout,
        validators_timeout=budget.validatorsTimeout,
        round_labels=round_labels,
        appeal_round_index=round_index,
        rotations=budget.rotations,
        rotations_used=budget.rotationsUsed,
    )
    appellant_address = budget.appeals[
        sum(1 for label in round_labels[: round_index + 1] if is_appeal_round(label))
        - 1
    ].appealantAddress
    appellant_events = [
        event
        for event in fee_events
        if event.address == appellant_address
        and event.role == "APPEALANT"
        and event.round_index == round_index
    ]
    _require(
        bool(appellant_events),
        "appellant_reward",
        "expected appellant settlement events",
    )
    expected_appellant_reward = int(appeal_bond * APPEAL_REWARD_MULTIPLE)
    is_full_transaction_output = any(
        event.address == budget.senderAddress and event.role == "SENDER"
        for event in fee_events
    )
    expected_bond_debit = appeal_bond if is_full_transaction_output else 0
    appellant_payoff = aggregate_payoff(
        appellant_events,
        appellant_address,
        role="APPEALANT",
        round_index=round_index,
    )
    _require(
        appellant_payoff.earned == expected_appellant_reward
        and appellant_payoff.cost == expected_bond_debit
        and appellant_payoff.burned == 0
        and appellant_payoff.slashed == 0,
        "appellant_reward",
        f"expected reward {expected_appellant_reward} and bond debit "
        f"{expected_bond_debit}, got {appellant_payoff}",
    )
    appellant_gross_reward = appellant_payoff.earned

    vindication_events = [
        event
        for event in fee_events
        if event.role == "VALIDATOR"
        and event.round_index == round_index
        and event.address in original_addresses
    ]
    vindication_payout = sum(event.earned for event in vindication_events)
    expected_vindication_payout = len(vindicated_addresses) * budget.validatorsTimeout
    _require(
        vindication_payout == expected_vindication_payout,
        "vindication_total",
        f"expected {expected_vindication_payout}, got {vindication_payout}",
    )

    # Full transaction processing appends the computed sender refund as a
    # terminal event. Exclude that output before independently recomputing it;
    # a direct round-handler certificate simply has no such event.
    sender_refund_events = [
        event
        for event in fee_events
        if event.address == budget.senderAddress
        and event.role == "SENDER"
        and event.earned > 0
    ]
    events_before_refund = [
        event for event in fee_events if event not in sender_refund_events
    ]
    actual_refund = compute_sender_refund(
        budget.senderAddress, events_before_refund, budget, round_labels
    )
    events_without_vindication = [
        event for event in events_before_refund if event not in vindication_events
    ]
    counterfactual_refund = compute_sender_refund(
        budget.senderAddress,
        events_without_vindication,
        budget,
        round_labels,
    )
    added_sender_cost = int(counterfactual_refund - actual_refund)
    _require(
        added_sender_cost == vindication_payout,
        "vindication_user_cost",
        f"refund delta {added_sender_cost} != payout {vindication_payout}",
    )
    if sender_refund_events:
        emitted_refund = sum(event.earned for event in sender_refund_events)
        _require(
            emitted_refund == actual_refund,
            "sender_refund",
            f"emitted refund {emitted_refund} != recomputed {actual_refund}",
        )

    return PaperPayoffCertificate(
        original_majority=original_majority,
        appeal_majority=appeal_majority,
        original_size=len(original_addresses),
        appeal_size=len(appeal_addresses),
        vindicated_count=len(vindicated_addresses),
        maximum_vindicated_count=maximum_vindicated_count,
        vindication_payout=vindication_payout,
        added_sender_cost=added_sender_cost,
        appellant_bond=appeal_bond,
        appellant_bond_debit=appellant_payoff.cost,
        appellant_gross_reward=appellant_gross_reward,
    )
