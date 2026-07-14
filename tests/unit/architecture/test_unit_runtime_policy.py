"""Runtime enforcement for the process-free unit tier."""

from __future__ import annotations

import socket
import subprocess
import sys

import pytest


def _indirect_child_start() -> None:
    subprocess.run(
        [sys.executable, "-c", "pass"],
        check=True,
        capture_output=True,
        text=True,
    )


def _indirect_listener_bind(listener: socket.socket) -> None:
    listener.bind(("127.0.0.1", 0))


def test_unit_policy_blocks_indirect_child_process_creation() -> None:
    with pytest.raises(RuntimeError, match="unit tests cannot start child processes"):
        _indirect_child_start()


def test_unit_policy_blocks_indirect_listener_binding() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match="unit tests cannot bind listeners"):
            _indirect_listener_bind(listener)
    finally:
        listener.close()
