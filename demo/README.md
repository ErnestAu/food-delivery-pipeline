# dbt PR reviewer demo

This is the build-day demo harness, not a production deployment. It keeps the
cloud pipeline untouched and runs a small, repeatable slice of the real dbt
project against a local DuckDB database.

## Architecture

`demo/load_demo_data.py` creates a deterministic, demo-only source layer in
DuckDB's `demo` schema. It contains 120 customers, 30 vendors, 45 drivers, 360
menu items, and 500 order lifecycles. The existing CI seed fixtures are not
used or changed. Existing dbt sources resolve to the demo schema only for `--target demo`; the
Databricks `dev` and `ci` targets are unchanged. The demo target treats tests as
errors (like CI), while production `dev` continues to surface known real-data
issues as warnings. The harness then rebuilds the dimension and order models and
uses the existing `fct_orders` data tests as the independent verifier.

The reviewer has a deliberately narrow contract:

1. dbt reports a failed model test.
2. The harness sends only that failure, the analyst model SQL, its declared
   contract, relevant parent-model context, and `AGENTS.md` rules to Codex.
3. Codex runs read-only and returns a schema-validated decision: suggest a
   patch, warn for review, or pass.
4. The harness renders a proposed diff but never writes it to disk.

This makes the boundary clear in a presentation: **dbt supplies independent
test evidence; Codex reviews the PR; a human decides whether to accept a
proposal.**

## Demo commands

Run these from the repository root:

```bash
python demo/agent.py --bootstrap
python demo/agent.py --review
python demo/agent.py --review --scenario lifecycle-timeline
```

`--bootstrap` creates `dbt/food_delivery/data/demo/food_delivery.duckdb` locally
from a deterministic fixture and proves the established core baseline. The file
is ignored by Git. `--review` runs the simulated analyst PR model and its dbt
contract, then invokes the authenticated local Codex CLI in read-only mode to
print a decision and, when warranted, a proposed diff. It does not change SQL.
The default `vendor-performance` scenario has a mechanical join-key defect;
`lifecycle-timeline` deliberately changes timestamp semantics and must produce
a warning for human review rather than a patch.

## Why not S3 or the simulator?

S3 would require live credentials, venue network, and production-shaped files.
Generating a new simulator batch introduces another setup step and a potentially
changing data state. Neither improves the core claim: an agent can review a dbt
pull request using independent test evidence. The deterministic fixture is the
local boundary that makes that claim repeatable on stage; it is not presented as
production data or a data-quality remediation system.

`fct_order_items` is intentionally outside this demo slice because the existing
fixture has no nested `items` column—the same reason CI excludes that model.

## Real GitHub PR check

`.github/workflows/analyst_pr_ci.yml` is a separate, unprivileged GitHub Actions
check. It runs the exact DuckDB setup above on a pull request, builds
`fct_vendor_daily_performance`, and enforces its contract. The intentional wrong
join makes this check red; that failure is the future GitHub review agent's
input. The workflow uses no cloud-warehouse credentials and no model API key.
On a PR that does not change this named analyst model or its contract, the same
required job exits successfully with an explicit skip so it does not block
unrelated platform updates.

The established `dbt-build` workflow stays separate: analyst demo models are
enabled only for the `demo` target, so they do not contaminate Databricks CI.

To publish the platform branch, stage only the demo platform files and run
these commands yourself from the repository root:

```bash
git add demo .github/scripts .github/workflows/pr_review_agent.yml
git commit -m "feat: add dbt PR review demo"
git push -u origin codex/duckdb-agent-demo
```

The platform branch stays isolated from `main`. Commit the harness on
`codex/duckdb-agent-demo`, then create a separate analyst branch that contains
`models/analyst_pr/` and open that PR **into** `codex/duckdb-agent-demo`.
Expect `analyst-pr-duckdb` to fail because the simulated analyst model joins
`vendor_id` to `city`. Do not repair that join yet—the red check is the demo's
starting state.

## GitHub PR review agent

`.github/workflows/pr_review_agent.yml` adds the presentation-layer agent. It
waits for a failed `Analyst PR DuckDB Check`, reads only the explicitly named
analyst SQL file as text, and posts a GitHub review:

- **HIGH / suggest fix:** a unified diff plus a native GitHub inline
  suggestion. Select **Commit suggestion** to make the correction yourself.
- **WARNING / warn for review:** an explanation and clarifying question, with
  no SQL patch.

The workflow never checks out or executes analyst PR code, never modifies
files, and never commits. The base branch supplies the reviewer code and
`AGENTS.md`; the PR SQL and dbt log are treated only as untrusted review
evidence.

Before using it, add `OPENAI_API_KEY` under **Settings → Secrets and variables
→ Actions → New repository secret**. Optionally add an `OPENAI_REVIEW_MODEL`
repository variable; otherwise the workflow uses `gpt-4.1-mini`.

After you push this platform update to `codex/duckdb-agent-demo`, push any new
commit to the analyst PR branch to trigger the review agent. The agent comment
appears only after the DuckDB check finishes red.
