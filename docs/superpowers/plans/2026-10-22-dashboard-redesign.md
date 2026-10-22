# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Streamlit dashboard as a three-page app with an Overview landing page, using Apple HIG principles, so a one-minute reader sees a live, observable pipeline.

**Architecture:**
- Theme tokens live in `.streamlit/config.toml` (light and dark).
- Our own HTML pieces (status pill, flow diagram, tiles) come from pure builders in `dashboard/ui.py`, styled by the single stylesheet `dashboard/style.css`.
- Data comes from cached query functions in `dashboard/queries.py`, shared by Overview and Pipeline health.
- Pure logic (freshness, reconciliation, HTML) is unit-tested. Pages are smoke-tested with Streamlit's `AppTest` against a fake `run_query`.

**Tech Stack:** Streamlit 1.66 (`st.navigation(position="top")`, `[theme.light]`/`[theme.dark]`, `chart*Colors`), Plotly with `theme="streamlit"`, databricks-sql-connector, pytest.

**Spec:** `docs/superpowers/specs/2026-10-22-dashboard-redesign-design.md`

## Global Constraints

- **Pin:** `streamlit==1.66.*` in `requirements.txt`. The local run venv is `/Users/ernestau/venvs/food-delivery`.
- **Keep-alive contract unchanged:** `dashboard-ready` (rendered in `app.py` after `.run()`) and `dashboard-status-<kind>` (in `db.show_status`).
- **Visible text:** no emoji or `st.divider()`. Sentence case in every heading and label. At most one line of supporting text per section.
- **Pages, in nav order:** Overview (`overview.py`, default), Pipeline health (`pipeline_health.py`), Operations (`operations.py`).
- **Freshness states** (`dashboard/freshness.py`, used by the pill and every freshness tile):
  - `live` under 180 min, `delayed` under 2,880 min, `stale` otherwise, `unknown` when there's no timestamp.
  - Labels: "Live", "Delayed", "Stale", "No data".
- **Status colors** (dataviz fixed set, always next to a word): live `#0ca30c`, delayed `#fab219`, stale `#d03b3b`, unknown `#8e8e93`.
- **Theme tokens:**

  | Token | Light | Dark |
  |---|---|---|
  | background | `#FFFFFF` | `#000000` |
  | secondary background | `#F2F2F7` | `#1C1C1E` |
  | text | `#1D1D1F` | `#F5F5F7` |
  | border | `#D2D2D7` | `#38383A` |
  | primary | `#007AFF` | `#0A84FF` |
  | link | `#0066CC` | `#0A84FF` |
- **Categorical palette** (validated 2026-10-22, all five checks passing):
  - Light `["#007AFF", "#FF2D55", "#AF52DE", "#1A9AB0"]` on `#FFFFFF`.
  - Dark `["#0A84FF", "#FF375F", "#BF5AF2", "#1A9AB0"]` on `#000000`.
  - Assigned in fixed order by entity: delivered → slot 1, cancelled → slot 2. Cancellation actors in the order customer, vendor, driver, system → slots 1–4.
- **Sequential ramp:** the dataviz blue steps `#cde2fb #b7d3f6 #9ec5f4 #86b6ef #6da7ec #3987e5 #2a78d6 #256abf #184f95 #0d366b`, light to dark. Dark mode uses the same list reversed.
- **Type:**

  | Text | Size / weight |
  |---|---|
  | Base | 15 px |
  | Page title | 2.125rem / 700 |
  | Section | 1.375rem / 600 |
  | Headline | 1.0625rem / 600 |

  Metrics use tabular figures. The font is the system stack `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif`.
- **CSS:** all in `dashboard/style.css`. Neutral surfaces use `color-mix(in srgb, currentColor N%, transparent)` so the same rules work in both modes. Any rule that targets a Streamlit `data-testid` carries a comment naming why.
- **Commits:** one conventional-commit line, no body or trailer. Never mention the agent tooling in messages; vendored-skill commits say "Apple HIG skills".
- **Tests:** run from the repo root with the scratch venv's pytest (Python 3.11, Streamlit 1.66, Plotly, connector).

## Review Focus

