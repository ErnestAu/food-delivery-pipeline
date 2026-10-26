"""Keep one GitHub issue per dashboard outage, driven by the keep-alive verdict.

Reads STATUS (ok/down) and CAUSE from the keep-alive check. The first failed check
opens a `dashboard-down` issue, a change of cause adds a comment, and the first
passing check closes it with the downtime. Uses `gh` with the workflow's token;
DRY_RUN=1 prints the write commands instead of running them.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timezone

LABEL = "dashboard-down"

CAUSES = {
    "token-rejected": (
        "Databricks token rejected",
        "Databricks refused the dashboard's access token: it has expired or been revoked. "
        "Rotate `DATABRICKS_TOKEN` in Streamlit Cloud secrets, then reboot the app "
        "(the token is read at import).",
    ),
    "compute-blocked": (
        "Databricks compute blocked",
        "Databricks won't start compute for the workspace: Free Edition marks idle "
        "workspaces inactive, and token traffic doesn't count as activity. Log in to the "
        "workspace and start the warehouse; rotating the token doesn't help.",
    ),
    "query-failed": (
        "Warehouse query failed",
        "The warehouse accepted the connection but a query failed. The full error is in "
        "the Streamlit Cloud app logs.",
    ),
    "app-exception": (
        "App error",
        "The app raised an uncaught exception before reaching the warehouse. The full "
        "error is in the Streamlit Cloud app logs.",
    ),
    "no-content": (
        "Dashboard not rendering",
        "The page never rendered dashboard content: an app that didn't wake, a Streamlit "
        "Cloud error page, or a timeout. The check run's log has the page text.",
    ),
    "data-stale": (
        "Data stale",
        "The dashboard is up, but the newest order in gold is more than a week old: the pipeline "
        "has stopped. Check the Databricks job, and log in to the workspace in case compute is blocked.",
    ),
    "data-missing": (
        "No data",
        "The dashboard is up, but gold has no order events at all.",
    ),
}

# Data causes are about the pipeline behind a working dashboard, so they read differently.
_TITLES = {
    "data-stale": "Pipeline stalled: no new orders for over a week",
    "data-missing": "Pipeline empty: no orders in gold",
}

_MARKER = re.compile(r"<!-- cause: ([a-z-]+) -->")


def describe(cause: str) -> tuple[str, str]:
    return CAUSES.get(cause, (cause, "The dashboard reported a status this check doesn't recognise."))


def title(cause: str) -> str:
    return _TITLES.get(cause, f"Dashboard down: {describe(cause)[0]}")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def last_cause(texts: list[str]) -> str | None:
    found = [kind for text in texts for kind in _MARKER.findall(text or "")]
    return found[-1] if found else None


def decide(open_issue: bool, last: str | None, status: str, cause: str) -> str:
    if status == "ok":
        return "close" if open_issue else "none"
    if not open_issue:
        return "open"
    return "none" if cause == last else "comment"


def format_duration(start: datetime, end: datetime) -> str:
    minutes = max(0, int((end - start).total_seconds() // 60))
    days, rest = divmod(minutes, 24 * 60)
    hours, minutes = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _utc(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def issue_body(cause: str, app_url: str, run_url: str, now: datetime) -> str:
    label, meaning = describe(cause)
    finding = "data out of date" if cause in _TITLES else "down"
    return "\n".join([
        f"The scheduled health check found the [live dashboard]({app_url}) {finding}.",
        "",
        f"- **Cause:** {label}",
        f"- **First detected:** {_utc(now)}",
        f"- **Check run:** {run_url}",
        "",
        meaning,
        "",
        "This issue closes itself when a check passes.",
        "",
        f"<!-- cause: {cause} -->",
    ])


def gh(*args: str, write: bool = True) -> str:
    if write and os.environ.get("DRY_RUN"):
        print("DRY_RUN: gh " + " ".join(shlex.quote(a) for a in args))
        return ""
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main() -> None:
    status, cause = os.environ["STATUS"], os.environ.get("CAUSE", "")
    app_url, run_url = os.environ["APP_URL"], os.environ["RUN_URL"]
    now = datetime.now(timezone.utc)

    gh("label", "create", LABEL, "--color", "B60205",
       "--description", "Opened and closed by the keep-alive health check", "--force")
    listed = gh("issue", "list", "--label", LABEL, "--state", "open",
                "--json", "number,body,createdAt,comments", "--limit", "1", write=False)
    issues = json.loads(listed or "[]")
    issue = issues[0] if issues else None
    last = last_cause([issue["body"], *(c["body"] for c in issue["comments"])]) if issue else None

    action = decide(issue is not None, last, status, cause)
    if action == "open":
        gh("issue", "create", "--title", title(cause),
           "--label", LABEL, "--body", issue_body(cause, app_url, run_url, now))
    elif action == "comment":
        old = describe(last)[0] if last else "unknown"
        label, meaning = describe(cause)
        gh("issue", "comment", str(issue["number"]), "--body",
           f"Cause changed: {old} → {label}. {meaning} ([check run]({run_url}))\n\n<!-- cause: {cause} -->")
        gh("issue", "edit", str(issue["number"]), "--title", title(cause))
    elif action == "close":
        took = format_duration(parse_ts(issue["createdAt"]), now)
        gh("issue", "close", str(issue["number"]), "--comment",
           f"Recovered: the check passed at {_utc(now)}, {took} after this outage was first detected.")
    print(f"Issue action: {action}" + (f" (#{issue['number']})" if issue else ""))


if __name__ == "__main__":
    main()
