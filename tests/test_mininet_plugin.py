from __future__ import annotations

import sys
import types

import pytest

from cornet.config.loader import load_unified
from cornet.context import ExperimentContext
from cornet.plugins.network.mininet_plugin import MininetPlugin


def _write_config(tmp_path, network_block: str):
    path = tmp_path / "config.yaml"
    path.write_text(
        "\n".join(
            [
                "_schema: unified-v1",
                "network:",
                network_block,
                "robot:",
                "  plugin: gazebo",
                "  robots: []",
                "experiment:",
                "  name: test",
                "  duration: 0.0",
                "  output_dir: tmp/results",
            ]
        )
    )
    return load_unified(path)


class _FakeNode:
    def __init__(self, name: str, ip: str) -> None:
        self._name = name
        self._ip = ip

    def IP(self) -> str:
        return self._ip


class _FakeNet:
    def __init__(self, kind: str, *args, **kwargs) -> None:
        self.kind = kind
        self.calls: list[tuple[str, str, dict]] = []
        self.nodes: dict[str, _FakeNode] = {}

    def addDocker(self, name: str, **kwargs):
        self.calls.append(("addDocker", name, kwargs))
        self.nodes[name] = _FakeNode(name, kwargs.get("ip", "10.0.0.2"))

    def addStation(self, name: str, **kwargs):
        self.calls.append(("addStation", name, kwargs))
        self.nodes[name] = _FakeNode(name, kwargs.get("ip", "10.0.0.2"))

    def addAP(self, name: str, **kwargs):
        self.calls.append(("addAP", name, kwargs))
        self.nodes[name] = _FakeNode(name, "10.0.0.1")

    def addHost(self, name: str, **kwargs):
        self.calls.append(("addHost", name, kwargs))
        self.nodes[name] = _FakeNode(name, kwargs.get("ip", "10.0.0.3"))

    def addController(self, name: str):
        self.calls.append(("addController", name, {}))

    def setPropagationModel(self, **kwargs):
        self.calls.append(("setPropagationModel", "", kwargs))

    def build(self):
        self.calls.append(("build", "", {}))

    def start(self):
        self.calls.append(("start", "", {}))

    def stop(self):
        self.calls.append(("stop", "", {}))

    def get(self, name: str):
        return self.nodes.get(name)


def test_containernet_path_uses_adddocker(monkeypatch, tmp_path) -> None:
    cfg = _write_config(
        tmp_path,
        "\n".join(
            [
                "  plugin: mininet",
                "  type: mininet",
                "  nodes:",
                "    - name: ap0",
                "      type: STATIC",
                "      ip: 10.0.0.1",
                "    - name: uav0",
                "      type: MOBILE",
                "      ip: 10.0.0.2",
                "      container:",
                "        image: ubuntu:22.04",
                "        cpu_quota: 0.5",
                "        mem_limit_mb: 512",
            ]
        ),
    )

    fake_module = types.ModuleType("containernet.net")
    fake_module.Containernet = lambda *args, **kwargs: _FakeNet("containernet")
    monkeypatch.setitem(sys.modules, "containernet", types.ModuleType("containernet"))
    monkeypatch.setitem(sys.modules, "containernet.net", fake_module)
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: types.SimpleNamespace(returncode=0, stderr=b""))

    plugin = MininetPlugin()
    plugin.configure(cfg, ExperimentContext(variant_id="test"))
    plugin.start()

    assert plugin._use_containernet is True
    docker_calls = [call for call in plugin._net.calls if call[0] == "addDocker"]
    assert docker_calls == [
        (
            "addDocker",
            "uav0",
            {
                "dimage": "ubuntu:22.04",
                "ip": "10.0.0.2",
                "cpu_quota": 0.5,
                "mem_limit": "512m",
            },
        )
    ]


def test_wifi_only_path_uses_mininet_wifi(monkeypatch, tmp_path) -> None:
    cfg = _write_config(
        tmp_path,
        "\n".join(
            [
                "  plugin: mininet",
                "  type: mininet",
                "  mininet:",
                "    wmediumd: true",
                "    ssid: cornet-net",
                "  nodes:",
                "    - name: ap0",
                "      type: STATIC",
                "      ip: 10.0.0.1",
                "    - name: sta0",
                "      type: MOBILE",
                "      ip: 10.0.0.2",
            ]
        ),
    )

    fake_net_mod = types.ModuleType("mn_wifi.net")
    fake_link_mod = types.ModuleType("mn_wifi.link")
    fake_link_mod.wmediumd = object()
    fake_net_mod.Mininet_wifi = lambda *args, **kwargs: _FakeNet("mininet")
    monkeypatch.setitem(sys.modules, "mn_wifi", types.ModuleType("mn_wifi"))
    monkeypatch.setitem(sys.modules, "mn_wifi.net", fake_net_mod)
    monkeypatch.setitem(sys.modules, "mn_wifi.link", fake_link_mod)

    plugin = MininetPlugin()
    plugin.configure(cfg, ExperimentContext(variant_id="test"))
    plugin.start()

    assert plugin._use_containernet is False
    assert any(call[0] == "addStation" for call in plugin._net.calls)
    assert any(call[0] == "setPropagationModel" for call in plugin._net.calls)


def test_containernet_missing_raises_actionable_error(tmp_path) -> None:
    cfg = _write_config(
        tmp_path,
        "\n".join(
            [
                "  plugin: mininet",
                "  type: mininet",
                "  nodes:",
                "    - name: node0",
                "      type: MOBILE",
                "      container:",
                "        image: ubuntu:22.04",
            ]
        ),
    )

    plugin = MininetPlugin()
    with pytest.raises(ImportError, match="containernet not installed"):
        plugin.configure(cfg, ExperimentContext(variant_id="test"))