- **Empty or missing data** (fresh deploy, an empty layer, a NULL timestamp): tiles and the flow must show "—" / "No data", not crash. Pinned in Task 3 (`freshness_state(None)`, flow node with `rows=None`).
- **Naive vs. tz-aware timestamps from Databricks:** minutes-since must treat naive values as UTC. Pinned in Task 3.
- **Text in HTML builders** (vendor names, reasons, any query string): it must be escaped. Pinned in Task 3.
- **A deselected `st.segmented_control`** returns `None`: every control falls back to its default. Pinned by the Task 6 smoke test.
- **Phone width (390 px):** the flow diagram stacks vertically with no horizontal page scroll. Checked in Task 7 screenshots.

---

### Task 1: Vendor the Apple HIG skills

**Files:**
- Create: `.claude/skills/hig-{foundations,components-layout,components-content,components-status,patterns}/SKILL.md`, `.claude/skills/LICENSE`, `.claude/skills/VENDORED.md`, `.claude/apple-design-context.md`
- Modify: `.gitignore`

- [ ] **Step 1: Copy the files.** The five `SKILL.md` files and `LICENSE` come from raintree-technology/apple-hig-skills at `fdc35993d580730a60b827ed39adc6c9991ade41`. The matching `references/` folders also go in, locally only.
- [ ] **Step 2: `.gitignore`.** Replace the `.claude/` line with these four lines:
  ```
  .claude/*
  !.claude/skills/
  !.claude/apple-design-context.md
  .claude/skills/*/references/
  ```
- [ ] **Step 3: Write `VENDORED.md` and `apple-design-context.md`.**
  - `VENDORED.md`: the source repo, the commit, that `SKILL.md` and `LICENSE` are MIT (© Raintree Technology), and that `references/` is © Apple Inc., kept local and gitignored, and how to fetch it.
  - `apple-design-context.md`:
    - Platform: web, Streamlit 1.66.
    - Audience: a hiring manager or DE interviewer on a one-minute read.
    - Light and dark modes. Accessibility target: WCAG AA.
    - Pointers to the spec and to `dashboard/style.css`.
- [ ] **Step 4: Verify.** `git status --short` lists only the 9 intended paths, and `git check-ignore .claude/skills/hig-foundations/references/color.md` prints the path.
- [ ] **Step 5: Commit:** `chore: vendor Apple HIG skills for the dashboard redesign`

### Task 2: Theme, stylesheet, top navigation

**Files:**
- Create: `.streamlit/config.toml`, `dashboard/style.css`, `dashboard/ui.py` (just `inject_css()` for now), `tests/test_pages.py`
- Modify: `requirements.txt`, `dashboard/app.py`

**Interfaces:**
- Produces: `ui.inject_css() -> None`, which reads `style.css` next to it and renders it once with `st.html("<style>…</style>")`. Also the `fake_run_query` fixture in `tests/test_pages.py` (dispatches on SQL keywords to return small DataFrames), reused by Tasks 4–6.

- [ ] **Step 1: Write the failing smoke test** `test_app_renders_without_exception`:
  - Set the three `DATABRICKS_*` env vars to dummies, and monkeypatch `db.run_query` to `fake_run_query`.
  - Run `AppTest.from_file("dashboard/app.py", default_timeout=30).run()`.
  - Assert `not at.exception` and that no `st-key-dashboard-status-` marker was rendered.

  Run it. Expected: FAIL. The fake doesn't serve today's queries yet, which proves the harness reaches the pages.
- [ ] **Step 2: Build `fake_run_query`** so today's pages render. Expected: PASS against the current pages.
- [ ] **Step 3: Pin and upgrade.** Set `streamlit==1.66.*` in `requirements.txt` and `pip install "streamlit==1.66.*"` into the run venv.
- [ ] **Step 4: Write `.streamlit/config.toml`.**
  - `[client] toolbarMode = "minimal"`.
  - `[theme]`: font, heading sizes and weights, `baseFontSize = 15`, `baseRadius = "10px"`, metric value size `1.75rem` / 600, `showWidgetBorder = false`.
  - `[theme.light]` and `[theme.dark]` hold the Global Constraints tokens plus `chartCategoricalColors`, `chartSequentialColors`, and green/orange/red/yellow set to the status colors.
