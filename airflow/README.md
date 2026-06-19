# Airflow Orchestration (local, via Astro CLI)

This folder is a local [Astro CLI](https://www.astronomer.io/docs/astro/cli/overview) project that runs Apache Airflow in Docker. It defines a single DAG, **`food_delivery_pipeline`**, that orchestrates the whole batch flow as one unit — replacing the v0 setup of two disconnected schedulers (macOS cron + a Databricks scheduled job "synced by timing").

## The DAG

`dags/food_delivery_pipeline.py` — three tasks, run in order:

```
generate_events  ──▶  sync_to_s3  ──▶  trigger_databricks
```

| Task | Operator | What it does |
|---|---|---|
| `generate_events` | `BashOperator` | Runs the simulator for the current hour (`python -m simulator.main --live`) inside the scheduler container. |
| `sync_to_s3` | `PythonOperator` + `S3Hook` | Uploads the new JSONL to S3 (`aws_default` connection). |
| `trigger_databricks` | `DatabricksRunNowOperator` | Triggers the existing Databricks job and waits for it (`databricks_default` connection). |

The DAG is `schedule=None` (manual-trigger only) so it coexists with the still-running cron feed without double-writing. It's an on-demand demonstration of unified orchestration, not the 24/7 production driver.

## Run it

**Prerequisites:** Docker Desktop running + the [Astro CLI](https://www.astronomer.io/docs/astro/cli/install-cli) (`brew install astro`).

```bash
astro dev start      # builds + starts Airflow (UI at http://localhost:8080, admin/admin)
astro dev restart    # rebuild after changing requirements.txt
astro dev stop       # stop the containers (frees RAM)
```

## Setup notes

- **Simulator code** is bind-mounted into the scheduler via [`docker-compose.override.yml`](docker-compose.override.yml) (`../simulator → /usr/local/airflow/simulator`) — single source of truth, no copy.
- **Connections** (create under Admin → Connections in the UI):
  - `aws_default` — AWS access key + secret (for the S3 sync).
  - `databricks_default` — host `https://<workspace>` + a full-scope PAT (`dapi…`) in the password field.
- **Python deps** for the Airflow image live in [`requirements.txt`](requirements.txt) (`faker`, the Amazon + Databricks providers).
