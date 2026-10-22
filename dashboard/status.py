"""Public-safe status kinds for warehouse failures.

The keep-alive check reads these kinds from the page (see db.show_status), so the
names are a contract: token-rejected, compute-blocked, query-failed.
"""
from __future__ import annotations

import re

KINDS = ("token-rejected", "compute-blocked", "query-failed")

MESSAGES = {
    "token-rejected": (
        "Databricks rejected this dashboard's access token, so it can't query the "
        "warehouse until the token is rotated."
    ),
    "compute-blocked": (
        "Databricks has paused compute for this Free Edition workspace, so live data "
        "is back once the workspace is reactivated."
    ),
    "query-failed": "A warehouse query failed. The full error is in the app logs.",
}

_TOKEN = re.compile(r"invalid access token|token .*expired", re.IGNORECASE)
_COMPUTE = re.compile(
    r"cannot create the resource|DENY_NEW_AND_EXISTING_RESOURCES|resource-gatekeeper",
    re.IGNORECASE,
)


def classify_error(exc: BaseException) -> str:
    """Map a databricks-sql-connector failure to one of KINDS."""
    message = str(exc)
    context = getattr(exc, "context", None) or {}
    if str(context.get("http-code", "")) in {"401", "403"} or _TOKEN.search(message):
        return "token-rejected"
    if _COMPUTE.search(message):
        return "compute-blocked"
    return "query-failed"
