from dashboard_issue import CAUSES, decide, describe, format_duration, issue_body, last_cause, parse_ts


def test_first_failure_opens():
    assert decide(False, None, "down", "compute-blocked") == "open"


def test_same_cause_stays_quiet():
    assert decide(True, "compute-blocked", "down", "compute-blocked") == "none"


def test_new_cause_comments():
    assert decide(True, "compute-blocked", "down", "token-rejected") == "comment"


def test_unknown_last_cause_comments():
    assert decide(True, None, "down", "no-content") == "comment"


def test_recovery_closes():
    assert decide(True, "token-rejected", "ok", "") == "close"


def test_healthy_without_issue_is_quiet():
    assert decide(False, None, "ok", "") == "none"


def test_last_marker_wins():
    texts = ["body <!-- cause: compute-blocked -->", "x", "<!-- cause: token-rejected -->"]
    assert last_cause(texts) == "token-rejected"


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


def test_unknown_kind_still_describes():
    label, meaning = describe("disk-full")
    assert label == "disk-full" and meaning


def run_main(monkeypatch, status, cause, open_issues):
    import json

    import dashboard_issue

    calls = []

    def fake_gh(*args, write=True):
        calls.append(args)
        return json.dumps(open_issues) if args[:2] == ("issue", "list") else ""

    monkeypatch.setattr(dashboard_issue, "gh", fake_gh)
    for key, value in {"STATUS": status, "CAUSE": cause, "APP_URL": "https://app", "RUN_URL": "https://run"}.items():
        monkeypatch.setenv(key, value)
    dashboard_issue.main()
    return calls


OPEN_ISSUE = {"number": 7, "body": "x <!-- cause: compute-blocked -->", "createdAt": "2026-10-20T06:00:00Z", "comments": []}


def test_main_closes_open_issue_on_recovery(monkeypatch):
    calls = run_main(monkeypatch, "ok", "", [OPEN_ISSUE])
    close = next(c for c in calls if c[:2] == ("issue", "close"))
    assert close[2] == "7" and "after this outage was first detected" in close[-1]


def test_main_comments_and_retitles_on_new_cause(monkeypatch):
    calls = run_main(monkeypatch, "down", "token-rejected", [OPEN_ISSUE])
    comment = next(c for c in calls if c[:2] == ("issue", "comment"))
    edit = next(c for c in calls if c[:2] == ("issue", "edit"))
    assert comment[2] == "7" and "Databricks compute blocked → Databricks token rejected" in comment[-1]
    assert "<!-- cause: token-rejected -->" in comment[-1]
    assert edit[-1] == "Dashboard down: Databricks token rejected"


def test_main_stays_quiet_on_same_cause(monkeypatch):
    calls = run_main(monkeypatch, "down", "compute-blocked", [OPEN_ISSUE])
    assert not [c for c in calls if c[:2] in {("issue", "create"), ("issue", "comment"), ("issue", "close")}]
