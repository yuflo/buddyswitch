"""Hard runtime boundary for BuddySwitch unit tests."""

from __future__ import annotations

import sys

import pytest


_POLICY_ACTIVE = 0


def _unit_runtime_audit(event: str, _args: tuple[object, ...]) -> None:
    if not _POLICY_ACTIVE:
        return
    if event == "subprocess.Popen":
        raise RuntimeError("unit tests cannot start child processes")
    if event == "socket.bind":
        raise RuntimeError("unit tests cannot bind listeners")


sys.addaudithook(_unit_runtime_audit)


@pytest.fixture(autouse=True)
def _enforce_process_free_unit_runtime() -> object:
    global _POLICY_ACTIVE
    _POLICY_ACTIVE += 1
    try:
        yield
    finally:
        _POLICY_ACTIVE -= 1
