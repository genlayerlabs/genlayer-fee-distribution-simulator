"""Opt-in, owner-funded negative fees over the ordinary fee simulator.

Work commitments are supplied before simulation and reserved together. They
are NOT inferred from realized losses. Supplied capital is collectible owner
capital in the same unit as FeeEvents, net of the declared other reservations.
The caller remains responsible for complete capital/exposure bounds and for
supplying canonical, terminal outcomes; this is not a consensus implementation.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from src.fee_simulator.analysis.appeal_liability_requirements import _amounts
from src.fee_simulator.analysis.liability_reservations import (
    LiabilityCommitment, LiabilityReservationBook, LiabilityResolution,
)
from src.fee_simulator.core.majority import normalize_vote
from src.fee_simulator.core.round_labeling import get_leader_action
from src.fee_simulator.core.transaction_processing import (
    FeeSimulation, process_transaction_with_provenance,
)
from src.fee_simulator.protocol.appeal_economics import successful_appeal_reward
from src.fee_simulator.protocol.models import (
    FeeEvent, TransactionBudget, TransactionRoundResults,
)
from src.fee_simulator.specification.invariants.definitions.common import InvariantViolation
from src.fee_simulator.utils_round_sizes import find_previous_normal_round


LEADER_CORRECTIONS = frozenset({
    "APPEAL_LEADER_SUCCESSFUL", "APPEAL_LEADER_TIMEOUT_SUCCESSFUL",
})


@dataclass(frozen=True, order=True)
class WorkKey:
    """One participant's work across all attempts of a generation/round.

    Existing FeeEvents do not identify the rotation producing every voter fee.
    The commitment therefore covers the whole admitted round, including its
    funded attempts. Correction evidence separately names the responsible
    leader's exact source attempt.
    """

    transaction: str
    generation: int
    round_index: int
    validator: str

    def __post_init__(self):
        if not self.transaction or not self.validator:
            raise ValueError("transaction and validator identities are required")
        _amounts(generation=self.generation, round_index=self.round_index)


@dataclass(frozen=True)
class OwnerCapital:
    owner: str
    self_funds: int
    delegated_funds: int = 0
    other_reserved: int = 0

    def __post_init__(self):
        if not self.owner:
            raise ValueError("owner identity is required")
        _amounts(self_funds=self.self_funds, delegated_funds=self.delegated_funds,
                 other_reserved=self.other_reserved)
        if self.other_reserved > self.self_funds:
            raise ValueError("other reservations exceed owner funds")


@dataclass(frozen=True)
class WorkCommitment:
    key: WorkKey
    owner: str
    negative_fee_cap: int
    correction_bonus_cap: int
    other_gain_bound: int | None

    def __post_init__(self):
        if not self.owner:
            raise ValueError("owner identity is required")
        if self.other_gain_bound is None:
            raise InvariantViolation("liability_coverage", "Other benefits need an explicit bound")
        _amounts(negative_fee_cap=self.negative_fee_cap,
                 correction_bonus_cap=self.correction_bonus_cap,
                 other_gain_bound=self.other_gain_bound)

    @property
    def cap(self) -> int:
        return self.negative_fee_cap + self.correction_bonus_cap + self.other_gain_bound


@dataclass(frozen=True)
class TransactionCase:
    transaction: str
    addresses: tuple[str, ...]
    results: TransactionRoundResults
    budget: TransactionBudget
    discarded_generations: tuple[TransactionRoundResults, ...] = ()


@dataclass(frozen=True)
class Correction:
    source: WorkKey
    source_attempt: int
    appeal_round: int
    kind: str
    bond: int
    bonus: int


@dataclass(frozen=True)
class OwnerCharge:
    key: WorkKey
    owner: str
    negative_fees: int
    correction_bonus: int
    other_gains: int
    cap: int
    negative_fee_event_ids: tuple[int, ...]
    correction_event_id: int | None

    @property
    def collected(self) -> int:
        return self.negative_fees + self.correction_bonus + self.other_gains


@dataclass(frozen=True)
class OwnerFundedTransaction:
    transaction: str
    ordinary: FeeSimulation
    fee_events: tuple[FeeEvent, ...]
    corrections: tuple[Correction, ...]


@dataclass(frozen=True)
class OwnerFundedSettlement:
    transactions: tuple[OwnerFundedTransaction, ...]
    commitments: tuple[WorkCommitment, ...]
    opening_capital: tuple[OwnerCapital, ...]
    closing_capital: tuple[OwnerCapital, ...]
    charges: tuple[OwnerCharge, ...]
    collected_burn: int


def _work_keys(transaction: str, simulation: FeeSimulation) -> set[WorkKey]:
    keys = set()
    for generation in simulation.generations:
        for index, round_obj in enumerate(generation.results.rounds):
            # Leader appeal rows are bond bookkeeping, not voting work.
            if generation.labels[index].startswith("APPEAL_LEADER"):
                continue
            for rotation in round_obj.rotations:
                leader = next(iter(rotation.votes), None)
                action = get_leader_action(rotation.votes, leader)
                for actor, vote in rotation.votes.items():
                    if normalize_vote(vote) not in ("NA", "IDLE") or (
                        actor == leader and action == "LEADER_TIMEOUT"
                    ):
                        keys.add(WorkKey(transaction, generation.generation, index, actor))
    return keys


def _corrections(transaction: str, simulation: FeeSimulation) -> tuple[Correction, ...]:
    observations = []
    for generation in simulation.generations:
        # A discarded generation's appeal bonds were returned on invalidation.
        # Preserved work is not itself a new correction or evidence of fault.
        if generation.invalidated:
            continue
        for appeal_round, label in enumerate(generation.labels):
            if label not in LEADER_CORRECTIONS:
                continue
            source_round = find_previous_normal_round(appeal_round, list(generation.labels))
            if source_round is None:
                raise InvariantViolation("liability_source", "Correction lacks source work")
            source = generation.results.rounds[source_round]
            if not source.rotations or not source.rotations[-1].votes:
                raise InvariantViolation("liability_source", "Correction lacks a responsible leader")
            votes = source.rotations[-1].votes
            leader = next(iter(votes))
            action = get_leader_action(votes, leader)
            expected = "LEADER_TIMEOUT" if "TIMEOUT" in label else "LEADER_RECEIPT"
            if action != expected:
                raise InvariantViolation("liability_source", "Correction family contradicts raw source action")
            appellant_events = [
                event for event in simulation.fee_events
                if event.role == "APPEALANT"
                and event.sequence_id in simulation.origins
                and simulation.origins[event.sequence_id].generation == generation.generation
                and simulation.origins[event.sequence_id].round_index == appeal_round
            ]
            bond = sum(event.cost for event in appellant_events)
            payout = sum(event.earned for event in appellant_events)
            if not appellant_events or payout != successful_appeal_reward(bond):
                raise InvariantViolation("liability_reward", "Successful appeal payout lacks exact bond backing")
            observations.append(Correction(
                WorkKey(transaction, generation.generation, source_round, leader),
                len(source.rotations) - 1, appeal_round, label, bond, payout - bond,
            ))
    return tuple(observations)


def simulate_owner_funded_fees(
    cases: Sequence[TransactionCase],
    *,
    capital: Sequence[OwnerCapital],
    commitments: Sequence[WorkCommitment],
) -> OwnerFundedSettlement:
    """Settle an explicit batch under the proposed owner-funded fee policy.

    All reservations are made before executing any case. Other outstanding
    work and competing slash exposure must be included in `other_reserved`.
    Terminal outcomes release every unused cap; until then the standalone
    reservation book can model withdrawal and asynchronous collection gates.

    Existing voting negative fees retain their trigger and amount. For each
    corrected source, the new additional charge is its total actual appeal
    bonus plus its committed aggregate other-gain bound. No original committee
    is retroactively penalized solely because a validator appeal succeeded.
    """
    cases, capital, commitments = tuple(cases), tuple(capital), tuple(commitments)
    if not cases or any(not case.transaction for case in cases):
        raise ValueError("at least one named transaction is required")
    if len({case.transaction for case in cases}) != len(cases):
        raise ValueError("transaction identities must be unique within a batch")
    accounts = {account.owner: account for account in capital}
    if len(accounts) != len(capital):
        raise ValueError("capital must be aggregated once per economic owner")
    plans = {}
    owners = {}
    book = LiabilityReservationBook()
    for account in capital:
        book.deposit(account.owner, account.self_funds - account.other_reserved)
    for commitment in commitments:
        if commitment.owner not in accounts:
            raise InvariantViolation("liability_coverage", "Commitment has no owner capital account")
        if commitment.key in plans:
            raise InvariantViolation("liability_identity", "Duplicate work commitment")
        previous_owner = owners.setdefault(commitment.key.validator, commitment.owner)
        if previous_owner != commitment.owner:
            raise InvariantViolation("liability_identity", "Validator ownership changes within the batch")
        plans[commitment.key] = commitment
        book.commit(LiabilityCommitment(commitment.key, commitment.owner, commitment.cap))

    transactions = []
    charges = []
    required = set()
    for case in cases:
        ordinary = process_transaction_with_provenance(
            list(case.addresses), case.results, case.budget, list(case.discarded_generations),
        )
        work = _work_keys(case.transaction, ordinary)
        required.update(work)
        if not work <= plans.keys():
            raise InvariantViolation("liability_coverage", "Some admitted work has no pre-work commitment")
        corrections = _corrections(case.transaction, ordinary)
        grouped_corrections = defaultdict(list)
        for correction in corrections:
            grouped_corrections[correction.source].append(correction)
        negative_events = defaultdict(list)
        for event in ordinary.fee_events:
            if not event.burned or event.role == "APPEALANT":
                continue  # Disposal of an already posted bond is not a second debit.
            if event.role not in ("LEADER", "VALIDATOR") or event.sequence_id not in ordinary.origins:
                raise InvariantViolation("liability_coverage", "Negative fee lacks work provenance")
            origin = ordinary.origins[event.sequence_id]
            key = WorkKey(case.transaction, origin.generation, origin.round_index, event.address)
            if key not in work:
                raise InvariantViolation("liability_source", "Negative fee names unadmitted work")
            negative_events[key].append(event)

        events = list(ordinary.fee_events)
        for key in sorted(work):
            commitment = plans[key]
            negative = sum(event.burned for event in negative_events[key])
            bonus = sum(item.bonus for item in grouped_corrections[key])
            other = commitment.other_gain_bound if grouped_corrections[key] else 0
            if negative > commitment.negative_fee_cap or bonus > commitment.correction_bonus_cap:
                raise InvariantViolation("committed_liability", "Realized exposure exceeds an admitted component cap")
            new_event_id = None
            if bonus + other:
                # Settlement-time debit. Its responsible source and correcting
                # rounds live in the typed charge/correction records, not in a
                # mutable FeeEvent payout label. The existing refund is intact.
                new_event_id = len(events) + 1
                events.append(FeeEvent(
                    sequence_id=new_event_id, address=key.validator,
                    role="LEADER", burned=bonus + other,
                ))
            charge = OwnerCharge(
                key, commitment.owner, negative, bonus, other, commitment.cap,
                tuple(event.sequence_id for event in negative_events[key]), new_event_id,
            )
            book.resolve(key, LiabilityResolution("terminal-owner-fees", charge.collected),
                         all_liability_final=True)
            charges.append(charge)
        transactions.append(OwnerFundedTransaction(
            case.transaction, ordinary, tuple(events), corrections,
        ))

    if required != plans.keys():
        raise InvariantViolation("liability_coverage", "Commitment set must match the admitted batch work")
    closing = tuple(OwnerCapital(
        account.owner, book.balance(account.owner) + account.other_reserved,
        account.delegated_funds, account.other_reserved,
    ) for account in capital)
    result = OwnerFundedSettlement(
        tuple(transactions), commitments, capital, closing, tuple(charges), book.burned,
    )
    # Independent output reconciliation is part of the opt-in entry point.
    from src.fee_simulator.specification.invariants.owner_liability import check_owner_funded_settlement
    check_owner_funded_settlement(result)
    return result
