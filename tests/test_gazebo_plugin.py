from __future__ import annotations

import signal
from pathlib import Path

from cornet.plugins.robot.gazebo_plugin import GazeboPlugin


def test_early_launch_exit_includes_stdout(monkeypatch) -> None:
    class _Exited:
        returncode = 1
        stdout = type("Out", (), {"read": staticmethod(lambda: "FileNotFoundError: models/pendulum.urdf")})()

        def poll(self):
            return self.returncode

    monkeypatch.setattr(
        "cornet.plugins.robot.gazebo_plugin.subprocess.run",
        lambda *args, **kwargs: type("R", (), {"stdout": ""})(),
    )
    monkeypatch.setattr("cornet.plugins.robot.gazebo_plugin.time.sleep", lambda _s: None)

    plugin = GazeboPlugin()
    plugin._launch_proc = _Exited()
    try:
        plugin._wait_for_clock()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert "code 1" in message
    assert "models/pendulum.urdf" in message


def test_launch_starts_in_its_own_process_group(monkeypatch, tmp_path: Path) -> None:
    seen: dict = {}

    class _Proc:
        pid = 7
        stdout = None

        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        seen["kwargs"] = kwargs
        return _Proc()

    monkeypatch.setattr("cornet.plugins.robot.gazebo_plugin.subprocess.Popen", fake_popen)
    plugin = GazeboPlugin()
    plugin._auto_generated = False
    plugin._launch_path = tmp_path / "launch.py"
    plugin._launch_path.write_text("pass\n")
    plugin._wait_for_clock = lambda: None
    plugin.start()
    assert seen["kwargs"]["start_new_session"] is True


def test_stop_kills_gazebo_after_launch_parent_exits(monkeypatch, tmp_path: Path) -> None:
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "cornet.plugins.robot.gazebo_plugin.os.killpg",
        lambda pid, sig: signals.append((pid, sig)),
    )

    class _DeadParent:
        pid = 910327

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

        def send_signal(self, sig):
            return None

    launch_dir = tmp_path / "cornet_launch"
    launch_dir.mkdir()
    launch_file = launch_dir / "generated_launch_1.py"
    launch_file.write_text("# generated\n")

    plugin = GazeboPlugin()
    plugin._launch_proc = _DeadParent()
    plugin._auto_generated = True
    plugin._launch_dir = launch_dir
    plugin._launch_path = launch_file

    plugin.stop()
    plugin.stop()

    assert (910327, signal.SIGKILL) in signals
    assert not launch_dir.exists()
