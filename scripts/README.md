# Scripts

## `live_tick.sh`

Hourly tick script — generates events for the current hour, **auto-backfills any missed hours**, and syncs to S3.

### How it handles laptop sleep

- Maintains a state file at `data/.last_tick` (UTC `YYYY-MM-DDTHH`).
- On each run, computes hours missed since last tick and backfills them in order.
- Safety cap: max 72 hours of backfill in one run (configurable in script).
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
   5 * * * * /Users/ernestau/Documents/food-delivery-pipeline/scripts/live_tick.sh
   ```

   Note: minute 5 (not 0) gives a small buffer so events naturally fall within
   the current hour rather than overlapping the hour boundary.

4. Check logs:
   ```bash
   ls -lt logs/ | head -5
   tail -50 logs/live_tick_*.log
   ```

### Troubleshooting

**cron isn't running the script:**
- macOS requires giving `cron` Full Disk Access: System Settings → Privacy → Full Disk Access → add `/usr/sbin/cron`
- Check cron is enabled: `sudo launchctl list | grep cron`

**AWS CLI fails in cron but works manually:**
- cron has a minimal PATH. Script handles this by exporting PATH explicitly.
- If using AWS SSO or temp creds: cron can't refresh those. Use a long-lived IAM access key for `food-delivery-cli` (already set up).

**Simulator runs but no files written:**
- Check `cfg.raw_base_path` in `simulator/config.py` — should be `data/raw` relative to CWD.
- Script `cd`s into project root first, so this should work.
