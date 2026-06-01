"""ClockServer and PositionServer — Unix Domain Socket servers.

ClockServer receives newline-delimited JSON messages of the form::

    {"t": 12.345}

and advances the shared physics clock.  Any registered listeners
(e.g. PacketDispatcher, AoITracker) are notified via callback.

PositionServer receives messages of the form::

    {"name": "robot0", "x": 1.0, "y": 2.0, "z": 0.0}

and atomically updates a shared position dict.

Both servers:
  - Clean up stale sockets on start.
  - Fall back to ``time.monotonic()`` if no client connects within
    *clock_timeout_s* seconds.
  - Have zero ROS imports.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_RECV_BUFSIZE = 4096
_BACKLOG = 5


class ClockServer:
    """UDS server that accepts physics-time updates.

    Parameters
    ----------
    socket_path:
        Path to the Unix domain socket file.
    clock_timeout_s:
        If no client connects within this many wall-clock seconds after
        ``start()``, the server falls back to advancing the clock via
        ``time.monotonic()`` at the real-time rate.
    on_tick:
        Optional callback invoked with the new physics time on every tick.
        Called from the server thread — must be thread-safe.
    """

    def __init__(
        self,
        socket_path: str = "/tmp/cornet_clock.sock",
        clock_timeout_s: float = 5.0,
        on_tick: Callable[[float], None] | None = None,
    ) -> None:
        self._socket_path = socket_path
        self._clock_timeout_s = clock_timeout_s
        self._on_tick = on_tick

        self._physics_time: float = 0.0
        self._lock = threading.Lock()
        self._stopped = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def physics_time(self) -> float:
        """Current physics time (thread-safe read)."""
        with self._lock:
            return self._physics_time

    def start(self) -> None:
        """Bind the socket and start the accept loop in a daemon thread."""
        self._stopped = False
        _remove_stale_socket(self._socket_path)
        self._thread = threading.Thread(
            target=self._accept_loop, name="cornet-clock-server", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the server to stop and wait for the thread to exit."""
        self._stopped = True
        # Unblock the accept() call by connecting to ourselves
        _poke_socket(self._socket_path)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        _remove_stale_socket(self._socket_path)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _accept_loop(self) -> None:
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.settimeout(self._clock_timeout_s)
        try:
            srv.bind(self._socket_path)
            srv.listen(_BACKLOG)
        except OSError as e:
            logger.error("ClockServer bind failed on %s: %s", self._socket_path, e)
            return

        client_connected = False
        while not self._stopped:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                if not client_connected:
                    logger.warning(
                        "ClockServer: no client within %.1fs — switching to wall-clock fallback",
                        self._clock_timeout_s,
                    )
                    self._wallclock_fallback()
                continue
            except OSError:
                break

            client_connected = True
            t = threading.Thread(
                target=self._handle_client,
                args=(conn,),
                name="cornet-clock-client",
                daemon=True,
            )
            t.start()

        srv.close()

    def _handle_client(self, conn: socket.socket) -> None:
        buf = b""
        try:
            while not self._stopped:
                try:
                    data = conn.recv(_RECV_BUFSIZE)
                except OSError:
                    break
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    self._process_clock_line(line.strip())
        finally:
            conn.close()

    def _process_clock_line(self, raw: bytes) -> None:
        if not raw:
            return
        try:
            msg = json.loads(raw)
            t = float(msg["t"])
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.debug("ClockServer: malformed message %r: %s", raw[:80], e)
            return
        with self._lock:
            self._physics_time = t
        if self._on_tick is not None:
            try:
                self._on_tick(t)
            except Exception:
                logger.exception("ClockServer on_tick callback raised")

    def _wallclock_fallback(self) -> None:
        """Advance physics time via wall clock until a real client connects."""
        t0_wall = time.monotonic()
        t0_phys = self.physics_time
        while not self._stopped:
            elapsed = time.monotonic() - t0_wall
            new_t = t0_phys + elapsed
            with self._lock:
                self._physics_time = new_t
            if self._on_tick is not None:
                try:
                    self._on_tick(new_t)
                except Exception:
                    logger.exception("ClockServer fallback on_tick raised")
            time.sleep(0.05)  # 20 Hz updates


class PositionServer:
    """UDS server that accepts node position updates.

    Maintains an atomic dict: ``positions[name] = {"x": float, "y": float, "z": float}``.

    Parameters
    ----------
    socket_path:
        Path to the Unix domain socket file.
    on_update:
        Optional callback invoked with ``(name, x, y, z)`` on every update.
    """

    def __init__(
        self,
        socket_path: str = "/tmp/cornet_positions.sock",
        on_update: Callable[[str, float, float, float], None] | None = None,
    ) -> None:
        self._socket_path = socket_path
        self._on_update = on_update

        self._positions: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()
        self._stopped = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._stopped = False
        _remove_stale_socket(self._socket_path)
        self._thread = threading.Thread(
            target=self._accept_loop, name="cornet-position-server", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopped = True
        _poke_socket(self._socket_path)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        _remove_stale_socket(self._socket_path)

    def get_position(self, name: str) -> dict[str, float] | None:
        """Return the latest position for *name*, or ``None`` if unknown."""
        with self._lock:
            return dict(self._positions[name]) if name in self._positions else None

    def all_positions(self) -> dict[str, dict[str, float]]:
        """Return a shallow copy of the full positions dict."""
        with self._lock:
            return {k: dict(v) for k, v in self._positions.items()}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _accept_loop(self) -> None:
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.settimeout(2.0)
        try:
            srv.bind(self._socket_path)
            srv.listen(_BACKLOG)
        except OSError as e:
            logger.error("PositionServer bind failed on %s: %s", self._socket_path, e)
            return

        while not self._stopped:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t = threading.Thread(
                target=self._handle_client,
                args=(conn,),
                name="cornet-position-client",
                daemon=True,
            )
            t.start()

        srv.close()

    def _handle_client(self, conn: socket.socket) -> None:
        buf = b""
        try:
            while not self._stopped:
                try:
                    data = conn.recv(_RECV_BUFSIZE)
                except OSError:
                    break
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    self._process_position_line(line.strip())
        finally:
            conn.close()

    def _process_position_line(self, raw: bytes) -> None:
        if not raw:
            return
        try:
            msg = json.loads(raw)
            name = str(msg["name"])
            x = float(msg.get("x", 0.0))
            y = float(msg.get("y", 0.0))
            z = float(msg.get("z", 0.0))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.debug("PositionServer: malformed message %r: %s", raw[:80], e)
            return
        with self._lock:
            self._positions[name] = {"x": x, "y": y, "z": z}
        if self._on_update is not None:
            try:
                self._on_update(name, x, y, z)
            except Exception:
                logger.exception("PositionServer on_update callback raised")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _remove_stale_socket(path: str) -> None:
    """Delete a socket file if it exists (stale from a previous run)."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.warning("Could not remove stale socket %s: %s", path, e)


def _poke_socket(path: str) -> None:
    """Connect briefly to unblock a blocking accept() call."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(path)
    except (OSError, socket.timeout):
        pass
