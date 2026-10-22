from keepalive import EXCEPTION, FRESHNESS, READY, STATUS, Observation, observe, verdict, write_outputs


class FakeLocator:
    def __init__(self, count=0, cls=None, detached=False):
        self._count, self._cls, self._detached = count, cls, detached

    def count(self):
        if self._detached:
            raise RuntimeError("Frame was detached")
        return self._count

    @property
    def first(self):
        return self

    def get_attribute(self, name):
        return self._cls


class FakeFrame:
    def __init__(self, counts=None, status_class=None, detached=False, freshness=None):
        self.counts, self.status_class, self.detached = dict(counts or {}), status_class, detached
        self.freshness = freshness
        if freshness is not None:
            self.counts[FRESHNESS] = 1

    def locator(self, selector):
        attribute = {STATUS: self.status_class, FRESHNESS: self.freshness}.get(selector)
        return FakeLocator(self.counts.get(selector, 0), attribute, self.detached)


def test_status_marker_wins():
    obs = Observation(ready=False, status="compute-blocked", exception=False, wake_button=False)
    assert verdict(obs) == ("down", "compute-blocked")


def test_ready_is_ok():
    assert verdict(Observation(ready=True, status=None, exception=False, wake_button=False)) == ("ok", "")


def test_exception_without_marker_is_app_exception():
    obs = Observation(ready=False, status=None, exception=True, wake_button=False)
    assert verdict(obs) == ("down", "app-exception")


def test_nothing_is_no_content():
    obs = Observation(ready=False, status=None, exception=False, wake_button=True)
    assert verdict(obs) == ("down", "no-content")


def test_observe_reads_status_kind_from_class():
    frame = FakeFrame({STATUS: 1}, status_class="stVerticalBlock st-key-dashboard-status-token-rejected e1x")
    assert observe([frame]).status == "token-rejected"


def test_observe_finds_ready_in_any_frame():
    frames = [FakeFrame(), FakeFrame({READY: 1})]
    assert observe(frames) == Observation(ready=True, status=None, exception=False, wake_button=False)


def test_observe_survives_detached_frame():
    frames = [FakeFrame(detached=True), FakeFrame({EXCEPTION: 1})]
    assert observe(frames) == Observation(ready=False, status=None, exception=True, wake_button=False)


def test_write_outputs_appends_to_file(tmp_path):
    out = tmp_path / "out"
    write_outputs("down", "no-content", str(out))
    assert out.read_text() == "status=down\ncause=no-content\n"


def test_write_outputs_without_path_prints(capsys):
    write_outputs("ok", "", None)
    assert "status=ok" in capsys.readouterr().out


def test_observe_keeps_only_safe_kind_characters():
    frame = FakeFrame({STATUS: 1}, status_class="st-key-dashboard-status-token-rejected$(curl) other")
    assert observe([frame]).status == "token-rejected"


def test_ready_with_stale_data_is_an_outage():
    obs = Observation(ready=True, status=None, exception=False, wake_button=False, freshness="stale")
    assert verdict(obs) == ("down", "data-stale")


def test_ready_with_delayed_or_missing_data_is_an_outage():
    assert verdict(Observation(True, None, False, False, "delayed")) == ("down", "data-delayed")
    assert verdict(Observation(True, None, False, False, "unknown")) == ("down", "data-missing")


def test_live_or_unmarked_data_is_ok():
    assert verdict(Observation(True, None, False, False, "live")) == ("ok", "")
    assert verdict(Observation(True, None, False, False)) == ("ok", "")


def test_status_marker_beats_freshness():
    assert verdict(Observation(True, "token-rejected", False, False, "stale")) == ("down", "token-rejected")


def test_observe_reads_freshness():
    assert observe([FakeFrame({READY: 1}, freshness="delayed")]).freshness == "delayed"


def test_observe_ignores_unknown_freshness_values():
    assert observe([FakeFrame({READY: 1}, freshness="$(id)")]).freshness is None
