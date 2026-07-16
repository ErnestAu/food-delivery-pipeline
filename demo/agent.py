#!/usr/bin/env python3
"""Review a simulated analyst dbt pull request without modifying any SQL."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DBT_PROJECT = REPO_ROOT / "dbt" / "food_delivery"
MODEL_CONTRACT_PATH = DBT_PROJECT / "models" / "analyst_pr" / "schema.yml"
RULES_PATH = REPO_ROOT / "AGENTS.md"
RESPONSE_SCHEMA = REPO_ROOT / "demo" / "review_response_schema.json"
DEMO_DATA_LOADER = REPO_ROOT / "demo" / "load_demo_data.py"
DBT_BIN = Path(os.environ.get("DBT_BIN", REPO_ROOT / ".venv" / "bin" / "dbt"))
CODEX_BIN = os.environ.get("CODEX_BIN", "/Applications/ChatGPT.app/Contents/Resources/codex")
CORE_MODELS = [
    "dim_customer",
    "dim_vendor",
    "dim_driver",
    "dim_menu_item",
    "fct_order_events",
    "fct_orders",
]
SCENARIOS = {
    "vendor-performance": {
        "model_name": "fct_vendor_daily_performance",
        "model_path": DBT_PROJECT / "models" / "analyst_pr" / "fct_vendor_daily_performance.sql",
        "context_paths": [
            DBT_PROJECT / "models" / "facts" / "fct_orders.sql",
            DBT_PROJECT / "models" / "dims" / "dim_vendor.sql",
        ],
        "review_posture": (
            "This is a declared relationship-resolution contract. A join between an ID and an unrelated "
            "dimension attribute is a high-confidence mechanical defect; suggest the smallest correction."
        ),
    },
    "lifecycle-timeline": {
        "model_name": "fct_order_lifecycle_timeline",
        "model_path": DBT_PROJECT / "models" / "analyst_pr" / "fct_order_lifecycle_timeline.sql",
        "context_paths": [DBT_PROJECT / "models" / "facts" / "fct_orders.sql"],
        "review_posture": (
            "This PR deliberately changes lifecycle timestamp semantics. A failure of the existing ordering "
            "contract may reflect an intended reporting-time, time-zone, or late-arrival policy. Return "
            "warn_for_review with a clarifying question; do not suggest SQL, even if a simple edit could "
            "make the current test pass."
        ),
    },
}


def run(
    command: list[str],
    *,
    cwd: Path,
    echo_output: bool = True,
    display_command: str | None = None,
) -> subprocess.CompletedProcess[str]:
    print("\n$", display_command or " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if echo_output and result.stdout:
        print(result.stdout, end="")
    if echo_output and result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result


def dbt(*arguments: str) -> subprocess.CompletedProcess[str]:
    return run([str(DBT_BIN), *arguments, "--target", "demo"], cwd=DBT_PROJECT)


def bootstrap() -> int:
    """Recreate the local warehouse and prove the established core is green."""
    data_load = run([sys.executable, str(DEMO_DATA_LOADER)], cwd=REPO_ROOT)
    if data_load.returncode:
        return data_load.returncode

    for arguments in (("run", "--select", *CORE_MODELS), ("test", "--select", "fct_orders")):
        result = dbt(*arguments)
        if result.returncode:
            return result.returncode
    print("\nCore baseline is green. Run --review to evaluate the simulated analyst PR.")
    return 0


def run_pr_check(scenario: dict[str, object]) -> tuple[bool, str]:
    """Build the candidate with its parents, then collect its independent dbt verdict."""
    model_name = str(scenario["model_name"])
    build = dbt("run", "--select", f"+{model_name}")
    if build.returncode:
        return False, build.stdout + build.stderr

    test = dbt("test", "--select", model_name)
    return test.returncode == 0, test.stdout + test.stderr


def supporting_context(scenario: dict[str, object]) -> str:
    parts = []
    for path in scenario["context_paths"]:
        assert isinstance(path, Path)
        parts.append(f"--- {path.relative_to(REPO_ROOT)} ---\n{path.read_text()}")
    return "\n\n".join(parts)


def request_review(failure_output: str, scenario: dict[str, object], model: str | None) -> dict[str, str]:
    """Ask Codex for a structured review while keeping it sandboxed read-only."""
    codex = shutil.which(CODEX_BIN) if not Path(CODEX_BIN).exists() else CODEX_BIN
    if not codex:
        raise RuntimeError("Codex CLI was not found. Set CODEX_BIN before running a review.")

    model_option = ["--model", model] if model else []
    model_path = scenario["model_path"]
    assert isinstance(model_path, Path)
    prompt = f"""You are a dbt pull-request reviewer. You do not edit files.

{RULES_PATH.read_text()}

Review posture for this scenario:
{scenario['review_posture']}

