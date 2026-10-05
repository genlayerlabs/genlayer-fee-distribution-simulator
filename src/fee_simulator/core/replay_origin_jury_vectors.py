"""F-B01 route and payout vectors for replay-origin validator juries.

Generated cases use the round engine. The all-idle no-reveal case is an
explicit admission/refund fixture: the generic idleness prepass removes all
votes before it can label that appeal, so it is not presented as a generated
round-engine result.
"""

from copy import deepcopy

from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.core.round_labeling import label_rounds
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.majority import compute_majority, normalize_vote
from src.fee_simulator.protocol.models import Appeal


ADDRESSES = [f"0x{i:040x}" for i in range(1, 41)]
PREFIX = [
    "START",
    "LEADER_RECEIPT_UNDETERMINED",
    "LEADER_APPEAL_SUCCESSFUL",
    "LEADER_RECEIPT_MAJORITY_TIMEOUT",
]
UNITS = {"leader": "100", "validator": "200", "price": "1"}


def _round_run(path):
    transaction, budget = path_to_transaction_results(
        path, ADDRESSES, ADDRESSES[-1], ADDRESSES[-2], 100, 200
    )
    # Give the two admissions distinct funders. This changes no unit fee or
    # committee result but exposes refund and principal ownership.
    budget = budget.model_copy(
        update={
            "appeals": [
                Appeal(appealantAddress=ADDRESSES[-2 - i])
                for i in range(len(budget.appeals))
            ]
        }
    )
    events, labels = process_transaction(ADDRESSES, transaction, budget)
    return transaction, budget, events, labels


def _admission_route(node):
    if node.startswith("VALIDATOR_APPEAL"):
        return "validator-jury"
    if node.startswith("LEADER_APPEAL_TIMEOUT"):
        return "leader-timeout-appeal"
    if node.startswith("LEADER_APPEAL"):
        return "leader-replay"
    return None


def _round_inputs(transaction, path):
    """Preserve the final rotation's ordered raw ballots for independent replay."""
    if len(transaction.rounds) != len(path) - 2:
        raise ValueError("path and transaction rounds differ")
    inputs = []
    for index, round_result in enumerate(transaction.rounds):
        votes = round_result.rotations[-1].votes
        first_address, first_vote = next(iter(votes.items()), (None, None))
        leader_action = (
            first_vote[0]
            if isinstance(first_vote, list)
            and first_vote[0] in ("LEADER_RECEIPT", "LEADER_TIMEOUT")
            else None
        )
        node = path[index + 1]
        inputs.append(
            {
                "roundIndex": index,
                "sourceNode": node,
                "sourceClassification": node,
                "admittedRoute": _admission_route(node),
                "bookkeepingOnly": not bool(votes)
                or _admission_route(node) in (
                    "leader-replay",
                    "leader-timeout-appeal",
                ),
                "leaderAddress": first_address if leader_action else None,
                "leaderAction": leader_action,
                "majorityVote": compute_majority(votes),
                "seats": [
                    {
                        "seat": seat,
                        "address": address,
                        "rawVote": raw_vote,
                        "normalizedVote": normalize_vote(raw_vote),
                    }
                    for seat, (address, raw_vote) in enumerate(votes.items())
                ],
            }
        )
    return inputs


def _generated_case(case_id, path, appeal_round, route, source_decision):
    transaction, budget, events, labels = _round_run(path)
    votes = transaction.rounds[appeal_round].rotations[-1].votes
    jury_addresses = list(votes) if route == "validator-jury" else []
    jury = [
        {
            "seat": seat,
            "address": address,
            "vote": normalize_vote(votes[address]),
            "earned": str(
                sum(
                    event.earned
                    for event in events
                    if event.round_index == appeal_round
                    and event.role == "VALIDATOR"
                    and event.address == address
                )
            ),
        }
        for seat, address in enumerate(jury_addresses)
    ]
    bond = sum(
        event.cost
        for event in events
        if event.round_index == appeal_round and event.role == "APPEALANT"
    )
    payout = sum(
        event.earned
        for event in events
        if event.round_index == appeal_round and event.role == "APPEALANT"
    )
    vindicated = [
        {"address": event.address, "earned": str(event.earned)}
        for event in events
        if event.round_index == appeal_round
        and event.role == "VALIDATOR"
        and event.earned
        and event.address not in jury_addresses
    ]
    jury_paid = sum(int(seat["earned"]) for seat in jury)
    unsuccessful = labels[appeal_round] == "APPEAL_VALIDATOR_UNSUCCESSFUL"
    appeal_ordinal = sum(
        label.startswith("APPEAL_") for label in labels[: appeal_round + 1]
    ) - 1
    dust = (len(jury) * 200 + bond - jury_paid) if unsuccessful else 0
    if dust < 0:
        raise ValueError("juror awards exceed failed-jury allocation")
    prefix_path = (
        PREFIX + ["END"]
        if route == "validator-jury"
        else ["START", "LEADER_TIMEOUT", "END"]
    )
    prefix_transaction, _ = path_to_transaction_results(
        prefix_path, ADDRESSES, ADDRESSES[-1], ADDRESSES[-2], 100, 200
    )
    source_color = label_rounds(prefix_transaction)[-1]
    return {
        "caseId": case_id,
        "provenance": "round-engine-generated",
        "sourcePath": path,
        "route": route,
        "sourceDecision": source_decision,
        "sourceFeeColorAtAdmission": source_color,
        "payers": {
            "sender": budget.senderAddress,
            "admissionAppellant": budget.appeals[appeal_ordinal].appealantAddress,
            "earlierAppellant": budget.appeals[0].appealantAddress,
        },
        "admittedAppeal": {
            "roundIndex": appeal_round,
            "kind": route,
            "bond": str(bond),
        },
        "roundInputs": _round_inputs(transaction, path),
        "roundLabels": labels,
        "jurorAwards": jury,
        "vindicationAwards": vindicated,
        "appellant": {
            "principalDeposited": str(bond),
            "principalReturned": str(min(bond, payout)),
            "profit": str(max(0, payout - bond)),
            "principalRefund": "0",
            "totalPayout": str(payout),
        },
        "divisionDust": str(dust),
        "remedyLabel": labels[appeal_round + 1]
        if appeal_round + 1 < len(labels)
        else None,
        "senderRefund": str(
            sum(event.earned for event in events if event.role == "SENDER")
        ),
    }


