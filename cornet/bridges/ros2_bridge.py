#!/usr/bin/env python3
"""cornet-bridge-ros2 — ROS 2 bridge for CORNET physics clock and positions.

Subscribes to:
  /clock  (rosgraph_msgs/msg/Clock)   → sends physics time to ClockServer
  /tf     (tf2_msgs/msg/TFMessage)    → sends model positions to PositionServer

This is the ONLY file in the cornet package that imports rclpy.
Install with:  pip install cornet[ros2]
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
import threading

logger = logging.getLogger("cornet.bridge.ros2")

# ------------------------------------------------------------------
# Sockets
# ------------------------------------------------------------------

_CLOCK_SOCK = os.environ.get("CORNET_CLOCK_SOCKET", "/tmp/cornet_clock.sock")
_POS_SOCK = os.environ.get("CORNET_POSITIONS_SOCKET", "/tmp/cornet_positions.sock")


def _connect_uds(path: str) -> socket.socket:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    return s


def _send_json(sock: socket.socket, data: dict) -> None:
    sock.sendall((json.dumps(data) + "\n").encode())


# ------------------------------------------------------------------
# ROS 2 node
# ------------------------------------------------------------------

def main() -> int:
    try:
        import rclpy  # noqa: PLC0415
        from rclpy.node import Node  # noqa: PLC0415
        from rosgraph_msgs.msg import Clock  # noqa: PLC0415
        from tf2_msgs.msg import TFMessage  # noqa: PLC0415
    except ImportError:
        print(
            "ERROR: rclpy not found. Install ROS 2 and 'pip install cornet[ros2]'.",
            file=sys.stderr,
        )
        return 1

    clock_sock = _connect_uds(_CLOCK_SOCK)
    pos_sock = _connect_uds(_POS_SOCK)

    rclpy.init()

    class CORNETBridgeNode(Node):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__("cornet_ros2_bridge")
            self.create_subscription(Clock, "/clock", self._clock_cb, 10)
            self.create_subscription(TFMessage, "/tf", self._tf_cb, 10)
            self.get_logger().info(
                "CORNET ROS 2 bridge started (clock=%s pos=%s)",
                _CLOCK_SOCK,
                _POS_SOCK,
            )

        def _clock_cb(self, msg: "Clock") -> None:
            t = msg.clock.sec + msg.clock.nanosec * 1e-9
            try:
                _send_json(clock_sock, {"t": t})
            except OSError as e:
                self.get_logger().warning(f"Clock socket write error: {e}")

        def _tf_cb(self, msg: "TFMessage") -> None:
            for transform in msg.transforms:
                frame = transform.child_frame_id.lstrip("/")
                tr = transform.transform.translation
                try:
                    _send_json(pos_sock, {"name": frame, "x": tr.x, "y": tr.y, "z": tr.z})
                except OSError as e:
                    self.get_logger().warning(f"Position socket write error: {e}")

    node = CORNETBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        clock_sock.close()
        pos_sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
