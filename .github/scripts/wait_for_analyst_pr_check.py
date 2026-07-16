#!/usr/bin/env python3
"""Wait for the unprivileged DuckDB check and save its failed-job log as review evidence."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


WORKFLOW_FILE = "analyst_pr_ci.yml"
POLL_SECONDS = 10
MAX_POLLS = 24


def gh_json(*arguments: str) -> dict[str, object]:
    result = subprocess.run(["gh", *arguments], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "GitHub CLI request failed.")
    return json.loads(result.stdout)


def gh_text(*arguments: str) -> str:
    result = subprocess.run(["gh", *arguments], text=True, capture_output=True)
    # gh run view --log-failed can return non-zero after printing useful logs.
    if result.returncode and not result.stdout:
        raise RuntimeError(result.stderr.strip() or "Unable to download failed-job logs.")
    return result.stdout + result.stderr


def write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a") as output:
            output.write(f"{name}={value}\n")


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    head_sha = os.environ["PR_HEAD_SHA"]
    head_ref = os.environ["PR_HEAD_REF"]
    result_path = Path(os.environ["ANALYST_CHECK_RESULT_PATH"])

    for attempt in range(MAX_POLLS):
        runs = gh_json(
            "api",
            f"repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs?event=pull_request&per_page=30",
        ).get("workflow_runs", [])
        matching = [
            run
            for run in runs
            if run.get("head_sha") == head_sha or run.get("head_branch") == head_ref
        ]
        if matching:
            run = max(matching, key=lambda item: item["id"])
            if run["status"] == "completed":
                conclusion = str(run.get("conclusion") or "unknown")
                evidence = ""
                if conclusion == "failure":
                    evidence = gh_text("run", "view", str(run["id"]), "--log-failed")[-12000:]
                result_path.write_text(
                    json.dumps(
                        {
                            "run_id": run["id"],
                            "conclusion": conclusion,
                            "failure_output": evidence,
                        }
                    )
                )
                write_output("conclusion", conclusion)
                print(f"Analyst PR DuckDB Check concluded: {conclusion}")
                return 0

        if attempt < MAX_POLLS - 1:
            print("Waiting for Analyst PR DuckDB Check...", flush=True)
            time.sleep(POLL_SECONDS)

    raise RuntimeError("Timed out waiting for Analyst PR DuckDB Check.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"::error::{error}", file=sys.stderr)
        raise
