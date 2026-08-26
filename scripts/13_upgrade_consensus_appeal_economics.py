#!/usr/bin/env python3
"""Upgrade checked-in consensus vectors without regenerating scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fee_simulator.analysis.consensus_vector_conformance import (  # noqa: E402
    upgrade_case_to_current_appeal_economics,
)


ECONOMICS_VERSION = "successful-appeal-5/2-vindication-v1"


def summarize(examples: list[dict]) -> dict[str, int]:
    return {
        "rewards": sum(
            int(reward["amount"])
            for example in examples
            for reward in example["expectedState"]["rewards"]
        ),
        "penalties": sum(
            int(penalty["amount"])
            for example in examples
            for penalty in example["expectedState"]["penalties"]
        ),
        "sender_outcomes": sum(
            int(example["expectedState"]["sender_outcome"]["net_change"])
            for example in examples
        ),
    }


def upgrade_file(path: Path, *, write: bool) -> tuple[int, bool]:
    payload = json.loads(path.read_text())
    patterns = payload.get("patterns")
    if not patterns or payload.get("appeal_economics_version") == ECONOMICS_VERSION:
        return 0, False

    upgraded_cases = 0
    for pattern, pattern_data in patterns.items():
        examples = pattern_data.get("examples", [])
        upgraded = []
        for example_index, example in enumerate(examples):
            future = upgrade_case_to_current_appeal_economics(
                example,
                source=str(path),
                pattern=pattern,
                example_index=example_index,
            )
            upgraded.append(future)
            if future != example:
                upgraded_cases += 1
        pattern_data["examples"] = upgraded
        if "summary" in pattern_data:
            pattern_data["summary"] = summarize(upgraded)

    if upgraded_cases == 0:
        return 0, False
    payload["appeal_economics_version"] = ECONOMICS_VERSION
    if write:
        path.write_text(json.dumps(payload, indent="\t") + "\n")
    return upgraded_cases, True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vectors_dir", type=Path)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the validated upgrades; otherwise report the pending files",
    )
    args = parser.parse_args()

    files = 0
    cases = 0
    for path in sorted(args.vectors_dir.rglob("*.json")):
        upgraded_cases, changed = upgrade_file(path, write=args.write)
        if changed:
            files += 1
            cases += upgraded_cases
            action = "upgraded" if args.write else "would upgrade"
            print(f"{action}: {path} ({upgraded_cases} cases)")
    print(f"files={files} cases={cases} write={args.write}")


if __name__ == "__main__":
    main()
