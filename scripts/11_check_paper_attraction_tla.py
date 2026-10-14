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
    ("green", "EndogenousEvaluatorAttraction.cfg", "pass", None),
    (
        "no effective diagnostics",
        "EndogenousEvaluatorAttraction_no_effective_diagnostics_expected_red.cfg",
        "invariant",
        "GoodBasin",
    ),
    (
        "no vindication",
        "EndogenousEvaluatorAttraction_no_vindication_expected_red.cfg",
        "invariant",
        "GoodBasin",
    ),
    (
        "weak payoff response",
        "EndogenousEvaluatorAttraction_weak_response_expected_red.cfg",
        "temporal",
        "EventuallyStableFullCompetence",
    ),
    (
        "bad bootstrap",
        "EndogenousEvaluatorAttraction_bad_bootstrap_expected_red.cfg",
        "temporal",
        "EventuallyStableFullCompetence",
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
    matches = re.findall(r"([\d,]+) distinct states found", output)
    return matches[-1].replace(",", "") if matches else "unknown"


def outcome_matches(code: int, output: str, expected: str, property_name: Optional[str]) -> bool:
    states = distinct_states(output)
    if states == "unknown" or int(states) == 0:
        return False
    if expected == "pass":
        return code == 0 and "Model checking completed. No error has been found." in output
    if expected == "invariant":
        violation = re.search(r"Invariant (\w+) is violated", output)
        return code == 12 and violation is not None and violation[1] == property_name
    if expected == "temporal":
        # Legacy generic wording is safe only with the one-property config
        # check below. New TLC identifies the actual violated property.
        named = re.search(r"Temporal property (\w+) was violated", output)
        matches = named[1] == property_name if named else "Temporal properties were violated" in output
        return (code == 13 and matches
                and ("Stuttering" in output or "Back to state" in output)
                and re.search(r"Invariant \w+ is violated", output) is None)
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--java", type=Path)
    parser.add_argument("--jar", type=Path)
    args = parser.parse_args()

    check_generated_kernel()
    java = find_java(args.java)
    tla_jar = find_tla_jar(args.jar)

    with tempfile.TemporaryDirectory(prefix="paper-attraction-tlc-") as temp:
        for index, (name, config, expected, property_name) in enumerate(CAMPAIGNS):
            if expected == "temporal":
                properties = re.findall(r"^PROPERTY\s+(\w+)\s*$", (TLA_DIRECTORY / config).read_text(), re.M)
                if properties != [property_name]:
                    raise SystemExit(f"Expected exactly the named temporal property in {config}")
            metadata = Path(temp) / f"campaign-{index}"
            command = [
                str(java),
                "-XX:+UseParallelGC",
                "-XX:ActiveProcessorCount=1",
                "-Xmx768m",
                "-Djava.io.tmpdir=" + temp,
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
            # Isolate generated trace-explorer files from the source checkout.
            work = Path(temp) / f"model-{index}"
            work.mkdir()
            for source in (MODEL, "PaperFeeKernel.tla", config):
                shutil.copyfile(TLA_DIRECTORY / source, work / source)
            result = subprocess.run(
                command,
                cwd=work,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=300,
            )
            if not outcome_matches(result.returncode, result.stdout, expected, property_name):
                print(result.stdout)
                raise SystemExit(
                    f"Unexpected TLC result for {name}: exit {result.returncode}"
                )
            expectation = "GREEN" if expected == "pass" else "EXPECTED RED"
            print(
                f"PASS [{expectation}]: {name} "
                f"({distinct_states(result.stdout)} distinct states)"
            )


if __name__ == "__main__":
    main()
