from datetime import datetime, timezone

import pandas as pd

from freshness import freshness_state, humanize, minutes_since


def test_states_follow_thresholds():
    minutes = (0, 179, 180, 2879, 2880, None)
    assert [freshness_state(m) for m in minutes] == ["live", "live", "delayed", "delayed", "stale", "unknown"]


def test_humanize():
    assert [humanize(m) for m in (None, 0.5, 12, 185, 3120)] == ["—", "just now", "12 min", "3 h 5 min", "2 d 4 h"]


def test_naive_timestamps_are_utc():
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    assert minutes_since(pd.Timestamp("2026-10-22 11:00:00"), now) == 60
    assert minutes_since(pd.Timestamp("2026-10-22 20:00:00+09:00"), now) == 60
    assert minutes_since(None, now) is None
    assert minutes_since(pd.NaT, now) is None


def test_ago_text():
    from freshness import ago_text

    assert [ago_text(m) for m in (None, 0.2, 12)] == ["no data yet", "just now", "12 min ago"]
