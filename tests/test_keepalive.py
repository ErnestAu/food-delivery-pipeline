from keepalive import EXCEPTION, READY, STATUS, Observation, observe, verdict, write_outputs


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
    def __init__(self, counts=None, status_class=None, detached=False):
        self.counts, self.status_class, self.detached = counts or {}, status_class, detached

    def locator(self, selector):
        cls = self.status_class if selector == STATUS else None
        return FakeLocator(self.counts.get(selector, 0), cls, self.detached)


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
