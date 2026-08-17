"""Run the green and expected-red endogenous-evaluator TLC campaigns.

The runner uses a fresh metadata directory per campaign so parallel or rapid
invocations cannot collide. It requires only a Java runtime and tla2tools.jar.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Optional

from src.fee_simulator.analysis.paper_fee_kernel_tla import (
    render_paper_fee_kernel_tla,
)
from src.fee_simulator.analysis.paper_property_sweep import (
    verify_first_rung_paper_properties,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TLA_DIRECTORY = REPOSITORY_ROOT / "formal" / "tla"
MODEL = "EndogenousEvaluatorAttraction.tla"

CAMPAIGNS = (
    ("green", "EndogenousEvaluatorAttraction.cfg", True, "No error has been found"),
    (
        "no effective diagnostics",
        "EndogenousEvaluatorAttraction_no_effective_diagnostics_expected_red.cfg",
        False,
        "Invariant GoodBasin is violated",
    ),
    (
        "no vindication",
        "EndogenousEvaluatorAttraction_no_vindication_expected_red.cfg",
        False,
        "Invariant GoodBasin is violated",
    ),
    (
        "weak payoff response",
        "EndogenousEvaluatorAttraction_weak_response_expected_red.cfg",
        False,
        "Temporal properties were violated",
    ),
    (
        "bad bootstrap",
        "EndogenousEvaluatorAttraction_bad_bootstrap_expected_red.cfg",
        False,
        "Temporal properties were violated",
    ),
)


def _working_java(candidate: Path) -> bool:
    if not candidate.exists():
        return False
    result = subprocess.run(
        [str(candidate), "-version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def find_java(explicit: Optional[Path]) -> Path:
    candidates = []
    if explicit is not None:
        candidates.append(explicit)
    if os.environ.get("JAVA_BIN"):
        candidates.append(Path(os.environ["JAVA_BIN"]))
    discovered = shutil.which("java")
    if discovered:
        candidates.append(Path(discovered))
    candidates.extend(
        [
            Path("/opt/homebrew/opt/openjdk@17/bin/java"),
            Path("/opt/homebrew/opt/openjdk/bin/java"),
        ]
    )
    for candidate in candidates:
        if _working_java(candidate):
            return candidate
    raise SystemExit("No working Java runtime found; pass --java or set JAVA_BIN")


def find_tla_jar(explicit: Optional[Path]) -> Path:
    candidates = []
    if explicit is not None:
        candidates.append(explicit)
    if os.environ.get("TLA2TOOLS_JAR"):
        candidates.append(Path(os.environ["TLA2TOOLS_JAR"]))
    candidates.append(REPOSITORY_ROOT / "tla2tools.jar")
    for editor_root in (
        Path.home() / ".cursor" / "extensions",
        Path.home() / ".vscode" / "extensions",
    ):
        candidates.extend(
            sorted(editor_root.glob("alygin.vscode-tlaplus-*/tools/tla2tools.jar"))
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit("tla2tools.jar not found; pass --jar or set TLA2TOOLS_JAR")


def check_generated_kernel() -> None:
    checked_in = TLA_DIRECTORY / "PaperFeeKernel.tla"
    rendered = render_paper_fee_kernel_tla(verify_first_rung_paper_properties())
    if not checked_in.exists() or checked_in.read_text() != rendered:
        raise SystemExit(
            "PaperFeeKernel.tla is stale; run "
            "scripts/10_generate_paper_fee_kernel_tla.py"
        )


def distinct_states(output: str) -> str:
    matches = re.findall(r"([0-9]+) distinct states found", output)
    return matches[-1] if matches else "unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--java", type=Path)
    parser.add_argument("--jar", type=Path)
    args = parser.parse_args()

    check_generated_kernel()
    java = find_java(args.java)
    tla_jar = find_tla_jar(args.jar)

    with tempfile.TemporaryDirectory(prefix="paper-attraction-tlc-") as temp:
        for index, (name, config, should_pass, evidence) in enumerate(CAMPAIGNS):
            metadata = Path(temp) / f"campaign-{index}"
            command = [
                str(java),
                "-XX:+UseParallelGC",
                "-cp",
                str(tla_jar),
                "tlc2.TLC",
                "-nowarning",
                "-workers",
                "1",
                "-metadir",
                str(metadata),
                "-config",
                config,
                MODEL,
            ]
            result = subprocess.run(
                command,
                cwd=TLA_DIRECTORY,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            outcome_matches = (
                result.returncode == 0 if should_pass else result.returncode != 0
            )
            if not outcome_matches or evidence not in result.stdout:
                print(result.stdout)
                raise SystemExit(
                    f"Unexpected TLC result for {name}: exit {result.returncode}"
                )
            expectation = "GREEN" if should_pass else "EXPECTED RED"
            print(
                f"PASS [{expectation}]: {name} "
                f"({distinct_states(result.stdout)} distinct states)"
            )


if __name__ == "__main__":
    main()
