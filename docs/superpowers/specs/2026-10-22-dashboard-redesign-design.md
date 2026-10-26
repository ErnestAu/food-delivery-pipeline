# Dashboard redesign: design

**Date:** 2026-10-22 · **Branch:** `feat/dashboard-redesign` (stacked on `fix/keepalive-health-check`) · **Status:** draft, waiting on the maintainer's approval

## Purpose

**Reader:** a hiring manager or data-engineering interviewer who opens the link from a CV or the README and gives it about a minute. The dashboard's first job is to show a real, live, observable pipeline. Analysis comes second.

**What's wrong today:**
- Every section carries an emoji header, a caption and a divider.
- It looks like default Streamlit.
- The app opens on Pipeline Health without saying what the project is.

## Structure

Top navigation (`st.navigation(position="top")`), with no sidebar and three pages:

| Page | Role | Default |
|---|---|---|
| **Overview** (new) | What this is, how data flows, proof it's live | yes |
| **Pipeline health** | Deep dive: freshness, volume, data quality, layer reconciliation | |
| **Operations** (renamed from Food Delivery Ops) | Deep dive: the business view of gold | |

### Overview

```
Food Delivery Pipeline                                     ● Live · last order 12 min ago
A simulated food-delivery marketplace, streamed through a medallion lakehouse on
Databricks, modeled and tested with dbt, monitored end to end.

  Source          Bronze             Silver               Gold               Serving
  Simulator  ──▶  Auto Loader   ──▶  dedup + watermark ──▶ dbt · 8 models ──▶ this dashboard
  hourly → S3     758,512 events     727,208 events       727,208 events
                  updated 1 h ago    updated 1 h ago      updated 1 h ago

  Freshness          Last pipeline run      Known data issues
  12 min             1 h ago                3 tracked, not hidden          → Pipeline health

  How it's built      five one-line decisions (ingestion, processing, modeling and
                      tests, orchestration, observability), each with its reason

  Pipeline health →        Operations →        Source on GitHub →
```

- **Status pill:**
  - **Live** (green) when gold's newest event is under 3 hours old, the same threshold as the SQL Alert.
  - **Delayed** (orange) from 3 hours to 2 days.
  - **Stale** (red) beyond 2 days.

  Each state is a word plus a dot, never color alone.
- **Flow diagram:** live row counts and freshness per layer. It reuses the cached queries Pipeline health already runs, so the landing page adds almost no warehouse load. The gold model count comes from `information_schema`.
- **"How it's built":** taken from the README's design-decisions table, one line each.

### Pipeline health: keep all four sections, restyle

1. **Freshness:** three tiles (pipeline last run, silver, gold). Each shows its state as a word next to the value, using the same thresholds as the pill.
2. **Volume vs. baseline:** unchanged logic. Bars in one hue, the 7-day same-hour baseline as a neutral dashed line, and the window control kept.
3. **Known issues, tracked not hidden:** the three counts, each with one line on its root cause (uncapped discount, non-deterministic dimension IDs, unannounced event types).
4. **Layer reconciliation:** replaces the three-bar funnel. A compact table of rows per layer, rows dropped versus the previous layer (count and %), and why rows drop (deduplication, late-event watermark).

### Operations: trim to five pieces, no new analysis

| Keep | Cut |
|---|---|
| KPI row: orders, GMV, average order value, cancellation rate | GMV by cuisine bar chart |
| One trend chart with a metric switch: orders by status / GMV / cancellation rate / delivery time | Lifecycle stage-minutes area chart |
| Weekday × hour heatmap | "Who cancels?" donut (folded into reasons) |
| Top 10 vendors table (vendor, cuisine, orders, GMV, cancel rate) | Raw-data debug expander |
| Top cancellation reasons, colored by who cancelled | Sidebar preset buttons, "data available" and cache captions |

The date range becomes one segmented control (7d / 30d / 90d / All) above the charts.

## Visual system (HIG principles, adapted for the web)

- **Content over chrome:** no emoji or dividers. Sections are separated by space and headings, with at most one line of supporting text, and only when it adds information.
- **Type:** the system font stack (SF Pro on Apple devices). Sizes:

  | Text | Size / weight |
  |---|---|
  | Page title | 34 bold |
  | Section | 22 semibold |
  | Headline | 17 semibold |
  | Body | 15 |
  | Footnote | 13, secondary label color |

  Metrics use tabular figures.
- **Color:**
  - Apple system colors as theme tokens in `.streamlit/config.toml`, with separate `[theme.light]` and `[theme.dark]` palettes that follow the viewer's system setting.
  - One accent, system blue.
  - Status green, orange and red are reserved for state and always paired with a word.
  - Chart palettes go in `chartCategoricalColors` / `chartSequentialColors`, checked with the dataviz palette validator in both modes.
