#!/usr/bin/env python3
"""
Generate the fee test vectors consumed by genlayer-consensus
(test/fees/simulator_results/*) directly in their final schema.

This replaces the previously undocumented, uncommitted modifications to
scripts 05/06 that produced those files, so the pipeline can be re-run
whenever the fee model changes:

  python3 scripts/07_generate_consensus_vectors.py \
      --output-dir consensus_vectors --max-length 7 --max-rotations 2 \
      --existing-dir /path/to/genlayer-consensus/test/fees/simulator_results

Outputs, per category (first appeal node in the path, or no_appeal):
  <category>_compressed.json            (variants without rotations)
  <category>_rotations_compressed.json  (variants with rotations)
  appeal_quote_checkpoints.json         (compact transition-quote campaign)
  summary.json

Use --appeal-quote-output to place the compact campaign directly in a
consensus checkout while leaving the larger category vectors in --output-dir.

If --existing-dir is given, the complex-scenario directories found there
(*_complex_scenarios/, leader_timeout_complex_scenarios/) are rebuilt
keeping their existing pattern keys (which the hardhat tests look up),
re-running each pattern through the current simulator.
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fee_simulator.core.path_to_transaction import path_to_transaction_results
from src.fee_simulator.core.bond_computing import compute_appeal_bond_quote
from src.fee_simulator.core.transaction_processing import process_transaction
from src.fee_simulator.core.majority import compute_majority, normalize_vote
from src.fee_simulator.specification.state_machine.graph import TRANSACTION_GRAPH
from src.fee_simulator.specification.state_machine.path_analysis.path_generator import (
    generate_all_paths,
)
from src.fee_simulator.specification.state_machine.path_analysis.path_types import (
    PathConstraints,
)
from src.fee_simulator.specification.state_machine.path_analysis.variant_generator import (
    generate_all_path_variants,
)
from src.fee_simulator.utils import generate_random_eth_address, is_appeal_round
from src.fee_simulator.utils_round_sizes import find_previous_normal_round

LEADER_TIMEOUT = 100
VALIDATORS_TIMEOUT = 200
DEFAULT_STAKE = "2000000"

# Simulator round label -> consensus vector round type
ROUND_TYPE_MAP = {
    "NORMAL_ROUND": "NORMAL",
    "SKIP_ROUND": "SKIP",
    "LEADER_TIMEOUT": "LEADER_TIMEOUT",
    "LEADER_TIMEOUT_50_PERCENT": "LEADER_TIMEOUT_50%",
    "LEADER_TIMEOUT_50_PREVIOUS_APPEAL_BOND": "LEADER_TIMEOUT_50%_APPEAL_BOND",
    "LEADER_TIMEOUT_150_PREVIOUS_NORMAL_ROUND": "LEADER_TIMEOUT_150%_NORMAL",
    "APPEAL_LEADER_SUCCESSFUL": "LEADER_APPEAL_SUCCESSFUL",
    "APPEAL_LEADER_UNSUCCESSFUL": "LEADER_APPEAL_UNSUCCESSFUL",
    "APPEAL_LEADER_TIMEOUT_SUCCESSFUL": "LEADER_TIMEOUT_APPEAL_SUCCESSFUL",
    "APPEAL_LEADER_TIMEOUT_UNSUCCESSFUL": "LEADER_TIMEOUT_APPEAL_UNSUCCESSFUL",
    "APPEAL_VALIDATOR_SUCCESSFUL": "VALIDATOR_APPEAL_SUCCESSFUL",
    "APPEAL_VALIDATOR_UNSUCCESSFUL": "VALIDATOR_APPEAL_UNSUCCESSFUL",
    "SPLIT_PREVIOUS_APPEAL_BOND": "SPLIT_APPEAL_BOND",
    "EQUAL_SPLIT": "EQUAL_SPLIT",
    "EMPTY_ROUND": "EMPTY",
}

APPEAL_NODE_TO_CATEGORY = {
    "VALIDATOR_APPEAL_SUCCESSFUL": "validator_appeal_successful",
    "VALIDATOR_APPEAL_UNSUCCESSFUL": "validator_appeal_unsuccessful",
    "LEADER_APPEAL_SUCCESSFUL": "leader_appeal_successful",
    "LEADER_APPEAL_UNSUCCESSFUL": "leader_appeal_unsuccessful",
    "LEADER_APPEAL_TIMEOUT_SUCCESSFUL": "leader_timeout_appeal_successful",
    "LEADER_APPEAL_TIMEOUT_UNSUCCESSFUL": "leader_timeout_appeal_unsuccessful",
}


def categorize(path):
    # Convention (matches the original vector set): the LAST appeal in the
    # path determines the category.
    for node in reversed(path):
        if node in APPEAL_NODE_TO_CATEGORY:
            return APPEAL_NODE_TO_CATEGORY[node]
    return "no_appeal"


def pattern_name(path, total_rotations, rotation_kind="timeout"):
    core = " -> ".join(n for n in path if n not in ("START", "END"))
    if total_rotations:
        # [rot:N] = leader-timeout rotations (entries pay only the 50% comp);
        # [vrot:N] = vote-based rotations (entries also pay their aligned
        # validators per the backward rotation loop).
        tag = "vrot" if rotation_kind == "vote" else "rot"
        return f"{core} [{tag}:{total_rotations}]"
    return core


class AddressBook:
    """Humanize addresses: validators by first appearance, sender, appealant."""

    def __init__(self, sender, appealants):
        self.sender = sender
        self.appealants = list(appealants)
        self.validators = {}

    def name(self, addr):
        if addr == self.sender:
            return "sender"
        if addr in self.appealants:
            if len(self.appealants) == 1:
                return "appealant"
            return f"appealant{self.appealants.index(addr) + 1}"
        if addr not in self.validators:
            self.validators[addr] = f"validator{len(self.validators) + 1}"
        return self.validators[addr]


def leader_vote_string(vote):
    if (
        isinstance(vote, list)
        and vote
        and vote[0]
        in (
            "LEADER_RECEIPT",
            "LEADER_TIMEOUT",
        )
    ):
        return vote[0]
    return normalize_vote(vote)


def appeal_source_decision(source_round, source_round_label, appeal_label):
    """Return the source decision and contract status from processed rounds.

    The appeal label is the simulator's contextual classification of the
    admission state: leader-timeout and undetermined appeals can originate from
    rounds later recolored as SKIP for settlement.  Validator appeals still need
    their processed majority to distinguish Accepted from ValidatorsTimeout.
    This deliberately avoids indexing back into the graph path because graph
    nodes and processed round indices diverge in chained scenarios.
    """

    if appeal_label.startswith("APPEAL_LEADER_TIMEOUT"):
        return "LEADER_TIMEOUT", "LeaderTimeout"

    votes = source_round.rotations[-1].votes if source_round.rotations else {}
    majority = compute_majority(votes)
    if appeal_label.startswith("APPEAL_LEADER"):
        return f"LEADER_RECEIPT_{majority}", "Undetermined"
    if majority == "TIMEOUT":
        return "LEADER_RECEIPT_MAJORITY_TIMEOUT", "ValidatorsTimeout"
    if majority == "AGREE":
        return "LEADER_RECEIPT_MAJORITY_AGREE", "Accepted"
    raise ValueError(
        f"Unsupported validator-appeal source majority {majority} "
        f"from {source_round_label}"
    )


def build_appeal_quote_checkpoints(transaction_results, round_labels, budget):
    """Export every appeal-boundary quote, including its pricing provenance."""

    checkpoints = []
    for appeal_round_index, label in enumerate(round_labels):
        if not is_appeal_round(label):
            continue
        source_round_index = find_previous_normal_round(
            appeal_round_index, round_labels
        )
        if source_round_index is None:
            raise ValueError(
                f"Appeal round {appeal_round_index} has no source normal round"
            )
        quote = compute_appeal_bond_quote(
            normal_round_index=source_round_index,
            leader_timeout=budget.leaderTimeout,
            validators_timeout=budget.validatorsTimeout,
            round_labels=round_labels,
            appeal_round_index=appeal_round_index,
            rotations=budget.rotations,
        )
        source_round_label = round_labels[source_round_index]
        source_decision, source_status = appeal_source_decision(
            transaction_results.rounds[source_round_index], source_round_label, label
        )
        checkpoints.append(
            {
                "appeal_round_index": quote.appeal_round_index,
                "source_round_index": quote.source_round_index,
                "source_decision": source_decision,
                "source_round_label": source_round_label,
                "source_status": source_status,
                "appeal_label": quote.appeal_label,
                "committee_basis": quote.committee_basis,
                "committee_size": quote.committee_size,
                "attempts": quote.attempts,
                "leader_unit": str(quote.leader_unit),
                "validator_unit": str(quote.validator_unit),
                "leader_component": str(quote.leader_component),
                "validator_component": str(quote.validator_component),
                "expected_bond": str(quote.total),
            }
        )
    return checkpoints


def build_example(
    path, rotation_counts, addresses_pool, sender, appealant, rotation_kind="timeout"
):
    transaction_results, budget = path_to_transaction_results(
        path=path,
        addresses=addresses_pool,
        sender_address=sender,
        appealant_address=appealant,
        leader_timeout=LEADER_TIMEOUT,
        validators_timeout=VALIDATORS_TIMEOUT,
        rotation_counts=rotation_counts or {},
        rotation_kind=rotation_kind,
    )
    fee_events, round_labels = process_transaction(
        addresses=addresses_pool,
        transaction_results=transaction_results,
        transaction_budget=budget,
    )

    appealants = [a.appealantAddress for a in budget.appeals]
    book = AddressBook(budget.senderAddress, appealants)

    rounds_out = []
    for i, round_obj in enumerate(transaction_results.rounds):
        if not round_obj.rotations:
            continue
        votes = round_obj.rotations[-1].votes
        first_addr = next(iter(votes.keys()), None)
        validators_out = []
        for addr, vote in votes.items():
            is_leader = addr == first_addr and not round_labels[i].startswith("APPEAL_")
            validators_out.append(
                {
                    "address": book.name(addr),
                    "stake": DEFAULT_STAKE,
                    "vote": (
                        leader_vote_string(vote) if is_leader else normalize_vote(vote)
                    ),
                    "is_leader": is_leader,
                }
            )
        rounds_out.append(
            {
                "round_index": i,
                "type": ROUND_TYPE_MAP.get(round_labels[i], round_labels[i]),
                "validators": validators_out,
                "leader": book.name(first_addr) if first_addr else None,
            }
        )

    rewards = []
    penalties = []
    sender_earned = 0
    sender_refund = 0
    for e in fee_events:
        if e.address == budget.senderAddress:
            if e.earned:
                # Explicit sender credits (e.g. bond halves) and the final
                # refund both fold into sender_outcome
                if e.role == "SENDER" and e.round_index is None:
                    sender_refund += e.earned
                else:
                    sender_earned += e.earned
            continue
        if e.earned:
            rewards.append(
                {
                    "address": book.name(e.address),
                    "amount": str(e.earned),
                    "round_index": e.round_index,
                    "role": e.role,
                }
            )
        if e.burned:
            penalties.append(
                {
                    "address": book.name(e.address),
                    "amount": str(int(e.burned)),
                    "round_index": e.round_index,
                    "role": e.role,
                }
            )

    total_rotations = sum((rotation_counts or {}).values())
    name = pattern_name(path, total_rotations, rotation_kind)
    appeal_quotes = build_appeal_quote_checkpoints(
        transaction_results, round_labels, budget
    )
    example = {
        "description": f"Test Case: {name}",
        "initialState": {"rounds": rounds_out, "sender": "sender"},
        "actions": [{"type": "DISTRIBUTE_FEES", "epoch": 1}],
        "expectedState": {
            "rewards": rewards,
            "penalties": penalties,
            "sender_outcome": {
                "address": "sender",
                "net_change": str(sender_earned + sender_refund),
            },
        },
    }
    if appeal_quotes:
        example["checkpoints"] = {"appeal_quotes": appeal_quotes}
    if total_rotations:
        rot_list = [
            (rotation_counts or {}).get(k, 0)
            for k in range(max(rotation_counts.keys()) + 1)
        ]
        example["rotations"] = rot_list
    return name, example


def summarize(examples):
    rewards = sum(
        int(r["amount"]) for ex in examples for r in ex["expectedState"]["rewards"]
    )
    penalties = sum(
        int(p["amount"]) for ex in examples for p in ex["expectedState"]["penalties"]
    )
    sender = sum(
        int(ex["expectedState"]["sender_outcome"]["net_change"]) for ex in examples
    )
    return {"rewards": rewards, "penalties": penalties, "sender_outcomes": sender}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="consensus_vectors")
    parser.add_argument("--max-length", type=int, default=7)
    parser.add_argument("--max-rotations", type=int, default=2)
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed for deterministic validator-address generation (default: 0).",
    )
    parser.add_argument(
        "--appeal-quote-output",
        default=None,
        help=(
            "Optional standalone path for the compact appeal-quote campaign. "
            "The full category vectors still go to --output-dir."
        ),
    )
    parser.add_argument(
        "--existing-dir",
        default=None,
        help="Existing simulator_results dir; complex-scenario dirs are rebuilt "
        "keeping their pattern keys",
    )
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    random.seed(args.seed)
    addresses_pool = [generate_random_eth_address() for _ in range(5000)]
    sender = addresses_pool[-1]
    appealant = addresses_pool[-2]

    paths = list(
        generate_all_paths(
            TRANSACTION_GRAPH,
            PathConstraints(
                # min_length=2 keeps the single-round (no appeal) paths
                min_length=2,
                max_length=args.max_length,
                source_node="START",
                target_node="END",
            ),
        )
    )
    print(f"paths: {len(paths)}")

    # category -> pattern -> examples (base and rotations kept separate)
    base = defaultdict(lambda: defaultdict(list))
    rot = defaultdict(lambda: defaultdict(list))
    counts = defaultdict(int)
    errors = []
    quote_candidates = {}

    for variant in generate_all_path_variants(
        paths, max_rotations=args.max_rotations, max_idle=0
    ):
        total_rotations = sum((variant.rotation_counts or {}).values())
        # Rotation variants are emitted in both flavors: leader-timeout
        # rotations ([rot:N]) and vote-based rotations ([vrot:N]), which pay
        # their entries' aligned validators per the backward rotation loop.
        kinds = ("timeout", "vote") if total_rotations else ("timeout",)
        for rotation_kind in kinds:
            try:
                name, example = build_example(
                    variant.path,
                    variant.rotation_counts,
                    addresses_pool,
                    sender,
                    appealant,
                    rotation_kind=rotation_kind,
                )
            except Exception as e:  # noqa: BLE001 - report and continue
                errors.append((variant.path, variant.rotation_counts, str(e)[:150]))
                continue
            category = categorize(variant.path)
            bucket = rot if total_rotations else base
            max_examples = 1 if total_rotations else 2
            if len(bucket[category][name]) < max_examples:
                bucket[category][name].append(example)
            counts[category] += 1

            quotes = example.get("checkpoints", {}).get("appeal_quotes", [])
            for quote in quotes:
                signature = (
                    quote["source_status"],
                    quote["committee_basis"],
                    quote["committee_size"],
                    quote["attempts"],
                )
                candidate = {
                    "category": category,
                    "pattern": name,
                    "example": example,
                }
                rank = (
                    len(example["initialState"]["rounds"]),
                    total_rotations,
                    name,
                )
                current = quote_candidates.get(signature)
                if current is None or rank < current[0]:
                    quote_candidates[signature] = (rank, candidate)

    def write_category(category, patterns, suffix):
        data = {
            "category": f"{category}{suffix.replace('_compressed', '')}",
            "total_cases": sum(len(exs) for exs in patterns.values()),
            "patterns": {
                nm: {
                    "count": len(exs),
                    "examples": exs,
                    "summary": summarize(exs),
                }
                for nm, exs in sorted(patterns.items())
            },
        }
        path = out / f"{category}{suffix}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent="\t")
        print(f"wrote {path} ({data['total_cases']} cases)")

    for category, patterns in sorted(base.items()):
        write_category(category, patterns, "_compressed")
    for category, patterns in sorted(rot.items()):
        write_category(category, patterns, "_rotations_compressed")

    with open(out / "summary.json", "w") as f:
        json.dump(
            {
                "total_test_cases": sum(counts.values()),
                "categories": {
                    c: {
                        "count": n,
                        "unique_patterns": len(base[c]) + len(rot[c]),
                    }
                    for c, n in sorted(counts.items())
                },
            },
            f,
            indent="\t",
        )

    quote_signatures = set(quote_candidates)
    quote_campaign_by_pattern = {}
    for _, candidate in quote_candidates.values():
        key = (candidate["category"], candidate["pattern"])
        quote_campaign_by_pattern[key] = candidate
    quote_campaign = [
        quote_campaign_by_pattern[key] for key in sorted(quote_campaign_by_pattern)
    ]

    quote_output = (
        Path(args.appeal_quote_output)
        if args.appeal_quote_output
        else out / "appeal_quote_checkpoints.json"
    )
    quote_output.parent.mkdir(parents=True, exist_ok=True)
    with open(quote_output, "w") as f:
        json.dump(
            {
                "schema_version": 1,
                "description": (
                    "Simulator appeal-price checkpoints selected to cover every "
                    "status, committee basis, committee size, and attempt count."
                ),
                "covered_signatures": [
                    {
                        "source_status": status,
                        "committee_basis": basis,
                        "committee_size": size,
                        "attempts": attempts,
                    }
                    for status, basis, size, attempts in sorted(quote_signatures)
                ],
                "cases": quote_campaign,
            },
            f,
            indent="\t",
        )
    print(
        f"wrote {quote_output} "
        f"({len(quote_campaign)} cases, {len(quote_signatures)} signatures)"
    )

    # Rebuild complex-scenario files keeping existing pattern keys
    if args.existing_dir:
        existing = Path(args.existing_dir)
        for sub in sorted(existing.glob("*complex_scenarios")):
            out_sub = out / sub.name
            out_sub.mkdir(exist_ok=True)
            for jf in sorted(sub.glob("*.json")):
                old = json.loads(jf.read_text())
                if "patterns" not in old:
                    continue
                new_patterns = {}
                for nm, pd in old["patterns"].items():
                    rotation_kind = "vote" if " [vrot:" in nm else "timeout"
                    core = nm.split(" [vrot:")[0].split(" [rot:")[0]
                    path = ["START"] + core.split(" -> ") + ["END"]
                    old_ex = pd["examples"][0] if pd.get("examples") else {}
                    rot_list = old_ex.get("rotations") or []
                    rotation_counts = {i: r for i, r in enumerate(rot_list) if r}
                    try:
                        gen_name, example = build_example(
                            path,
                            rotation_counts,
                            addresses_pool,
                            sender,
                            appealant,
                            rotation_kind=rotation_kind,
                        )
                    except Exception as e:  # noqa: BLE001
                        errors.append((path, rotation_counts, str(e)[:150]))
                        continue
                    new_patterns[gen_name] = {
                        "count": 1,
                        "examples": [example],
                        "summary": summarize([example]),
                    }
                with open(out_sub / jf.name, "w") as f:
                    json.dump(
                        {
                            "category": old.get("category", jf.stem),
                            "total_cases": len(new_patterns),
                            "patterns": new_patterns,
                        },
                        f,
                        indent="\t",
                    )
                print(f"rebuilt {out_sub / jf.name} ({len(new_patterns)} patterns)")

    if errors:
        print(f"\n{len(errors)} variants failed:")
        for p, rc, msg in errors[:10]:
            print(f"  {'->'.join(p)} rot={rc}: {msg}")
    print("done")


if __name__ == "__main__":
    main()
