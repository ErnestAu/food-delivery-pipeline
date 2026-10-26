"""Keep the Streamlit app awake and report whether it's actually serving data.

The dashboard renders `st-key-dashboard-ready` after a clean page render, or
`st-key-dashboard-status-<kind>` when the warehouse fails (see dashboard/db.py).
The Overview's status pill also carries `data-freshness` and `data-age-minutes`.
This script opens the app, wakes it if needed, waits for one of those markers,
and writes `status` (ok/down) and `cause` to $GITHUB_OUTPUT for the workflow.
It exits non-zero only when the monitor itself breaks.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

READY = ".st-key-dashboard-ready"
STATUS = "[class*='st-key-dashboard-status-']"
EXCEPTION = "[data-testid='stException']"
WAKE = "text=/get this app back up/i"
FRESHNESS = "[data-freshness]"

FRESHNESS_STATES = {"live", "delayed", "unknown"}
# Old data counts as an outage only after 4 days: the producer runs on laptop cron, and
# overnight sleep regularly leaves gaps of up to a day that recover on their own.
ALERT_AFTER_MINUTES = 4 * 24 * 60

DEADLINE_S = 240  # cold start + warehouse wake-up
POLL_S = 5
RETRY_S = 120  # one second look before calling an outage
LINGER_S = 10  # let Streamlit register the visit

_KIND = re.compile(r"st-key-dashboard-status-([a-z0-9-]+)")  # the kind flows into the workflow


@dataclass
class Observation:
    ready: bool
    status: str | None
    exception: bool
    wake_button: bool
    freshness: str | None = None
    age_minutes: int | None = None


def observe(frames) -> Observation:
    """Look for the markers in every frame; the app renders inside an iframe."""
    ready = exception = wake_button = False
    status = freshness = age = None
    for frame in frames:
        try:
            ready = ready or frame.locator(READY).count() > 0
            exception = exception or frame.locator(EXCEPTION).count() > 0
            wake_button = wake_button or frame.locator(WAKE).count() > 0
            marker = frame.locator(STATUS)
            if status is None and marker.count():
                match = _KIND.search(marker.first.get_attribute("class") or "")
                status = match.group(1) if match else None
            pill = frame.locator(FRESHNESS)
            if freshness is None and pill.count():
                value = pill.first.get_attribute("data-freshness")
                freshness = value if value in FRESHNESS_STATES else None
                raw_age = pill.first.get_attribute("data-age-minutes") or ""
                age = int(raw_age) if raw_age.lstrip("-").isdigit() else None
        except Exception:  # a frame can detach mid-poll while Streamlit Cloud reloads it
            continue
    return Observation(ready, status, exception, wake_button, freshness, age)


def verdict(obs: Observation) -> tuple[str, str]:
    if obs.status:
        return "down", obs.status
    if obs.ready:
        if obs.freshness == "unknown":  # the page works, but gold has no data at all
            return "down", "data-missing"
        if obs.age_minutes is not None and obs.age_minutes >= ALERT_AFTER_MINUTES:
            return "down", "data-stale"  # the page works, but the pipeline behind it has stalled
        return "ok", ""
    if obs.exception:
        return "down", "app-exception"
    return "down", "no-content"


def write_outputs(status: str, cause: str, path: str | None) -> None:
    lines = f"status={status}\ncause={cause}\n"
    if path:
        with open(path, "a") as out:
            out.write(lines)
    else:
        print(lines, end="")


def _click_wake(page) -> None:
    for frame in page.frames:
        try:
            button = frame.locator(WAKE)
            if button.count():
                button.first.click(timeout=8_000)
                return
        except Exception:
            continue


def _page_text(page) -> str:
    texts = []
    for frame in page.frames:
        try:
            texts.append(frame.locator("body").inner_text(timeout=5_000))
        except Exception:
            continue
    return "\n".join(t.strip() for t in texts if t.strip())[:2_000]


def check(url: str) -> tuple[str, str]:
    """One attempt: open the app, wake it if asleep, wait for a marker."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(url, timeout=60_000)
        except Exception as exc:  # unreachable app or Streamlit Cloud: an outage, not a monitor bug
            print(f"Could not load {url}: {exc}")
            browser.close()
            return "down", "no-content"
        deadline = time.monotonic() + DEADLINE_S
        obs = observe(page.frames)
        while not (obs.ready or obs.status or obs.exception) and time.monotonic() < deadline:
            if obs.wake_button:
                print("App was asleep: clicking the wake button.")
                _click_wake(page)
            time.sleep(POLL_S)
            obs = observe(page.frames)

        status, cause = verdict(obs)
        if status == "ok":
            time.sleep(LINGER_S)
        else:
            print(f"--- page text ({cause}) ---\n{_page_text(page)}\n---")
        browser.close()
    return status, cause


def main() -> None:
    url = os.environ["APP_URL"]
    status, cause = check(url)
    if status == "down":
        print(f"Down ({cause}); checking again in {RETRY_S}s.")
        time.sleep(RETRY_S)
        status, cause = check(url)
    print(f"Verdict: {status} {cause}".strip())
    write_outputs(status, cause, os.environ.get("GITHUB_OUTPUT"))


if __name__ == "__main__":
    main()