- **Surfaces:** tiles and the flow diagram sit on grouped-background cards with 12 px radius and no borders. Content width is capped near 1,200 px.
- **Charts:**
  - Thin marks and recessive grids.
  - A section heading plus one sentence saying what the chart shows, instead of in-plot titles.
  - Hover tooltips.
  - No pies and no dual axes.
- **Loading:** each section shows a placeholder while its query runs, instead of a blank page.

## Technical approach

- **`.streamlit/config.toml` (new):** theme tokens for both modes, fonts, heading sizes and chart colors.
- **`dashboard/style.css` (new):** the only stylesheet, injected once from `app.py`. It targets our own HTML and `st-key-*` classes. It touches Streamlit internals only where unavoidable, and each such rule carries a comment.
- **`dashboard/theme.py` (new):** shared tokens for Plotly and the HTML pieces.
- **`dashboard/queries.py` (new):** cached layer counts and freshness, shared by Overview and Pipeline health.
- **`dashboard/overview.py` (new).** `food_delivery_ops.py` becomes `operations.py`, so the URL changes to `/operations`.
- **Pin `streamlit==1.66.*`** in `requirements.txt`, and match it locally.
- **Keep-alive contract unchanged:** the `dashboard-ready` and `dashboard-status-<kind>` keys stay, and the monitor is re-run against a local build.
- **Vendored skills:**
  - `.claude/skills/hig-{foundations,components-layout,components-content,components-status,patterns}/SKILL.md`, plus Raintree's `LICENSE` and a `VENDORED.md` naming the source commit (`fdc35993d580`).
  - Apple's `references/` stay local and gitignored.
  - `.claude/apple-design-context.md` records this project's design context (web/Streamlit, the audience above, WCAG AA), because the skills look for it first.
  - `.gitignore` becomes `.claude/*` with exceptions for `skills/` and that context file.
- **README:** new light-mode screenshots of the three pages replace `docs/dashboard-*.png`.

## Testing

- The pytest suite stays green, and the keep-alive monitor reports `ok` against a local run.
- Screenshots in light and dark, at desktop width and at phone width (390 px).
- The palette validator passes in both modes.

## Out of scope

New metrics or analyses, changes to query semantics beyond the reconciliation table, and any dbt or pipeline change.

## Addendum (2026-10-22): alert when the data goes stale

After the redesign shipped locally, the Databricks job sat idle for hours after compute came back. The dashboard rendered fine and showed "Stale", so the keep-alive counted it as healthy. The maintainer asked for the keep-alive to also raise an outage when the Overview pill says Delayed or Stale.

- **App:** the Overview pill carries `data-freshness="live|delayed|stale|unknown"`. It's an explicit contract for the monitor, separate from the styling classes.
- **Monitor:** once the page has finished (`dashboard-ready` present), the freshness value decides the verdict:

  | Pill state | Verdict |
  |---|---|
  | `delayed` | down / `data-delayed` |
  | `stale` | down / `data-stale` |
  | `unknown` | down / `data-missing` |
  | `live`, or no attribute | `ok` |

  A status marker (dashboard down) still takes precedence.
- **Issue:** the same one-issue-per-outage flow. Data causes get their own titles:
  - "Pipeline delayed: no new orders for 3+ hours"
  - "Pipeline stalled: no new orders for 2+ days"
  - "Pipeline empty: no orders in gold"

  Each one explains what to check.
- **Known trade-off:** the producer runs on laptop cron, so overnight sleep can push the newest order past 3 hours. The states that trigger alerts are one constant in `keepalive.py` (`ALERT_ON`), so narrowing to Stale only is a one-line change.

**Revised the same day:** the maintainer chose to alert only when the newest order is **4+ days** old, or when gold has no data. Laptop-sleep gaps in the last 29 days reached 27 hours (42 gaps over 3 hours, none over 2 days). The pill also carries `data-age-minutes`, the monitor alerts at `ALERT_AFTER_MINUTES = 5760`, and `data-delayed` was removed. The pill's display thresholds are unchanged.

**Revised 2026-10-26:** Live now means under 24 hours, changed from 3. Laptop-sleep gaps made a 10-hour-old order read as Delayed. Delayed runs from 24 hours to 2 days; Stale is unchanged.

**Revised 2026-10-26 (again):** Live within a week, Delayed beyond that. The Stale state is gone. The keep-alive's 4-day data alert is a separate setting and is unchanged.
