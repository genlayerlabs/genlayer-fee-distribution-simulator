"""Independent reconciliation for the opt-in owner-funded settlement.

Checks realized ledgers, provenance and supplied commitments. These assertions
do not establish truthful outcomes, beneficial ownership or a complete bound
on off-ledger benefits; see docs/OWNER_FUNDED_NEGATIVE_FEES.md for the theorem's
assumptions and the distinction between algebra and protocol security.
"""

from collections import defaultdict

from src.fee_simulator.core.owner_liability import OwnerFundedSettlement, WorkKey
from src.fee_simulator.protocol.models import FeeEvent
from src.fee_simulator.specification.invariants.definitions.common import InvariantViolation


def _require(condition: bool, name: str, message: str) -> None:
    if not condition:
        raise InvariantViolation(name, message)


def check_owner_funded_settlement(result: OwnerFundedSettlement) -> None:
    """Recompute required charges from ordinary output, not charge totals."""
    plans = {item.key: item for item in result.commitments}
    charges = {item.key: item for item in result.charges}
    opening = {item.owner: item for item in result.opening_capital}
    closing = {item.owner: item for item in result.closing_capital}
    _require(len(plans) == len(result.commitments) and len(charges) == len(result.charges),
             "liability_identity", "Duplicate commitment or charge")
    _require(plans.keys() == charges.keys(), "liability_coverage", "Commitment/charge coverage differs")
    _require(len(opening) == len(result.opening_capital) and len(closing) == len(result.closing_capital)
             and opening.keys() == closing.keys(), "liability_identity", "Capital owner coverage differs")

    caps = defaultdict(int)
    owners = {}
    for plan in result.commitments:
        _require(plan.owner in opening, "liability_coverage", "Missing owner capital")
        _require(plan.other_gain_bound is not None, "liability_coverage", "Other benefits are unbounded")
        _require(owners.setdefault(plan.key.validator, plan.owner) == plan.owner,
                 "liability_identity", "Validator has inconsistent ownership")
        caps[plan.owner] += plan.cap
    for owner, account in opening.items():
        _require(caps[owner] + account.other_reserved <= account.self_funds,
                 "liability_backing", "Concurrent commitments exceed available self funds")

    transactions = {item.transaction: item for item in result.transactions}
    _require(len(transactions) == len(result.transactions), "liability_identity", "Repeated transaction")
    work = set()
    total_burn = 0
    collected = defaultdict(int)
    for tx in result.transactions:
        ordinary = tx.ordinary
        n = len(ordinary.fee_events)
        _require(tx.fee_events[:n] == ordinary.fee_events, "liability_funding_separation",
                 "Existing rewards, bonds, refunds or penalties changed")
        _require([event.sequence_id for event in tx.fee_events] == list(range(1, len(tx.fee_events) + 1)),
                 "liability_identity", "Event sequence is not unique and contiguous")
        added = {event.sequence_id: event for event in tx.fee_events[n:]}
        expected_added = set()
        negatives = defaultdict(list)
        bonus_by_source = defaultdict(int)
        corrected_sources = set()

        # Independently enumerate actual service, excluding NA bookkeeping and
        # idleness (whose broader slash remains outside this new fee policy).
        for generation in ordinary.generations:
            for index, round_obj in enumerate(generation.results.rounds):
                if generation.labels[index].startswith("APPEAL_LEADER"):
                    continue
                for rotation in round_obj.rotations:
                    for actor, vote in rotation.votes.items():
                        raw = vote if isinstance(vote, str) else (
                            vote[1] if vote[0] in ("LEADER_RECEIPT", "LEADER_TIMEOUT") else vote[0]
                        )
                        proposal_timeout = isinstance(vote, list) and vote[0] == "LEADER_TIMEOUT"
                        if raw not in ("NA", "IDLE") or proposal_timeout:
                            work.add(WorkKey(tx.transaction, generation.generation, index, actor))

        expected_corrections = {}
        for generation in ordinary.generations:
            if generation.invalidated:
                continue
            for index, label in enumerate(generation.labels):
                if label in ("APPEAL_LEADER_SUCCESSFUL", "APPEAL_LEADER_TIMEOUT_SUCCESSFUL"):
                    expected_corrections[(generation.generation, index)] = (generation, label)
        observed = {(item.source.generation, item.appeal_round): item for item in tx.corrections}
        _require(len(observed) == len(tx.corrections) and observed.keys() == expected_corrections.keys(),
                 "liability_coverage", "Successful correction coverage differs")
        for identity, correction in observed.items():
            generation, label = expected_corrections[identity]
            source_index = correction.appeal_round - 1
            while source_index >= 0 and generation.labels[source_index].startswith("APPEAL_"):
                source_index -= 1
            _require(source_index >= 0, "liability_source", "Correction has no source round")
            source_round = generation.results.rounds[source_index]
            _require(bool(source_round.rotations and source_round.rotations[-1].votes),
                     "liability_source", "Correction has no source participant")
            votes = source_round.rotations[-1].votes
            actor = next(iter(votes))
            source_key = WorkKey(tx.transaction, generation.generation, source_index, actor)
            required_action = "LEADER_TIMEOUT" if label == "APPEAL_LEADER_TIMEOUT_SUCCESSFUL" else "LEADER_RECEIPT"
            _require(isinstance(votes[actor], list) and votes[actor][0] == required_action,
                     "liability_source", "Payout label is not raw responsibility evidence")
            _require(correction.source == source_key and correction.source_attempt == len(source_round.rotations) - 1
                     and correction.kind == label, "liability_source", "Correction names the wrong source")
            appeal_events = [event for event in ordinary.fee_events
                             if event.role == "APPEALANT" and event.sequence_id in ordinary.origins
                             and (ordinary.origins[event.sequence_id].generation,
                                  ordinary.origins[event.sequence_id].round_index) == identity]
            bond = sum(event.cost for event in appeal_events)
            payout = sum(event.earned for event in appeal_events)
            _require(bool(appeal_events) and payout == bond * 5 // 2
                     and correction.bond == bond and correction.bonus == payout - bond,
                     "liability_reward", "Reward/principal accounting differs from the 5/2 policy")
            bonus_by_source[source_key] += payout - bond
            corrected_sources.add(source_key)

        for event in ordinary.fee_events:
            if event.burned and event.role != "APPEALANT":
                origin = ordinary.origins.get(event.sequence_id)
                _require(origin is not None and event.role in ("LEADER", "VALIDATOR"),
                         "liability_coverage", "Negative fee lacks service provenance")
                key = WorkKey(tx.transaction, origin.generation, origin.round_index, event.address)
                negatives[key].append(event)
        tx_work = {key for key in work if key.transaction == tx.transaction}
        _require(set(negatives) | corrected_sources <= tx_work,
                 "liability_source", "Charge belongs to unadmitted work")
        _require(tx_work <= plans.keys(), "liability_coverage", "Work has no commitment")
        for key in tx_work:
            plan, charge = plans[key], charges[key]
            negative = sum(event.burned for event in negatives[key])
            bonus = bonus_by_source[key]
            other = plan.other_gain_bound if key in corrected_sources else 0
            _require(negative <= plan.negative_fee_cap and bonus <= plan.correction_bonus_cap,
                     "committed_liability", "A component exceeds its pre-work cap")
            _require(charge.owner == plan.owner and charge.cap == plan.cap
                     and charge.negative_fees == negative and charge.correction_bonus == bonus
                     and charge.other_gains == other,
                     "owned_liability", "Collected source charge differs from the policy")
            _require(charge.negative_fee_event_ids == tuple(event.sequence_id for event in negatives[key]),
                     "liability_identity", "Existing negative fee was omitted or counted twice")
            if bonus + other:
                _require(charge.correction_event_id in added,
                         "owned_liability", "Correction debit is missing")
                expected = FeeEvent(sequence_id=charge.correction_event_id,
                                    address=key.validator, role="LEADER", burned=bonus + other)
                _require(added[charge.correction_event_id] == expected,
                         "liability_funding_separation", "Correction debit changes a recipient payment")
                _require(charge.correction_event_id not in expected_added,
                         "liability_identity", "One debit was reused by multiple sources")
                expected_added.add(charge.correction_event_id)
            else:
                _require(charge.correction_event_id is None,
                         "liability_identity", "Uncorrected source has a correction debit")
            collected[plan.owner] += negative + bonus + other
            total_burn += negative + bonus + other
        _require(expected_added == added.keys(), "liability_funding_separation", "Unexpected added payment or debit")

    _require(work == plans.keys(), "liability_coverage", "Commitments do not match actual batch work")
    for owner, account in opening.items():
        after = closing[owner]
        _require(account.delegated_funds == after.delegated_funds,
                 "owner_only_incidence", "Delegated funds paid an owner fee penalty")
        _require(account.other_reserved == after.other_reserved,
                 "liability_backing", "Other liabilities lost their reserved backing")
        _require(account.self_funds - after.self_funds == collected[owner]
                 and after.self_funds >= after.other_reserved,
                 "owner_collection", "Owner's actual loss does not equal the collected charge")
    _require(total_burn == result.collected_burn, "liability_conservation", "Collected loss does not equal burn")
