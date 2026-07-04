# Scripts

## `live_tick.sh`

Hourly tick script — generates events for the current hour, **auto-backfills any missed hours**, and syncs to S3.

### How it handles laptop sleep

- Maintains a state file at `data/.last_tick` (UTC `YYYY-MM-DDTHH`).
- On each run, computes hours missed since last tick and backfills them in order.
- Safety cap: max 168 hours (1 week) of backfill in one run (configurable in script).
- If you close your laptop at 10pm and reopen at 6am, the next cron tick (6:05am) will generate 8 hours of catch-up data + the current hour, then sync everything to S3.

### Setup

1. Already executable (already chmod +x'd).

2. Test manually first:
   ```bash
   ./scripts/live_tick.sh
   ```
   Confirm it runs, generates events, and syncs to S3 without errors.

3. Add to crontab (`crontab -e`):
   ```cron
   # Hourly food delivery simulator tick (runs at minute 5 each hour)
   5 * * * * /bin/bash /Users/ernestau/Documents/food-delivery-pipeline/scripts/live_tick.sh
   ```

   Note: minute 5 (not 0) gives a small buffer so events naturally fall within
   the current hour rather than overlapping the hour boundary.

   **IMPORTANT — invoke via `/bin/bash`, not the bare script path.** macOS TCC
   assigns the "responsible process" from whatever cron `execve`s. If that is the
   script itself (which lives in `~/Documents`, a TCC-protected folder), TCC denies
   the script's child `python` read-access to `~/Documents` — so `import simulator`
   fails with `ModuleNotFoundError`, the run dies before the S3 sync, and the dashboard
   silently stops updating. Routing through `/bin/bash` (a system binary in an
   unprotected path) makes `/bin/bash` the responsible process, which has proper
   access. The script's preflight check will catch this and print a pointer if it
   ever regresses.

4. Check logs:
   ```bash
   ls -lt logs/ | head -5
   tail -50 logs/live_tick_*.log
   ```

### Venv

The venv lives at `.venv/` in the project root (the standard location).

To recreate the venv if needed:
```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

For interactive dev (running Streamlit etc.), activate it:
```bash
source .venv/bin/activate
```

### Troubleshooting

**cron isn't running the script:**
- macOS requires giving `cron` Full Disk Access: System Settings → Privacy → Full Disk Access → add `/usr/sbin/cron`
- Check cron is enabled: `sudo launchctl list | grep cron`

**`ModuleNotFoundError: No module named 'simulator'` under cron (but works when run by hand):**
- Same macOS TCC root cause, different symptom. The crontab is invoking the script via its
  bare path (`5 * * * * /Users/.../live_tick.sh`), so the in-`~/Documents` script becomes the
  TCC responsible process and its child `python` is denied read-access to `~/Documents` —
  the `simulator` package is right there but invisible to the import.
- Fix: prefix the crontab command with `/bin/bash` (see step 3 above). The preflight check
  prints a reminder if this regresses.