- [ ] **Step 5: Write the stylesheet and the app shell.**
  - `style.css`:
    - Main block max-width 1200 px.
    - Tabular-nums on metric values.
    - The `.fd-*` component classes Tasks 3–6 use: pill, flow, node, arrow, tile, tiles grid, defs, section lede.
    - A single-column flow below 760 px.
  - `app.py`:
    - `set_page_config(page_title="Food Delivery Pipeline", layout="wide")` with no page icon emoji.
    - `inject_css()`.
    - `st.navigation(position="top")` over the existing pages, with titles "Pipeline health" and "Operations" and no icons.
    - Keep the ready marker.
- [ ] **Step 6: Verify in the browser.** Run the app locally (launch config `dr-dashboard`, port 8504) and check:
  - Nav is in the top bar.
  - Computed `font-family` on body starts with `-apple-system`. If Streamlit rejects the stack, use `fontFaces`/`font = "sans-serif"` and set the stack in CSS, and record that in the ledger.
  - Plotly charts take `chartCategoricalColors`. If they don't, Tasks 5–6 set colors from `ui.palette()` keyed on `st.context.theme.type`, and that gets ledgered.
- [ ] **Step 7: Run** `pytest -q`. Expected: all pass. **Commit:** `feat: apply HIG theme tokens, shared stylesheet and top navigation`

### Task 3: Pure helpers

**Files:**
- Create: `dashboard/freshness.py`, `tests/test_freshness.py`, `tests/test_ui.py`, `tests/test_reconcile.py`
- Modify: `dashboard/ui.py`
- Create: `dashboard/queries.py` (only `reconcile` in this task)

**Interfaces:**
- Produces:
  - **`freshness.py`:** `minutes_since(ts, now: datetime) -> float | None`, `freshness_state(minutes: float | None) -> str`, `humanize(minutes: float | None) -> str`. `humanize` gives `"—"` for None, `"just now"` under 1 min, else `"12 min"`, `"3 h 5 min"` or `"2 d 4 h"`.
  - **`ui.py`:**
    - `Node(name: str, tech: str, rows: int | None, updated: str)` (dataclass).
    - `status_pill(state: str, text: str) -> str`.
    - `tile(label: str, value: str, note: str = "", state: str | None = None) -> str`.
    - `tiles(items: list[str]) -> str`.
    - `flow(nodes: list[Node]) -> str`.
    - `defs(items: list[tuple[str, str]]) -> str`.
    - `palette() -> dict`.
  - **`queries.py`:** `reconcile(counts: dict[str, int | None]) -> list[dict]`, with rows `{"layer", "rows", "dropped", "dropped_pct", "why"}` for bronze, silver, gold.

- [ ] **Step 1: Write the failing tests.**

```python
def test_states_follow_thresholds():
    assert [freshness_state(m) for m in (0, 179, 180, 2879, 2880, None)] == ["live", "live", "delayed", "delayed", "stale", "unknown"]

def test_humanize():
    assert [humanize(m) for m in (None, 0.5, 12, 185, 3120)] == ["—", "just now", "12 min", "3 h 5 min", "2 d 4 h"]

def test_naive_timestamps_are_utc():
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    assert minutes_since(pd.Timestamp("2026-10-22 11:00:00"), now) == 60
    assert minutes_since(None, now) is None

def test_pill_pairs_color_with_label():
    html = status_pill("delayed", "Delayed · last order 4 h ago")
    assert 'fd-pill--delayed' in html and "Delayed · last order 4 h ago" in html

def test_builders_escape_text():
    assert "<script>" not in tile("<script>", "1") and "&lt;script&gt;" in tile("<script>", "1")

def test_flow_shows_dash_for_missing_rows():
    html = flow([Node("Bronze", "Auto Loader", None, "—")])
    assert "—" in html and "None" not in html

def test_flow_formats_counts():
    assert "758,512" in flow([Node("Bronze", "Auto Loader", 758512, "1 h ago")])

def test_reconcile_drops():
    rows = reconcile({"bronze": 758512, "silver": 727208, "gold": 727208})
    assert rows[1]["dropped"] == 31304 and round(rows[1]["dropped_pct"], 1) == 4.1
    assert rows[2]["dropped"] == 0 and rows[0]["dropped"] is None

def test_reconcile_missing_layer():
    assert reconcile({"bronze": None, "silver": 5, "gold": 5})[1]["dropped"] is None
```

