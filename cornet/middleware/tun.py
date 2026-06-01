"""TunManager — Linux TUN interface lifecycle and policy routing.

Creates one TUN interface per CORNET node (IP), attaches file descriptors,
and installs ip-rule / ip-route entries so that NS-3 tap traffic is
steered to the correct interface.

Requires CAP_NET_ADMIN (root or ambient capability).

Usage::

    mgr = TunManager(ip_list=["10.0.0.1", "10.0.0.2"])
    mgr.setup()         # create TUNs and configure routing
    # ... run simulation ...
    mgr.teardown()      # idempotent cleanup
"""

from __future__ import annotations

import fcntl
import logging
import os
import struct
import subprocess
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

# Linux TUN/TAP ioctl constants
TUNSETIFF = 0x400454CA
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000  # do not prepend packet info header

# Template for TUN interface names: cornet0, cornet1, ...
_TUN_PREFIX = "cornet"

# Routing table base: outbound table i+1, loopback table i+101
_OUTBOUND_TABLE_BASE = 1
_LOOPBACK_TABLE_BASE = 101


class TunManager:
    """Manage a set of Linux TUN interfaces for CORNET nodes.

    Parameters
    ----------
    ip_list:
        Ordered list of IP addresses (one per node).  Prefix length
        defaults to /24 unless an address already contains ``/``.
    prefix_len:
        Default prefix length used when not embedded in the address string.
    """

    def __init__(
        self,
        ip_list: Sequence[str],
        prefix_len: int = 24,
    ) -> None:
        self._ip_list: list[str] = list(ip_list)
        self._prefix_len = prefix_len
        self._fds: dict[str, int] = {}   # if_name -> open file descriptor
        self._configured: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup(self) -> dict[str, str]:
        """Create all TUN interfaces and install routing rules.

        Returns
        -------
        dict[str, str]
            Mapping of interface name -> IP address for caller to pass to NS-3.

        Raises
        ------
        PermissionError
            If CAP_NET_ADMIN is not available.
        RuntimeError
            If an ``ip`` command fails.
        """
        _require_net_admin()

        mapping: dict[str, str] = {}
        for i, addr in enumerate(self._ip_list):
            if_name = f"{_TUN_PREFIX}{i}"
            cidr = addr if "/" in addr else f"{addr}/{self._prefix_len}"
            bare_ip = cidr.split("/")[0]

            fd = self._create_tun(if_name)
            self._fds[if_name] = fd

            self._run(["ip", "link", "set", if_name, "up"])
            self._run(["ip", "addr", "add", cidr, "dev", if_name])

            # Policy routing: route traffic FROM bare_ip via table i+1
            table_out = _OUTBOUND_TABLE_BASE + i
            table_lo = _LOOPBACK_TABLE_BASE + i
            self._run(["ip", "rule", "add", "from", bare_ip, "table", str(table_out)])
            self._run(["ip", "route", "add", "default", "dev", if_name, "table", str(table_out)])
            # Loopback rule for return traffic to bare_ip
            self._run(["ip", "rule", "add", "to", bare_ip, "table", str(table_lo)])
            self._run(["ip", "route", "add", cidr, "dev", if_name, "table", str(table_lo)])

            mapping[if_name] = bare_ip
            logger.info("TUN created: %s <-> %s", if_name, cidr)

        self._configured = True
        return mapping

    def teardown(self) -> None:
        """Remove all TUN interfaces and routing rules (idempotent).

        Safe to call even if ``setup()`` was never invoked or partially failed.
        """
        for i, addr in enumerate(self._ip_list):
            if_name = f"{_TUN_PREFIX}{i}"
            bare_ip = addr.split("/")[0]
            table_out = _OUTBOUND_TABLE_BASE + i
            table_lo = _LOOPBACK_TABLE_BASE + i

            # Remove routing rules — ignore errors (may not exist)
            self._run_ignore(["ip", "rule", "del", "from", bare_ip, "table", str(table_out)])
            self._run_ignore(["ip", "rule", "del", "to", bare_ip, "table", str(table_lo)])

            # Close file descriptor; kernel removes the interface automatically
            fd = self._fds.pop(if_name, None)
            if fd is not None:
                try:
                    os.close(fd)
                    logger.info("TUN removed: %s", if_name)
                except OSError as e:
                    logger.warning("Error closing TUN fd for %s: %s", if_name, e)

        self._configured = False

    def get_fd(self, if_name: str) -> int | None:
        """Return the open file descriptor for *if_name*, if configured."""
        return self._fds.get(if_name)

    def if_names(self) -> list[str]:
        """Return interface names in order matching *ip_list*."""
        return [f"{_TUN_PREFIX}{i}" for i in range(len(self._ip_list))]

    def __enter__(self) -> "TunManager":
        self.setup()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.teardown()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_tun(if_name: str) -> int:
        """Open /dev/net/tun and register *if_name*.  Returns the open fd."""
        try:
            fd = os.open("/dev/net/tun", os.O_RDWR)
        except OSError as e:
            raise PermissionError(
                f"Cannot open /dev/net/tun: {e}. "
                "CORNET requires CAP_NET_ADMIN to create TUN interfaces."
            ) from e
        flags = IFF_TUN | IFF_NO_PI
        ifreq = struct.pack("16sH14x", if_name.encode("ascii"), flags)
        try:
            fcntl.ioctl(fd, TUNSETIFF, ifreq)
        except OSError as e:
            os.close(fd)
            raise RuntimeError(
                f"TUNSETIFF ioctl failed for {if_name}: {e}"
            ) from e
        return fd

    @staticmethod
    def _run(args: list[str]) -> None:
        result = subprocess.run(args, capture_output=True, text=True)  # noqa: S603
        if result.returncode != 0:
            raise RuntimeError(
                f"Command {args!r} failed (rc={result.returncode}): {result.stderr.strip()}"
            )

    @staticmethod
    def _run_ignore(args: list[str]) -> None:
        """Run a command, swallowing all errors."""
        try:
            subprocess.run(args, capture_output=True)  # noqa: S603
        except Exception:
            pass


# ------------------------------------------------------------------
# Capability check
# ------------------------------------------------------------------

def _require_net_admin() -> None:
    """Raise PermissionError if process does not appear to have CAP_NET_ADMIN."""
    # Effective UID 0 always has it
    if os.geteuid() == 0:
        return
    # Check /proc/self/status for CapEff containing bit 12 (CAP_NET_ADMIN)
    try:
        status = Path("/proc/self/status").read_text()
        for line in status.splitlines():
            if line.startswith("CapEff:"):
                cap_eff = int(line.split(":")[1].strip(), 16)
                if cap_eff & (1 << 12):
                    return
                break
    except Exception:
        pass
    raise PermissionError(
        "CORNET TunManager requires CAP_NET_ADMIN. "
        "Run with 'sudo' or grant the capability: "
        "sudo setcap cap_net_admin+ep $(which python3)"
    )
