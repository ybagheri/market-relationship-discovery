"""The CLI must not fail silently or leave a process behind.

Two defects in `cli.py`, both found by the audit and both invisible to a green
suite because each produced no wrong number at all.

`_serializable` raised a bare `TypeError` for anything it could not encode, and
a bare `TypeError` carries no message. NumPy scalars reach this function from
pandas inside report payloads, so a report write died with a traceback naming
neither the value, nor its type, nor the field it sat in, and the failure
surfaced long after the number that produced it was computed.

`_dashboard` used `subprocess.call`, which blocks in `wait()` and offers the
caller no way to stop the child. Verified directly: interrupting the CLI while
the app was starting left the child running and still holding the dashboard
port, so the next invocation could not bind and the orphan had to be killed by
hand.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from market_relationship_discovery.cli import _serializable, _terminate


class _Opaque:
    def __repr__(self) -> str:
        return "<an opaque report field>"


def test_a_numpy_scalar_is_serialised_as_a_number_not_a_string() -> None:
    """The common case: pandas values in a report payload.

    Not every NumPy scalar reaches the encoder. `np.float64` subclasses `float`
    and `np.int64` on some builds is handled by `json` directly, so those never
    arrive here. The ones that do arrive are `np.int64`, `np.bool_`,
    `np.float32`, arrays, and `np.datetime64`, and each of them previously
    produced a `TypeError` with no message.

    The values must round-trip as native JSON types. Reported as strings, a
    figure would be carried into a downstream consumer as text that cannot be
    compared or summed.
    """
    payload = {
        "count": np.int64(7),
        "flag": np.bool_(True),
        "small": np.float32(0.5),
        "series": np.array([1.0, 2.0]),
    }

    restored = json.loads(_serializable(payload))

    assert restored == {"count": 7, "flag": True, "small": 0.5, "series": [1.0, 2.0]}
    assert isinstance(restored["count"], int)
    assert isinstance(restored["flag"], bool)
    assert not isinstance(restored["count"], str)


def test_an_unserialisable_value_names_its_type_and_value() -> None:
    """A context-free error is the defect, so the message is the assertion.

    `raise TypeError` produces an exception whose `str()` is empty, so the
    traceback said only that something was wrong.
    """
    with pytest.raises(TypeError) as failure:
        _serializable({"metrics": {"edge": _Opaque()}})

    message = str(failure.value)
    assert message, "TypeError must carry a message"
    assert "_Opaque" in message
    assert "an opaque report field" in message


def test_the_existing_conversions_are_unchanged() -> None:
    """Dataclasses, enums, paths, and dates must still serialise as before."""
    from dataclasses import dataclass
    from datetime import UTC, datetime
    from enum import StrEnum
    from pathlib import Path as RealPath

    class Kind(StrEnum):
        TICK = "tick"

    @dataclass
    class Row:
        value: float

    payload = {
        "row": Row(1.5),
        "kind": Kind.TICK,
        "path": RealPath("a/b.parquet"),
        "when": datetime(2026, 9, 25, tzinfo=UTC),
    }

    restored = json.loads(_serializable(payload))

    assert restored["row"] == {"value": 1.5}
    assert restored["kind"] == "tick"
    assert restored["path"].endswith("b.parquet")
    assert restored["when"].startswith("2026-09-25")


def _running_child(script: Path, pidfile: Path) -> subprocess.Popen[bytes]:
    script.write_text(
        "import os, pathlib, time\n"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(120)\n",
        encoding="utf-8",
    )
    return subprocess.Popen([sys.executable, str(script)])


def test_the_old_wait_strategy_orphans_the_child(tmp_path: Path) -> None:
    """Why `_terminate` exists, asserted against the strategy it replaced.

    `subprocess.call` is `Popen(...).wait()`: an interrupt reaches the parent
    and leaves the child running, still holding the dashboard port. This test
    runs that strategy directly so the claim behind the fix is checked rather
    than repeated in a docstring, and so it documents the behaviour on the
    platform the CLI actually runs on.
    """
    pidfile = tmp_path / "pid"
    script = tmp_path / "child.py"
    script.write_text(
        "import os, pathlib, time\n"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(120)\n",
        encoding="utf-8",
    )
    process = subprocess.Popen([sys.executable, str(script)])
    pid = _wait_for_pid(pidfile)

    # The old strategy: propagate the interrupt, do not touch the child.
    try:
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired as exc:
            raise KeyboardInterrupt from exc
    except KeyboardInterrupt:
        pass

    assert _is_running(pid), (
        "expected the bare wait() strategy to leave the child running; if this "
        "platform reaps children on interrupt the fix is still correct but "
        "this premise no longer holds"
    )
    _terminate(process)


def _is_running(pid: int) -> bool:
    import ctypes

    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    code = ctypes.c_ulong()
    ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(handle)
    return code.value == 259


def _wait_for_pid(pidfile: Path) -> int:
    for _ in range(100):
        if pidfile.exists():
            return int(pidfile.read_text())
        time.sleep(0.05)
    raise AssertionError("child never reported its pid")


def test_terminate_stops_a_child_that_is_still_running(tmp_path: Path) -> None:
    """The orphan the interrupt used to leave behind."""
    pidfile = tmp_path / "pid"
    process = _running_child(tmp_path / "child.py", pidfile)
    pid = _wait_for_pid(pidfile)
    assert _is_running(pid)

    _terminate(process)

    assert not _is_running(pid)
    assert process.poll() is not None


def test_terminate_is_a_no_op_for_a_child_that_already_exited() -> None:
    """The finally path runs on a normal exit too, so it must tolerate one."""
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()

    _terminate(process)

    assert process.returncode == 0


def test_an_interrupt_during_the_wait_leaves_no_running_child(tmp_path: Path) -> None:
    """The whole point: the CLI can be stopped without orphaning the app."""
    pidfile = tmp_path / "pid"
    process = _running_child(tmp_path / "child.py", pidfile)
    pid = _wait_for_pid(pidfile)

    with pytest.raises(KeyboardInterrupt):
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired as exc:
            raise KeyboardInterrupt from exc
        finally:
            _terminate(process)

    assert not _is_running(pid)
