# Keep-alive health check: design

**Date:** 2026-10-22 · **Branch:** `fix/keepalive-health-check` · **Status:** decided in a design Q&A with the maintainer; reviewed in the PR

## Problem

`.github/workflows/keepalive.yml` opens the Streamlit app every 6 hours, clicks the wake button if the app is asleep, waits 15 seconds, and exits 0. It has passed every run, but it never looks at what the page shows. On 2026-10-22 the live dashboard was showing a redacted `databricks.sql.exc.RequestError` on Pipeline Health while the previous night's run reported success.

The dashboard depends on one credential, `DATABRICKS_TOKEN` in Streamlit Cloud secrets (dbt CI keeps a separate copy in GitHub secrets). Two outages in its history looked identical from outside:

| Outage | What Databricks returns | Fix |
|---|---|---|
| Expired or revoked token (Aug 2026) | `403` `Invalid access token` at `OpenSession` | Rotate the Streamlit secret, then reboot the app |
| Free Edition compute block (Sep–Oct 2026, and again now) | `400` `BAD_REQUEST: Cannot create the resource` at `OpenSession` | None. It lifts on its own |

Streamlit Cloud redacts both to the same generic error, so the monitor can't tell them apart by reading the page. The Databricks freshness SQL Alert can't catch either one: it runs on the same warehouse, which is exactly what's down.

## Goals

- A check fails when the dashboard isn't serving data, and says why when the cause is known.
- The maintainer is alerted by GitHub's failed-workflow email, plus one GitHub issue per outage.
- Visitors see a plain status message instead of a stack trace.

Out of scope: a faster schedule (each check is real Free Edition warehouse load), phone or chat alerts, and monitoring the dbt CI token.

## Design

Three units with one shared vocabulary of status kinds:

| Kind | Raised by | Meaning |
|---|---|---|
| `token-rejected` | app | Databricks refused the token (`401`/`403`, "Invalid access token", "token expired") |
| `compute-blocked` | app | Databricks won't start compute ("Cannot create the resource", `DENY_NEW_AND_EXISTING_RESOURCES`, `resource-gatekeeper`) |
| `query-failed` | app | Any other warehouse or query error |
| `app-exception` | monitor | Streamlit showed an uncaught exception before any query ran |
| `no-content` | monitor | Nothing rendered before the deadline: a sleeping app that didn't wake, a Streamlit Cloud error page, or a timeout |

### 1. The app labels its own failures (`dashboard/status.py`, `dashboard/db.py`, `dashboard/app.py`)

- `status.py` is pure (no Streamlit import): `classify_error(exc) -> kind` reads the connector exception's message and its `context["http-code"]`. `MESSAGES[kind]` holds the public-safe sentence shown to visitors.
- `db.py`: the cached query moves to `_query()`, and `run_query()` wraps it. On any exception it logs the full error (still visible under Manage app → logs), renders the message inside `st.container(key=f"dashboard-status-{kind}")`, and calls `st.stop()`. Pages keep calling `run_query()` unchanged.
- `app.py`: after `st.navigation(...).run()`, it renders `st.container(key="dashboard-ready")` holding an empty `st.html` span. An empty keyed container isn't rendered, so it needs content. Because `st.stop()` and uncaught exceptions end the script before that line, the marker exists only when the page finished cleanly.
- Streamlit gives a keyed container the documented CSS class `st-key-<key>`. These classes are the contract between app and monitor, so the dashboard redesign must keep both keys.

### 2. The monitor reads the page (`.github/scripts/keepalive.py`)

- It loads `APP_URL` in headless Chromium and clicks the wake button if present. Then it polls every frame (the app renders inside an iframe at `/~/+/`) for `.st-key-dashboard-ready`, `[class*="st-key-dashboard-status-"]` or `[data-testid="stException"]`, for up to 4 minutes.
- `verdict(observation)` is pure:
  - a status marker means `down` with that kind
  - the ready marker means `ok`
  - an exception means `down` / `app-exception`
  - nothing means `down` / `no-content`
- If the verdict is down, it waits 2 minutes and checks once more on a fresh page, so a cold start or a one-off blip doesn't open a public issue. The second result stands.
- On `ok`, it stays on the page 10 seconds so Streamlit counts the visit, which is the old keep-alive behaviour.
- It writes `status` and `cause` to `$GITHUB_OUTPUT`. The script exits 0 on any verdict and non-zero only if the monitor itself breaks. That way a monitor bug fails the job (email) without opening an outage issue.

### 3. The outage issue (`.github/scripts/dashboard_issue.py`)

- It uses `gh` with the workflow's `GITHUB_TOKEN`. Issues are filed by `github-actions[bot]`.
- `decide(open_issue, last_cause, status, cause)` is pure and returns `open`, `comment`, `close` or `none`:
  - **down, no open issue:** open "Dashboard down: <cause label>", labelled `dashboard-down`. The body gives the cause, when it was first detected (UTC), a link to the run, and what the cause usually means.
  - **down, open issue, different cause:** comment "Cause changed: A → B" and retitle the issue.
  - **down, same cause:** nothing, so no comment every 6 hours.
  - **ok, open issue:** comment "Recovered after 1d 4h" (from the issue's creation time) and close it.
- The last recorded cause is kept in a hidden `<!-- cause: kind -->` marker in the issue body and comments.
- Issue text uses only the public-safe cause descriptions, never raw error output.
- `DRY_RUN=1` prints the write commands instead of running them, for local testing.

### Workflow (`.github/workflows/keepalive.yml`)

```
permissions: contents: read, issues: write
check (id: check)     → keepalive.py writes status/cause
issue (if check ran)  → dashboard_issue.py
fail (if status=down) → exit 1, so GitHub sends its failed-run email
```

The schedule stays every 6 hours, with `workflow_dispatch` for manual runs. Playwright gets pinned (`1.64.0`), and the job gets a 20-minute timeout. The README's Observability section gains one bullet for this outside-in check.

## Testing

- **Unit tests (pytest, local only, not in CI):** `classify_error` against the real exception messages captured on 2026-10-22, `verdict`, `decide`, and duration formatting.
- **End to end, locally:**
  - The monitor against the live app, which currently shows the uncaught error and should give `app-exception`.
  - The monitor against the branch's dashboard running locally, which should give `compute-blocked` while the block lasts, and `token-rejected` with a fake token.
  - The monitor against a stub page carrying `dashboard-ready`, which should give `ok`.
  - `dashboard_issue.py` with `DRY_RUN=1` for each decision.
- **Not testable before merge:** real issue creation and closing on GitHub, and the failure email. The first scheduled run after merge exercises them. The workflow can also be triggered by hand.

## Known limits

- **Schedule pausing:** GitHub pauses scheduled workflows in a public repo after 60 days without repository activity, and emails before it does. The monitor can't watch itself.
- **Up to 6 hours to detect:** that's the price of not adding warehouse load.
- **Opaque `no-content`:** it's a catch-all. The run log keeps the page's text for diagnosis, but the issue doesn't.
