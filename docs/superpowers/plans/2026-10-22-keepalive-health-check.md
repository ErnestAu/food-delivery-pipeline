# Keep-alive Health Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 6-hourly keep-alive fail, and open or close a GitHub issue, when the dashboard isn't serving data, naming the cause when it's known.

**Architecture:** The dashboard sorts its own warehouse failures into a status kind and renders a keyed marker. The Playwright monitor reads those markers, or their absence, from the page. A small `gh` script turns the verdict into one issue per outage.

**Tech Stack:** Streamlit (keyed containers → `st-key-*` classes), databricks-sql-connector 4.x, Playwright for Python 1.64.0, GitHub Actions + `gh`, pytest (local only).

**Spec:** `docs/superpowers/specs/2026-10-22-keepalive-health-check-design.md`

## Global Constraints

- Status kinds, exactly: `token-rejected`, `compute-blocked`, `query-failed` (app) and `app-exception`, `no-content` (monitor).
- Marker keys, exactly: `dashboard-ready` and `dashboard-status-<kind>` (rendered classes `st-key-dashboard-ready`, `st-key-dashboard-status-<kind>`).
- Issue label `dashboard-down`. Hidden cause marker `<!-- cause: <kind> -->`.
- Monitor timings: poll deadline 240 s, poll interval 5 s, retry once after 120 s, linger 10 s on `ok`.
- Playwright pinned to `1.64.0` in the workflow. Job timeout 20 minutes. Schedule unchanged: `0 */6 * * *` plus `workflow_dispatch`.
- Issue and page text use only the fixed copy in this plan, never raw exception text.
- Commits are one conventional-commit line with no body or trailer (see `AGENTS.md`).
- Tests live in `tests/` and run with `pytest` from the repo root. `tests/conftest.py` puts `dashboard/` and `.github/scripts/` on `sys.path`.

## Review Focus

- A failure without connector context (socket timeout, DNS error, plain `Exception`) must classify as `query-failed`, not crash the classifier. Pinned in Task 1.
- An open issue whose markers were edited away, so the last cause is unknown, must get a cause comment on the next failure, not silence. Pinned in Task 4.
- A frame that detaches mid-poll (Streamlit Cloud reloading the iframe while waking) must count as "nothing found yet", not crash the monitor. Pinned in Task 3.
- Running the monitor locally without `$GITHUB_OUTPUT` must print the result, not crash. Pinned in Task 3.
- Downtimes under an hour must read as minutes ("35m"), and GitHub's `Z`-suffixed timestamps must parse. Pinned in Task 4.

---

### Task 1: Status vocabulary and classifier

**Files:**
- Create: `dashboard/status.py`
- Create: `tests/conftest.py`, `tests/test_status.py`, `requirements-dev.txt` (`pytest>=8`)

**Interfaces:**
- Produces: `KINDS: tuple[str, ...]` (the three app kinds), `MESSAGES: dict[str, str]`, `classify_error(exc: BaseException) -> str`.

- [ ] **Step 1: Write the failing tests** in `tests/test_status.py`. Use a fake `RequestError(Exception)` with a `context` dict, so the tests don't need the connector:

```python
def test_rejected_token_is_token_rejected():
    exc = FakeRequestError("Error during request to server: : Invalid access token.. ", {"http-code": "403"})
    assert classify_error(exc) == "token-rejected"

def test_unauthorized_status_is_token_rejected():
    assert classify_error(FakeRequestError("Error during request to server", {"http-code": "401"})) == "token-rejected"

def test_quota_block_is_compute_blocked():
    msg = "Error during request to server: BAD_REQUEST: Cannot create the resource, please try again later.."
    assert classify_error(FakeRequestError(msg, {"http-code": "400"})) == "compute-blocked"

def test_gatekeeper_reason_is_compute_blocked():
    assert classify_error(Exception("denyReason INACTIVE reason DENY_NEW_AND_EXISTING_RESOURCES")) == "compute-blocked"

def test_error_without_context_is_query_failed():
    assert classify_error(TimeoutError("timed out")) == "query-failed"

def test_sql_error_is_query_failed():
    assert classify_error(Exception("[TABLE_OR_VIEW_NOT_FOUND] gold_dbt.fct_orders")) == "query-failed"

def test_every_kind_has_a_message():
    assert set(MESSAGES) == set(KINDS)
```

