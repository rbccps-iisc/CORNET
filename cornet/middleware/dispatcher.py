"""PacketDispatcher — physics-time priority queue with RTF-scaled sleep.

Algorithm 1 from the CORNET design (async dispatch, NOT barrier model):
  - Packets are enqueued with a physics_time release timestamp.
  - A background thread wakes when wall_clock >= release_time / rtf.
  - BER-induced loss uses geometric distribution (stdlib only, no numpy).
  - Packets exceeding deadline_s are silently discarded and counted.

Thread safety: all heap/dict access is protected by a single lock.
"""

from __future__ import annotations

import heapq
import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

_EPSILON = 0.001  # release tolerance in simulated seconds


@dataclass(order=True)
class _HeapEntry:
    release_time: float
    seq: int
    payload: bytes = field(compare=False)
    flow_id: str = field(compare=False, default="")


class PacketDispatcher:
    """Dispatch packets in physics-time order.

    Parameters
    ----------
    rtf:
        Real-time factor.  rtf=1.0 means 1 s sim == 1 s wall.
        rtf=0 means run as fast as possible (no sleep).
    deadline_s:
        Packets whose enqueue lag exceeds this simulated-second threshold
        are discarded.  deadline_s=0 disables deadline enforcement.
    ber:
        Bit-error rate per bit.  0.0 = lossless.
    on_dispatch:
        Callable invoked with (flow_id, payload) when a packet is released.
        Called from the dispatcher thread — must be thread-safe.
    """

    def __init__(
        self,
        rtf: float = 1.0,
        deadline_s: float = 0.5,
        ber: float = 0.0,
        on_dispatch: Callable[[str, bytes], None] | None = None,
    ) -> None:
        self.rtf = rtf
        self.deadline_s = deadline_s
        self.ber = ber
        self.on_dispatch = on_dispatch

        self._heap: list[_HeapEntry] = []
        self._lock = threading.Lock()
        self._wake = threading.Condition(self._lock)
        self._physics_time: float = 0.0
        self._seq: int = 0
        self._stopped = False

        # Stats
        self._n_enqueued: int = 0
        self._n_dispatched: int = 0
        self._n_deadline_drop: int = 0
        self._n_ber_drop: int = 0

        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background dispatch thread."""
        self._stopped = False
        self._thread = threading.Thread(
            target=self._dispatch_loop, name="cornet-dispatcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the dispatch thread to drain and exit."""
        with self._wake:
            self._stopped = True
            self._wake.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def update_physics_time(self, t: float) -> None:
        """Advance the physics clock.  May be called from any thread."""
        with self._wake:
            self._physics_time = t
            self._wake.notify_all()

    def enqueue(self, flow_id: str, physics_time: float, payload: bytes) -> None:
        """Add a packet to the release queue.

        Packets are released when physics_time >= release_time - _EPSILON.
        """
        with self._wake:
            # Deadline check: drop packets already past deadline
            if (
                self.deadline_s > 0.0
                and self._physics_time - physics_time > self.deadline_s
            ):
                self._n_deadline_drop += 1
                logger.debug(
                    "Deadline drop: flow=%s pt=%.3f now=%.3f deadline=%.3f",
                    flow_id,
                    physics_time,
                    self._physics_time,
                    self.deadline_s,
                )
                return
            seq = self._seq
            self._seq += 1
            entry = _HeapEntry(
                release_time=physics_time,
                seq=seq,
                payload=payload,
                flow_id=flow_id,
            )
            heapq.heappush(self._heap, entry)
            self._n_enqueued += 1
            self._wake.notify_all()

    def stats(self) -> dict[str, int]:
        """Return a snapshot of dispatcher statistics."""
        with self._lock:
            return {
                "enqueued": self._n_enqueued,
                "dispatched": self._n_dispatched,
                "deadline_drop": self._n_deadline_drop,
                "ber_drop": self._n_ber_drop,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_ber(self, payload: bytes) -> bytes | None:
        """Return corrupted payload or None if the packet is dropped by BER.

        Uses the geometric distribution to find the first errored bit.
        A single bit error in a header is treated as a full packet drop.
        """
        if self.ber <= 0.0:
            return payload
        if self.ber >= 1.0:
            return None
        n_bits = len(payload) * 8
        # Geometric: position of first error
        r = random.random()
        if r <= 0.0:
            # Avoid log(0) for edge-case; treat as guaranteed error
            first_error = 1
        else:
            first_error = math.ceil(math.log(r) / math.log(1.0 - self.ber))
        if first_error <= n_bits:
            return None  # packet dropped
        return payload

    def _dispatch_loop(self) -> None:
        """Background thread: release packets in physics-time order."""
        while True:
            sleep_for = 0.0
            with self._wake:
                while not self._heap and not self._stopped:
                    self._wake.wait(timeout=0.1)
                if self._stopped and not self._heap:
                    return

                if self._stopped:
                    entry = heapq.heappop(self._heap)
                else:
                    next_entry = self._heap[0]
                    next_pt = next_entry.release_time
                    current_pt = self._physics_time
                    remaining_sim = (next_pt + _EPSILON) - current_pt
                    if self.rtf > 0.0 and remaining_sim > 0.0:
                        sleep_for = max(0.0, remaining_sim / self.rtf)
                        entry = None
                    elif next_entry.release_time > self._physics_time + _EPSILON:
                        entry = None
                    else:
                        entry = heapq.heappop(self._heap)

            if entry is None:
                if sleep_for > 0.0:
                    time.sleep(sleep_for)
                continue

            # Apply BER outside the lock
            out = self._apply_ber(entry.payload)
            with self._lock:
                if out is None:
                    self._n_ber_drop += 1
                else:
                    self._n_dispatched += 1

            if out is not None and self.on_dispatch is not None:
                try:
                    self.on_dispatch(entry.flow_id, out)
                except Exception:
                    logger.exception(
                        "on_dispatch callback raised for flow=%s", entry.flow_id
                    )
