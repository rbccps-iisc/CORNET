#!/usr/bin/env python3
"""cornet-bridge-ros1 — ROS 1 bridge for CORNET physics clock and positions.

Subscribes to:
    /clock                (rosgraph_msgs/Clock)      → sends physics time to ClockServer
    /gazebo/model_states  (gazebo_msgs/ModelStates)  → sends model positions to PositionServer

This is the ONLY file in the cornet package that imports rospy.
Install with:  pip install cornet[ros1]
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sys

logger = logging.getLogger("cornet.bridge.ros1")

_CLOCK_SOCK = os.environ.get("CORNET_CLOCK_SOCKET", "/tmp/cornet_clock.sock")
_POS_SOCK = os.environ.get("CORNET_POSITIONS_SOCKET", "/tmp/cornet_positions.sock")


def _connect_uds(path: str) -> socket.socket:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    return s


def _send_json(sock: socket.socket, data: dict) -> None:
    sock.sendall((json.dumps(data) + "\n").encode())


def main() -> int:
    try:
        import rospy  # noqa: PLC0415
        from rosgraph_msgs.msg import Clock  # noqa: PLC0415
        from gazebo_msgs.msg import ModelStates  # noqa: PLC0415
    except ImportError:
        print(
            "ERROR: rospy not found. Install ROS 1 and 'pip install cornet[ros1]'.",
            file=sys.stderr,
        )
        return 1

    clock_sock = _connect_uds(_CLOCK_SOCK)
    pos_sock = _connect_uds(_POS_SOCK)

    rospy.init_node("cornet_ros1_bridge", anonymous=False)

    def clock_cb(msg: "Clock") -> None:
        t = msg.clock.secs + msg.clock.nsecs * 1e-9
        try:
            _send_json(clock_sock, {"t": t})
        except OSError as e:
            rospy.logwarn(f"Clock socket write error: {e}")

    def model_states_cb(msg: "ModelStates") -> None:
        for name, pose in zip(msg.name, msg.pose):
            try:
                _send_json(
                    pos_sock,
                    {
                        "name": name,
                        "x": pose.position.x,
                        "y": pose.position.y,
                        "z": pose.position.z,
                    },
                )
            except OSError as e:
                rospy.logwarn(f"Position socket write error: {e}")

    rospy.Subscriber("/clock", Clock, clock_cb, queue_size=100)
    rospy.Subscriber("/gazebo/model_states", ModelStates, model_states_cb, queue_size=100)
    rospy.loginfo(
        "CORNET ROS 1 bridge started (clock=%s pos=%s)", _CLOCK_SOCK, _POS_SOCK
    )
    try:
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    finally:
        clock_sock.close()
        pos_sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
