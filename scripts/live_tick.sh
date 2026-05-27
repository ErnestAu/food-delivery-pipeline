#!/bin/bash
# Hourly tick: generate events for the current hour + backfill any missed hours.
# Called by cron — see scripts/README.md.

set -euo pipefail

# --- Config ---
PROJECT_DIR="/Users/ernestau/Documents/food-delivery-pipeline"
S3_BUCKET="s3://food-delivery-pipeline-102947735140-ap-southeast-1-an"
DAILY_TARGET=300
LOG_DIR="$PROJECT_DIR/logs"
STATE_FILE="$PROJECT_DIR/data/.last_tick"   # tracks last successful hour as "YYYY-MM-DDTHH"
MAX_BACKFILL_HOURS=168                       # safety cap (1 week)

# --- Setup ---
mkdir -p "$LOG_DIR" "$(dirname "$STATE_FILE")"
TIMESTAMP="$(date -u +'%Y-%m-%d_%H')"
LOG_FILE="$LOG_DIR/live_tick_${TIMESTAMP}.log"

cd "$PROJECT_DIR"

# cron has a minimal PATH — restore it so we can find aws CLI
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Use the project's venv Python directly (no shell activation needed)
PYTHON="$PROJECT_DIR/.venv/bin/python"

# Ensure Python can import the local simulator package
export PYTHONPATH="$PROJECT_DIR:${PYTHONPATH:-}"

{
    echo "==============================="
    echo "Live tick: $(date -u)"
    echo "==============================="

    NOW_UTC_DATE="$(date -u +'%Y-%m-%d')"
    NOW_UTC_HOUR="$(date -u +'%H')"
    NOW_UTC_HOUR_INT=$((10#$NOW_UTC_HOUR))   # 10# = force base 10 (avoids 08 → octal error)
    NOW_KEY="${NOW_UTC_DATE}T${NOW_UTC_HOUR}"
    NOW_EPOCH=$(date -u -j -f "%Y-%m-%dT%H" "$NOW_KEY" "+%s")

    # --- Detect missed hours ---
    # If no state file, treat as if last tick was MAX_BACKFILL_HOURS ago (backfill the week)
    if [[ -f "$STATE_FILE" ]]; then
        LAST_KEY="$(cat "$STATE_FILE")"
        LAST_EPOCH=$(date -u -j -f "%Y-%m-%dT%H" "$LAST_KEY" "+%s")
    else
        echo "  No state file — assuming 1 week of catch-up needed"
        LAST_EPOCH=$(( NOW_EPOCH - (MAX_BACKFILL_HOURS * 3600) ))
    fi

    # Hours between last tick + 1 and the hour BEFORE now (current hour handled by --live)
    MISSED_HOURS=$(( (NOW_EPOCH - LAST_EPOCH) / 3600 - 1 ))

    if (( MISSED_HOURS > 0 )); then
        if (( MISSED_HOURS > MAX_BACKFILL_HOURS )); then
            echo "  WARN: $MISSED_HOURS missed hours exceeds cap ($MAX_BACKFILL_HOURS), backfilling last $MAX_BACKFILL_HOURS only"
            MISSED_HOURS=$MAX_BACKFILL_HOURS
        fi
        echo "  Backfilling $MISSED_HOURS missed hour(s)..."

        for ((i = MISSED_HOURS; i >= 1; i--)); do
            BACKFILL_EPOCH=$(( NOW_EPOCH - (i * 3600) ))
            BACKFILL_DATE=$(date -u -j -f "%s" "$BACKFILL_EPOCH" "+%Y-%m-%d")
            BACKFILL_HOUR=$(date -u -j -f "%s" "$BACKFILL_EPOCH" "+%H")
            BACKFILL_HOUR_INT=$((10#$BACKFILL_HOUR))

            echo "    > Backfill $BACKFILL_DATE hour=$BACKFILL_HOUR"
            "$PYTHON" -m simulator.main \
                --date "$BACKFILL_DATE" \
                --hour "$BACKFILL_HOUR_INT" \
                --daily-target "$DAILY_TARGET"
        done
    else
        echo "  No missed hours."
    fi

    # --- Current hour (live) ---
    echo ""
    echo "[1/2] Generating events for current hour..."
    "$PYTHON" -m simulator.main --live --daily-target "$DAILY_TARGET"

    # --- Sync everything to S3 ---
    echo ""
    echo "[2/2] Syncing to S3..."
    aws s3 sync data/raw/order_events/ "$S3_BUCKET/data/raw/order_events/" --only-show-errors

    # --- Update state file ---
    echo "$NOW_KEY" > "$STATE_FILE"

    echo ""
    echo "Done at $(date -u). State updated to $NOW_KEY"
} 2>&1 | tee -a "$LOG_FILE"
