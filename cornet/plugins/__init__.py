"""Plugin registry: maps string names to Plugin subclasses."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cornet.plugins.base import Plugin


class PluginNotFoundError(KeyError):
    """Raised when a plugin name is not found in the registry."""


# Registry is populated by each plugin module via register()
_REGISTRY: dict[str, type["Plugin"]] = {}


def register(name: str, cls: type["Plugin"]) -> None:
    """Register a plugin class under the given name."""
    _REGISTRY[name] = cls


def get(name: str) -> type["Plugin"]:
    """Return the plugin class for *name*, or raise PluginNotFoundError."""
    if name not in _REGISTRY:
        raise PluginNotFoundError(
            f"Plugin '{name}' not found. Available plugins: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]


def available() -> list[str]:
    """Return sorted list of registered plugin names."""
    return sorted(_REGISTRY)


# ── Eagerly import plugin modules so they self-register ──────────────────────
def _load_builtin_plugins() -> None:
    import importlib

    _BUILTIN = [
        "cornet.plugins.network.mininet_plugin",
        "cornet.plugins.network.ns3_plugin",
        "cornet.plugins.robot.gazebo_plugin",
    ]
    for mod in _BUILTIN:
        try:
            importlib.import_module(mod)
        except ImportError:
            # Optional heavy dependencies (mininet-wifi, etc.) may not be installed
            pass


_load_builtin_plugins()