- [ ] **Step 2: Run** `pytest tests/test_freshness.py tests/test_ui.py tests/test_reconcile.py -q`. Expected: import errors.
- [ ] **Step 3: Implement.** Everything goes through `html.escape`. Each pill has a dot `<span>` plus a text `<span>`. Reconciliation `why` copy:
  - bronze: "Raw events as landed by Auto Loader"
  - silver: "Duplicates removed on event ID; events more than an hour late dropped by the watermark"
  - gold: "Modeled by dbt; expected to match silver"
- [ ] **Step 4: Run** `pytest -q`. Expected: all pass. **Commit:** `feat: add freshness, reconciliation and HTML helpers for the dashboard`

### Task 4: Shared queries and the Overview page

**Files:**
- Modify: `dashboard/queries.py`, `dashboard/app.py`, `tests/test_pages.py`
- Create: `dashboard/overview.py`

**Interfaces:**
- Consumes: Task 3 helpers, `db.run_query`.
- Produces (all through `run_query`, so they're cached and status-marked on failure):
  - `layer_stats() -> pd.DataFrame` with columns `layer, row_count, last_event_at`. Bronze uses `max(try_cast(occurred_at AS TIMESTAMP))`.
  - `last_pipeline_run() -> pd.Timestamp | None`, from the latest `DESCRIBE HISTORY` of silver.
  - `known_issues() -> pd.Series` with `negative_gmv, unknown_event_types, orphan_vendors` (today's SQL).
  - `gold_model_count() -> int`, from `information_schema.tables` where `table_schema = 'gold_dbt'`.

- [ ] **Step 1: Write the failing test** `test_overview_renders`. Run `AppTest` on `app.py` with the fake serving the four queries. Assert:
  - no exception;
  - the page title "Food Delivery Pipeline" is present;
  - the HTML contains `fd-pill--live` when the fake gold timestamp is 10 minutes old.

  Run. Expected: FAIL (no Overview page).
- [ ] **Step 2: Implement `overview.py`, top to bottom:**
  - **Header row:** title in a wide column; the pill in a narrow right column (label plus "last order X ago").
  - **Lede:** the spec's one sentence.
  - **Flow:** `flow()` with five nodes:

    | Node | Tech | Rows / updated |
    |---|---|---|
    | Source | "Simulator, hourly → S3" | no rows |
    | Bronze | "Auto Loader" | rows + updated |
    | Silver | "Dedup + watermark" | rows + updated |
    | Gold | `f"dbt · {gold_model_count()} models"` | rows + updated |
    | Serving | "This dashboard" | — |
  - **"At a glance":** `tiles()` with freshness, pipeline last run, and "Known data issues" (sum of the three counts, note "tracked, not hidden"), followed by `st.page_link("pipeline_health.py", label="Pipeline health")`.
  - **"How it's built":** `defs()` with five pairs:
    - Ingestion: "Auto Loader batch every hour; streaming would be over-engineering at this cadence."
    - Processing: "Lakeflow SDP in PySpark: deduplicated on event ID, one-hour watermark for late events."
    - Modeling: "Gold modeled in dbt; tests fail the build in CI and warn in production."
    - Orchestration: "One Databricks job: the SDP pipeline, then dbt run and test, every hour."
    - Observability: "Freshness alert, job-failure emails, and an outside-in health check that files an issue per outage."
  - **Footer links:** `st.page_link` to Pipeline health and Operations, plus the GitHub repo URL `https://github.com/ErnestAu/food-delivery-pipeline`.
  - Register it as the default first page in `app.py`.
- [ ] **Step 3: Run** `pytest -q`. Expected: all pass. Then look at it in the browser (port 8504) at desktop width.
- [ ] **Step 4: Commit:** `feat: add an overview landing page with a live medallion flow`

### Task 5: Pipeline health

**Files:**
- Modify: `dashboard/pipeline_health.py`, `tests/test_pages.py`

**Interfaces:**
- Consumes: `queries.layer_stats/last_pipeline_run/known_issues/reconcile`, `freshness.*`, `ui.tile/tiles`.

- [ ] **Step 1: Write the failing test** `test_pipeline_health_renders`: switch to the page and assert no exception and that "Layer reconciliation" is present. Run. Expected: FAIL (the old headings).
- [ ] **Step 2: Rewrite the page.** Title "Pipeline health". Drop the sidebar, emoji, captions and dividers. Sections, in order:
  - **Freshness:** `tiles()` with three state tiles.
  - **Volume against the 7-day baseline:**
    - One sentence: "Orders per hour; the dashed line is the average for that hour over the previous seven days."
    - The segmented window control stays: default 72h, falling back on None.
    - Bars in slot 1; the baseline as a dashed `#8e8e93` line.
    - No in-plot title, with recessive grid and hover.
  - **Known issues, tracked not hidden:** three tiles, each with a root-cause note:
    - "Uncapped ¥500 discount on small orders"
    - "Simulator events outside the agreed contract"
    - "Dimension IDs regenerated outside the warehouse"
  - **Layer reconciliation:** `st.dataframe(reconcile(...))` with formatted columns Layer, Rows, Dropped, Dropped %, Why. It replaces the funnel.
- [ ] **Step 3: Run** `pytest -q`. Expected: all pass. Check it in the browser.
- [ ] **Step 4: Commit:** `feat: restyle pipeline health and replace the funnel with a reconciliation table`

### Task 6: Operations

**Files:**
- Rename: `dashboard/food_delivery_ops.py` → `dashboard/operations.py` (`git mv`)
- Modify: `dashboard/operations.py`, `dashboard/app.py`, `tests/test_pages.py`

- [ ] **Step 1: Write the failing test** `test_operations_renders`: switch to `operations.py` and assert no exception, plus subheaders exactly `["Trend", "When orders arrive", "Top vendors", "Cancellations"]`. Run. Expected: FAIL (file missing).
- [ ] **Step 2: `git mv` the file, then rewrite it to the spec's keep list:**
  - **Header controls:** title "Operations" and the range segmented control `7d / 30d / 90d / All`, default 30d, falling back on None. The range ends at the last complete day, as today.
  - **KPI row:** orders, GMV, average order value, cancellation rate.
  - **Trend:** a metric segmented control "Orders / GMV / Cancellation rate / Delivery time".
    - Orders: stacked daily bars, delivered in slot 1 and cancelled in slot 2.
    - The others: a single-series line.
  - **When orders arrive:** the weekday × hour heatmap with the sequential ramp, keeping the today-last row order.
  - **Top vendors:** top 10, with columns Vendor, Cuisine, Orders, GMV, Cancel rate, using `column_config` number formats.
  - **Cancellations:**
    - Horizontal bars of reasons, grouped by actor in the fixed order customer, vendor, driver, system, colored slots 1–4, with a legend.
    - Counts shown as text on the bars (the CVD secondary channel).
  - **Delete:** the cuisine chart, the lifecycle chart, the donut, the debug expander, and the sidebar.
- [ ] **Step 3: Run** `pytest -q`. Expected: all pass. Check in the browser that every control works, including deselecting.
- [ ] **Step 4: Commit:** `feat: trim operations to five views with one shared date range`

### Task 7: Verify and document

**Files:**
- Replace: `docs/dashboard-*.png` (delete the 3 old ones; add `docs/dashboard-overview.png`, `docs/dashboard-pipeline-health.png`, `docs/dashboard-operations.png`)
- Modify: `README.md` (screenshot references, "Dashboard" run section, project layout tree)

- [ ] **Step 1: Run the monitor against the local app:** `APP_URL=http://localhost:8504 python .github/scripts/keepalive.py`. Expected: `status=ok`.
- [ ] **Step 2: Take screenshots** of all three pages: light and dark at 1280 px wide, plus light at 390 px. Check each:
  - no overflow or label collisions;
  - the flow stacks on mobile;
  - the status pill reads correctly.

  Fix anything found, with a ledger ruling.
- [ ] **Step 3: Save the three light-mode desktop screenshots** to `docs/` and update the README references and text.
- [ ] **Step 4: Run** `pytest -q`. **Commit:** `docs: refresh dashboard screenshots and README for the redesign`