- [ ] **Step 2: Run** `pytest tests/test_status.py -v`. Expected: collection error (`status` doesn't exist yet).
- [ ] **Step 3: Implement `dashboard/status.py`.** No Streamlit import. Token checks run first: `context["http-code"]` in `{"401", "403"}`, or the message matches `invalid access token|token .*expired` (case-insensitive). Then compute: `cannot create the resource|DENY_NEW_AND_EXISTING_RESOURCES|resource-gatekeeper`. Anything else is `query-failed`. Use `getattr(exc, "context", None) or {}`. Copy for `MESSAGES`:
  - `token-rejected`: "Databricks rejected this dashboard's access token, so it can't query the warehouse until the token is rotated."
  - `compute-blocked`: "Databricks has paused compute for this Free Edition workspace, so live data is back once the workspace is reactivated."
  - `query-failed`: "A warehouse query failed. The full error is in the app logs."
- [ ] **Step 4: Run** `pytest tests/test_status.py -v`. Expected: 7 passed.
- [ ] **Step 5: Commit:** `feat: classify dashboard warehouse failures into status kinds`

### Task 2: Dashboard renders status and ready markers

**Files:**
- Modify: `dashboard/db.py` (wrap `run_query`), `dashboard/app.py` (ready marker after `.run()`)

**Interfaces:**
- Consumes: `classify_error`, `MESSAGES` (Task 1).
- Produces: the DOM contract. `.st-key-dashboard-status-<kind>` when a query fails. `.st-key-dashboard-ready` only when the page finished. `run_query(query: str, params: dict | None = None) -> pd.DataFrame` keeps its signature.

- [ ] **Step 1: Split `db.py`.** The current cached body becomes `_query(query, params)` under `@st.cache_data(ttl=300)`. `run_query` calls it inside `try`. On `Exception` it calls `logging.getLogger(__name__).exception(...)` with the kind, then `show_status(kind)`.
- [ ] **Step 2: Add `show_status(kind: str) -> NoReturn`** in `db.py`. It renders `st.warning(f"**Live data is unavailable right now.** {MESSAGES[kind]}")` inside `st.container(key=f"dashboard-status-{kind}")`, then calls `st.stop()`.
- [ ] **Step 3: Add the ready marker** at the end of `app.py`: `st.container(key="dashboard-ready")` holding `st.html("<span></span>")`, with a one-line comment saying the keep-alive reads it.
- [ ] **Step 4: Verify locally.** Run the branch's dashboard (`streamlit run dashboard/app.py --server.port 8502`) and check the page:
  - **While the compute block lasts:** the warning shows, the page has `.st-key-dashboard-status-compute-blocked`, and it has no `.st-key-dashboard-ready`.
  - **With `DATABRICKS_TOKEN=dapi000…` set in the environment:** the page has `.st-key-dashboard-status-token-rejected`.
- [ ] **Step 5: Commit:** `feat: show a status marker instead of a stack trace when the warehouse fails`

### Task 3: Monitor reads the page

**Files:**
- Modify: `.github/scripts/keepalive.py` (rewrite)
- Create: `tests/test_keepalive.py`

**Interfaces:**
- Produces: `Observation(ready: bool, status: str | None, exception: bool, wake_button: bool)` (dataclass), `observe(frames: Iterable) -> Observation`, `verdict(obs: Observation) -> tuple[str, str]` (`("ok", "")` or `("down", kind)`), `write_outputs(status: str, cause: str, path: str | None) -> None`, `check(url: str) -> tuple[str, str]`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_status_marker_wins():
    assert verdict(Observation(ready=False, status="compute-blocked", exception=False, wake_button=False)) == ("down", "compute-blocked")

def test_ready_is_ok():
    assert verdict(Observation(ready=True, status=None, exception=False, wake_button=False)) == ("ok", "")

def test_exception_without_marker_is_app_exception():
    assert verdict(Observation(ready=False, status=None, exception=True, wake_button=False)) == ("down", "app-exception")

def test_nothing_is_no_content():
    assert verdict(Observation(ready=False, status=None, exception=False, wake_button=True)) == ("down", "no-content")

def test_observe_reads_status_kind_from_class(): ...
    # fake frame whose locator("[class*='st-key-dashboard-status-']") has count 1 and get_attribute("class") returns
    # "stVerticalBlock st-key-dashboard-status-token-rejected e1x" -> Observation.status == "token-rejected"

def test_observe_survives_detached_frame(): ...
    # fake frame whose locator().count() raises playwright.sync_api.Error -> Observation(False, None, False, False)

def test_write_outputs_appends_to_file(tmp_path):
    out = tmp_path / "out"
    write_outputs("down", "no-content", str(out))
    assert out.read_text() == "status=down\ncause=no-content\n"

def test_write_outputs_without_path_prints(capsys):
    write_outputs("ok", "", None)
    assert "status=ok" in capsys.readouterr().out
```

- [ ] **Step 2: Run** `pytest tests/test_keepalive.py -v`. Expected: fails on import.
- [ ] **Step 3: Implement.** Import Playwright inside `check()` and `observe()` only, so `verdict` and `write_outputs` import without it. `observe` treats any exception from a frame as "not found". The kind is the class token after `st-key-dashboard-status-`. `check(url)` does one attempt:
  1. Navigate, then click the wake button whenever it shows.
  2. Poll `observe(page.frames)` every 5 s until `ready`, `status` or `exception` is set, or 240 s pass.
  3. On a down verdict, print the frame's visible text (≤ 2,000 chars) to the log. On ok, linger 10 s.

  `main()` runs `check`, waits 120 s and runs `check` once more if the first is down, then calls `write_outputs(status, cause, os.environ.get("GITHUB_OUTPUT"))`. It exits 0 unless an exception escapes.
- [ ] **Step 4: Run** `pytest tests/test_keepalive.py -v`. Expected: 8 passed.
- [ ] **Step 5: Verify end to end** (scratch Playwright venv):
  - `APP_URL=https://ernestau-food-delivery-ops.streamlit.app` should give `status=down`, `cause=app-exception`, since the live app still runs the old code.
  - `APP_URL=http://localhost:8502` (Task 2's local run) should give `cause=compute-blocked`.
  - A stub page that renders `dashboard-ready` should give `status=ok`.
- [ ] **Step 6: Commit:** `feat: make the keep-alive read dashboard status from the page`

### Task 4: Outage issue

**Files:**
- Create: `.github/scripts/dashboard_issue.py`, `tests/test_dashboard_issue.py`

**Interfaces:**
- Consumes: the kinds from Global Constraints. Env `STATUS`, `CAUSE`, `APP_URL`, `RUN_URL`, `GH_TOKEN`, optional `DRY_RUN`.
- Produces: `CAUSES: dict[str, tuple[str, str]]` (kind → (label, meaning)), `last_cause(texts: list[str]) -> str | None`, `decide(open_issue: bool, last: str | None, status: str, cause: str) -> str`, `format_duration(start: datetime, end: datetime) -> str`, `issue_body(cause: str, app_url: str, run_url: str, now: datetime) -> str`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_first_failure_opens():            assert decide(False, None, "down", "compute-blocked") == "open"
def test_same_cause_stays_quiet():         assert decide(True, "compute-blocked", "down", "compute-blocked") == "none"
def test_new_cause_comments():             assert decide(True, "compute-blocked", "down", "token-rejected") == "comment"
def test_unknown_last_cause_comments():    assert decide(True, None, "down", "no-content") == "comment"
def test_recovery_closes():                assert decide(True, "token-rejected", "ok", "") == "close"
def test_healthy_without_issue_is_quiet(): assert decide(False, None, "ok", "") == "none"

def test_last_marker_wins():
    assert last_cause(["body <!-- cause: compute-blocked -->", "x", "<!-- cause: token-rejected -->"]) == "token-rejected"

def test_no_marker_is_none():
    assert last_cause(["edited body"]) is None

def test_duration_days_hours():
    assert format_duration(parse_ts("2026-10-20T06:00:00Z"), parse_ts("2026-10-21T10:30:00Z")) == "1d 4h"

def test_duration_minutes():
    assert format_duration(parse_ts("2026-10-21T10:00:00Z"), parse_ts("2026-10-21T10:35:00Z")) == "35m"

def test_body_carries_cause_marker_and_links():
    body = issue_body("compute-blocked", "https://app", "https://run", parse_ts("2026-10-22T06:00:00Z"))
    assert "<!-- cause: compute-blocked -->" in body and "https://app" in body and "https://run" in body
    assert "2026-10-22 06:00 UTC" in body

def test_every_kind_has_copy():
    assert set(CAUSES) == {"token-rejected", "compute-blocked", "query-failed", "app-exception", "no-content"}
```

- [ ] **Step 2: Run** `pytest tests/test_dashboard_issue.py -v`. Expected: fails on import.
- [ ] **Step 3: Implement.** Add a `parse_ts(s) -> datetime` helper for GitHub ISO strings with a trailing `Z`. `format_duration` returns `"{d}d {h}h"` when the downtime is at least a day, `"{h}h {m}m"` at least an hour, otherwise `"{m}m"`. `main()`:
  1. `gh label create dashboard-down --color B60205 --description "Opened and closed by the keep-alive health check" --force`
  2. `gh issue list --label dashboard-down --state open --json number,body,createdAt,comments --limit 1`, then `decide`.
  3. **open:** `gh issue create --title "Dashboard down: <label>" --label dashboard-down --body <issue_body>`
  4. **comment:** `gh issue comment N --body "Cause changed: <old label> → <new label>. <meaning> ([check run](RUN_URL)) <!-- cause: kind -->"`, then `gh issue edit N --title "Dashboard down: <new label>"`
  5. **close:** `gh issue close N --comment "Recovered: the check passed at <now> UTC, <duration> after this outage was first detected."`

  With `DRY_RUN` set, write commands (`label create`, `create`, `comment`, `edit`, `close`) are printed instead of run, while the `list` read still runs. Copy for `CAUSES`:
  - `token-rejected`: "Databricks token rejected" / "Databricks refused the dashboard's access token: it has expired or been revoked. Rotate `DATABRICKS_TOKEN` in Streamlit Cloud secrets, then reboot the app (the token is read at import)."
  - `compute-blocked`: "Databricks compute blocked" / "Databricks won't start compute for the workspace: Free Edition marks idle workspaces inactive, and token traffic doesn't count as activity. Log in to the workspace and start the warehouse; rotating the token doesn't help."
  - `query-failed`: "Warehouse query failed" / "The warehouse accepted the connection but a query failed. The full error is in the Streamlit Cloud app logs."
  - `app-exception`: "App error" / "The app raised an uncaught exception before reaching the warehouse. The full error is in the Streamlit Cloud app logs."
  - `no-content`: "Dashboard not rendering" / "The page never rendered dashboard content: an app that didn't wake, a Streamlit Cloud error page, or a timeout. The check run's log has the page text."

  `issue_body` layout: one sentence linking the dashboard, then bullets for **Cause** (label), **First detected** (`YYYY-MM-DD HH:MM UTC`) and **Check run** (link), then the meaning, then "This issue closes itself when a check passes.", then the hidden marker.
- [ ] **Step 4: Run** `pytest tests/test_dashboard_issue.py -v`. Expected: 12 passed.
- [ ] **Step 5: Verify:** `DRY_RUN=1 STATUS=down CAUSE=compute-blocked APP_URL=https://ernestau-food-delivery-ops.streamlit.app RUN_URL=https://example.invalid/run python .github/scripts/dashboard_issue.py` prints a `gh issue create …` line and nothing is written to GitHub. Then `STATUS=ok` prints `nothing to do`.
- [ ] **Step 6: Commit:** `feat: open and close one GitHub issue per dashboard outage`

### Task 5: Workflow and README

**Files:**
- Modify: `.github/workflows/keepalive.yml`, `README.md` (Observability bullet)

**Interfaces:**
- Consumes: `keepalive.py` outputs `status` and `cause` (Task 3). `dashboard_issue.py` env (Task 4).

- [ ] **Step 1: Rewrite the workflow:**
  - **Header:** `name: Keep-alive & health check`, `permissions: {contents: read, issues: write}`, a `concurrency: keepalive` group without cancel, and `timeout-minutes: 20`.
  - **Steps:** checkout → setup-python 3.11 → `pip install playwright==1.64.0` + `playwright install --with-deps chromium` → `id: check` (`APP_URL` env) → issue step (`if: steps.check.outcome == 'success'`, env `GH_TOKEN: ${{ github.token }}`, `STATUS`/`CAUSE` from outputs, `APP_URL`, `RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}`) → fail step (`if: steps.check.outputs.status == 'down'`: `echo "::error::Dashboard down: ${{ steps.check.outputs.cause }}"; exit 1`).
- [ ] **Step 2: Verify the workflow parses:** `python -c "import yaml; yaml.safe_load(open('.github/workflows/keepalive.yml'))"`. Then check by eye that every `steps.check.outputs.*` name matches `write_outputs`.
- [ ] **Step 3: Add the README bullet** under Observability, after the SQL Alert bullet:
  - **Bold lead-in:** "Watch from the outside".
  - **Content:** the 6-hourly keep-alive reads what the page actually shows and files one `dashboard-down` issue per outage, naming the cause (token rejected / compute blocked / …).
  - **Why it's needed:** it's the check that still works when the warehouse itself is down, which is the one condition the SQL Alert can't see.
- [ ] **Step 4: Run the whole suite:** `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit:** `feat: fail the keep-alive and track outages as issues when the dashboard is down`