Candidate analyst model: {model_path.relative_to(REPO_ROOT)}
--- candidate SQL ---
{model_path.read_text()}
--- candidate contract ---
{MODEL_CONTRACT_PATH.read_text()}
--- dbt PR-check output ---
{failure_output}
--- relevant established-model context ---
{supporting_context(scenario)}

Classify this pull request using only the supplied contract and model context:
- suggest_fix / high: one minimal SQL correction is directly supported by the failed contract.
- warn_for_review / warning: the behavior could be intentional and needs an analyst decision.
- pass / info: the check passes and no review concern is apparent.

For suggest_fix, return the complete proposed candidate SQL. For warn_for_review
and pass, return an empty proposed_sql. Never propose edits to tests, sources,
seeds, configuration, or established core models.
"""

    with tempfile.TemporaryDirectory(prefix="dbt-pr-review-") as directory:
        output_path = Path(directory) / "review.json"
        command = [
            str(codex),
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--cd",
            str(REPO_ROOT),
            "--output-schema",
            str(RESPONSE_SCHEMA),
            "--output-last-message",
            str(output_path),
            *model_option,
            prompt,
        ]
        result = run(
            command,
            cwd=REPO_ROOT,
            echo_output=False,
            display_command="codex exec --sandbox read-only (reviewing analyst PR)",
        )
        if result.returncode:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            raise RuntimeError("Codex did not return a structured PR review.")
        review = json.loads(output_path.read_text())

    required = {"decision", "severity", "summary", "rationale", "proposed_sql", "clarifying_question"}
    expected_severity = {"suggest_fix": "high", "warn_for_review": "warning", "pass": "info"}
    if (
        not required.issubset(review)
        or review["decision"] not in expected_severity
        or review["severity"] != expected_severity[review["decision"]]
    ):
        raise RuntimeError("Codex response did not match the PR-review schema.")
    return review


def validate_proposal(proposed_sql: str) -> str:
    candidate = proposed_sql.rstrip() + "\n"
    if not candidate.strip() or candidate.lstrip().startswith("```"):
        raise RuntimeError("The proposed SQL is not a complete raw model file.")
    normalized = candidate.lstrip().lower()
    while normalized.startswith("--"):
        _, _, normalized = normalized.partition("\n")
        normalized = normalized.lstrip()
    if not normalized.startswith(("with ", "select ")):
        raise RuntimeError("The proposal is not a read-only dbt model query.")
    blocked = ("insert ", "update ", "delete ", "drop ", "alter ", "create ", "attach ")
    if any(keyword in normalized for keyword in blocked):
        raise RuntimeError("The proposal contains a disallowed mutation or DDL keyword.")
    return candidate


def show_review(review: dict[str, str], scenario: dict[str, object]) -> None:
    print(f"\nDecision: {review['decision']}")
    print(f"Severity: {review['severity']}")
    print(f"Summary: {review['summary']}")
    print(f"Rationale: {review['rationale']}")

    if review["decision"] == "suggest_fix":
        proposed_sql = validate_proposal(review["proposed_sql"])
        model_path = scenario["model_path"]
        assert isinstance(model_path, Path)
        diff = difflib.unified_diff(
            model_path.read_text().splitlines(keepends=True),
            proposed_sql.splitlines(keepends=True),
            fromfile=f"a/{model_path.relative_to(REPO_ROOT)}",
            tofile=f"b/{model_path.relative_to(REPO_ROOT)} (proposed)",
        )
        print("\nProposed diff (not applied):")
        print("".join(diff), end="")
    elif review["decision"] == "warn_for_review":
        print(f"\nQuestion for analyst: {review['clarifying_question']}")

    print("\nNo SQL files were changed. A human must accept any proposal.")


def review(scenario_name: str, model: str | None) -> int:
    scenario = SCENARIOS[scenario_name]
    passed, output = run_pr_check(scenario)
    if passed:
        show_review(
            {
                "decision": "pass",
                "severity": "info",
                "summary": "The candidate model's dbt check passed.",
                "rationale": "No failed contract was supplied for remediation.",
                "proposed_sql": "",
                "clarifying_question": "",
            },
            scenario,
        )
        return 0

    show_review(request_review(output, scenario, model), scenario)
    # A failed PR check is the review input, not a reviewer execution failure.
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bootstrap", action="store_true", help="Recreate DuckDB and verify core models.")
    group.add_argument("--review", action="store_true", help="Run the analyst PR check and print a review proposal.")
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS.keys(),
        default="vendor-performance",
        help="Analyst PR scenario to review (default: vendor-performance).",
    )
    parser.add_argument("--model", help="Optional Codex model override; defaults to local Codex configuration.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return bootstrap() if args.bootstrap else review(args.scenario, args.model)


if __name__ == "__main__":
    raise SystemExit(main())