def replay_origin_jury_vectors():
    failed = _generated_case(
        "replay-origin-jury-failed",
        PREFIX + ["VALIDATOR_APPEAL_UNSUCCESSFUL", "END"],
        3,
        "validator-jury",
        "ValidatorsTimeout",
    )
    successful_normal = _generated_case(
        "replay-origin-jury-success-normal-remedy",
        PREFIX
        + ["VALIDATOR_APPEAL_SUCCESSFUL", "LEADER_RECEIPT_MAJORITY_AGREE", "END"],
        3,
        "validator-jury",
        "ValidatorsTimeout",
    )
    successful_timeout = _generated_case(
        "replay-origin-jury-success-timeout-remedy",
        PREFIX + ["VALIDATOR_APPEAL_SUCCESSFUL", "LEADER_TIMEOUT", "END"],
        3,
        "validator-jury",
        "ValidatorsTimeout",
    )
    true_timeout = _generated_case(
        "actual-leader-timeout-control",
        [
            "START",
            "LEADER_TIMEOUT",
            "LEADER_APPEAL_TIMEOUT_SUCCESSFUL",
            "LEADER_RECEIPT_MAJORITY_AGREE",
            "END",
        ],
        1,
        "leader-timeout-appeal",
        "LeaderTimeout",
    )

    # E-B03 no-reveal settlement returns principal after an admitted jury
    # produces no payable votes. The generic simulator's IDLE prepass removes
    # all such votes and would label an EMPTY_ROUND, so this is deliberately a
    # focused admission/refund fixture based on the generated validator quote.
    all_idle = deepcopy(failed)
    all_idle.update(
        caseId="replay-origin-jury-all-idle-refund",
        provenance="manual-admission-refund-fixture",
        sourcePath=PREFIX + ["VALIDATOR_APPEAL_ALL_IDLE_NO_REVEAL", "END"],
        roundInputs=failed["roundInputs"][:-1]
        + [
            {
                **failed["roundInputs"][-1],
                "sourceNode": "VALIDATOR_APPEAL_ALL_IDLE_NO_REVEAL",
                "sourceClassification": "VALIDATOR_APPEAL_ALL_IDLE_NO_REVEAL",
                "majorityVote": "UNDETERMINED",
                "seats": [
                    {**seat, "rawVote": "IDLE", "normalizedVote": "IDLE"}
                    for seat in failed["roundInputs"][-1]["seats"]
                ],
            }
        ],
        roundLabels=failed["roundLabels"][:-1] + ["JURY_ALL_IDLE_NO_REVEAL"],
        jurorAwards=[
            {**seat, "vote": "IDLE", "earned": "0"}
            for seat in failed["jurorAwards"]
        ],
        vindicationAwards=[],
        appellant={
            "principalDeposited": failed["admittedAppeal"]["bond"],
            "principalReturned": failed["admittedAppeal"]["bond"],
            "profit": "0",
            "principalRefund": failed["admittedAppeal"]["bond"],
            "totalPayout": failed["admittedAppeal"]["bond"],
        },
        divisionDust="0",
        senderRefund=None,
        scope=(
            "Admission and E-B03 principal refund only; "
            "generic IDLE prepass cannot settle this path"
        ),
    )
    return {
        "schemaVersion": 1,
        "finding": "F-B01",
        "units": UNITS,
        "validatorFixtureCount": 40,
        "cases": [
            failed,
            successful_normal,
            successful_timeout,
            all_idle,
            true_timeout,
        ],
    }
