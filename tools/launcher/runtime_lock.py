#!/usr/bin/env python3
"""Run a command while holding the BuddySwitch runtime lock."""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import math
import os
import signal
import struct
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_TIMEOUT_SECONDS = 30.0
LOCK_WAIT_POLL_SECONDS = 0.05
BUSY_EXIT_CODE = 4
TIMEOUT_ENV = "BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"
SHARED_ROOT_ENV = "BUDDYSWITCH_SHARED_ROOT"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Acquire the BuddySwitch runtime lock and run a command while holding it."
    )
    parser.add_argument(
        "--shared-root",
        default=os.environ.get(SHARED_ROOT_ENV),
        help=f"Runtime shared root path (default: ${SHARED_ROOT_ENV})",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help=f"Lock wait timeout in seconds (default: ${TIMEOUT_ENV} or {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--assert-held",
        action="store_true",
        help="Verify the current process inherited the runtime lock context.",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run while holding the lock.")
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if args.assert_held and args.command:
        parser.error("--assert-held does not accept a command")
    if not args.assert_held and not args.command:
        parser.error("a command is required")
    return args


def resolve_timeout(timeout_override: float | None) -> float:
    if timeout_override is not None:
        timeout = timeout_override
    else:
        raw_timeout = os.environ.get(TIMEOUT_ENV)
        if raw_timeout is None or raw_timeout.strip() == "":
            timeout = DEFAULT_TIMEOUT_SECONDS
        else:
            try:
                timeout = float(raw_timeout)
            except ValueError as exc:
                raise ValueError(f"invalid {TIMEOUT_ENV} value: {raw_timeout!r}") from exc
    if not math.isfinite(timeout):
        raise ValueError(f"timeout must be finite, got {timeout}")
    if timeout < 0:
        raise ValueError(f"timeout must be >= 0, got {timeout}")
    return timeout


def normalize_shared_root(raw_shared_root: str | None) -> str:
    if raw_shared_root is None:
        raise ValueError(f"{SHARED_ROOT_ENV} is required")
    shared_root = raw_shared_root.rstrip("/")
    if not shared_root:
        raise ValueError(f"{SHARED_ROOT_ENV} must not be empty")
    return shared_root


def runtime_lock_dir(shared_root: str) -> Path:
    return Path(shared_root) / "run" / "locks"


def runtime_lock_path(shared_root: str) -> Path:
    return runtime_lock_dir(shared_root) / "runtime.lock"


def runtime_owner_lock_path(shared_root: str) -> Path:
    return runtime_lock_dir(shared_root) / "runtime.owner.lock"


def acquire_owner_lock(lock_fd: int, lock_path: Path) -> int:
    try:
        fcntl.lockf(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"runtime state busy: owner lock is already held at {lock_path}", file=sys.stderr)
        return BUSY_EXIT_CODE
    return 0


def write_lock_owner(lock_fd: int) -> int | None:
    if sys.platform == "darwin":
        request = struct.pack("qqihh", 0, 0, 0, fcntl.F_WRLCK, os.SEEK_SET)
        response = fcntl.fcntl(lock_fd, fcntl.F_GETLK, request)
        _start, _length, pid, lock_type, _whence = struct.unpack("qqihh", response[: struct.calcsize("qqihh")])
    else:
        request = struct.pack("hhqqi", fcntl.F_WRLCK, os.SEEK_SET, 0, 0, 0)
        response = fcntl.fcntl(lock_fd, fcntl.F_GETLK, request)
        lock_type, _whence, _start, _length, pid = struct.unpack("hhqqi", response[: struct.calcsize("hhqqi")])
    if lock_type == fcntl.F_UNLCK:
        return None
    return int(pid)


def darwin_parent_process_id(pid: int) -> int | None:
    if sys.platform != "darwin":
        return None
    buffer = ctypes.create_string_buffer(4096)
    try:
        libc = ctypes.CDLL("libc.dylib", use_errno=True)
        result = libc.proc_pidinfo(ctypes.c_int(pid), ctypes.c_int(3), ctypes.c_uint64(0), buffer, len(buffer))
    except (AttributeError, OSError):
        return None
    if result < struct.calcsize("IIIII"):
        return None
    try:
        _flags, _status, _xstatus, _pid, ppid = struct.unpack_from("IIIII", buffer.raw)
    except struct.error:
        return None
    return int(ppid)


def parent_process_id(pid: int) -> int | None:
    darwin_ppid = darwin_parent_process_id(pid)
    if darwin_ppid is not None:
        return darwin_ppid

    proc_stat = Path("/proc") / str(pid) / "stat"
    try:
        stat_text = proc_stat.read_text(encoding="utf-8")
        stat_fields = stat_text.rsplit(") ", 1)[1].split()
        return int(stat_fields[1])
    except (OSError, IndexError, ValueError):
        pass

    try:
        output = subprocess.check_output(
            ["ps", "-o", "ppid=", "-p", str(pid)],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    output_lines = output.strip().splitlines()
    if not output_lines:
        return None
    try:
        return int(output_lines[0].strip())
    except ValueError:
        return None


def process_is_descendant_of(pid: int, ancestor_pid: int) -> bool:
    current_pid = pid
    seen: set[int] = set()
    while current_pid > 0 and current_pid not in seen:
        if current_pid == ancestor_pid:
            return True
        seen.add(current_pid)
        parent_pid = parent_process_id(current_pid)
        if parent_pid is None:
            return False
        current_pid = parent_pid
    return False


def acquire_runtime_lock(lock_fd: int, lock_path: Path, timeout_seconds: float) -> int:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return 0
        except BlockingIOError:
            if time.monotonic() >= deadline:
                print(
                    f"runtime state busy: could not acquire lock at {lock_path} within {timeout_seconds:.2f}s",
                    file=sys.stderr,
                )
                return BUSY_EXIT_CODE
            time.sleep(LOCK_WAIT_POLL_SECONDS)


def run_with_lock(shared_root: str, timeout_seconds: float, command: list[str]) -> int:
    lock_path = runtime_lock_path(shared_root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    owner_lock_path = runtime_owner_lock_path(shared_root)
    owner_lock_fd: int | None = None
    child: subprocess.Popen[bytes] | None = None
    received_signal: int | None = None
    try:
        lock_result = acquire_runtime_lock(lock_fd, lock_path, timeout_seconds)
        if lock_result != 0:
            return lock_result
        owner_lock_fd = os.open(owner_lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        owner_lock_result = acquire_owner_lock(owner_lock_fd, owner_lock_path)
        if owner_lock_result != 0:
            return owner_lock_result
        child_env = os.environ.copy()

        def forward_signal(signum: int, _frame: object) -> None:
            nonlocal received_signal
            received_signal = signum
            if child is None or child.poll() is not None:
                return
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass

        previous_handlers = {
            signal.SIGTERM: signal.getsignal(signal.SIGTERM),
            signal.SIGINT: signal.getsignal(signal.SIGINT),
            signal.SIGHUP: signal.getsignal(signal.SIGHUP),
        }
        for signum in previous_handlers:
            signal.signal(signum, forward_signal)
        try:
            child = subprocess.Popen(command, env=child_env, start_new_session=True)
            return_code = child.wait()
        finally:
            for signum, previous_handler in previous_handlers.items():
                signal.signal(signum, previous_handler)

        if received_signal is not None:
            return 128 + received_signal
        return return_code
    finally:
        if owner_lock_fd is not None:
            os.close(owner_lock_fd)
        os.close(lock_fd)


def assert_runtime_lock_held(shared_root: str) -> int:
    try:
        owner_lock_fd = os.open(runtime_owner_lock_path(shared_root), os.O_RDWR)
    except OSError as exc:
        print(f"runtime lock required: could not open lock context: {exc}", file=sys.stderr)
        return 2
    try:
        try:
            runtime_owner = write_lock_owner(owner_lock_fd)
        except OSError as exc:
            print(f"runtime lock required: could not inspect lock owner: {exc}", file=sys.stderr)
            return 2
    finally:
        os.close(owner_lock_fd)

    if runtime_owner is None:
        print("runtime lock required: runtime lock owner is not locked", file=sys.stderr)
        return 2

    if not process_is_descendant_of(os.getpid(), runtime_owner):
        print("runtime lock required: current process did not inherit runtime lock owner", file=sys.stderr)
        return 2

    lock_path = runtime_lock_path(shared_root)
    try:
        probe_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        print(f"runtime lock required: could not open lock file: {exc}", file=sys.stderr)
        return 2
    try:
        try:
            fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        else:
            fcntl.flock(probe_fd, fcntl.LOCK_UN)
            print("runtime lock required: lock file is not locked", file=sys.stderr)
            return 2
    finally:
        os.close(probe_fd)


def main() -> int:
    try:
        args = parse_args()
        timeout_seconds = resolve_timeout(args.timeout_seconds)
        shared_root = normalize_shared_root(args.shared_root)
    except ValueError as exc:
        print(f"runtime lock configuration error: {exc}", file=sys.stderr)
        return 2
    if args.assert_held:
        return assert_runtime_lock_held(shared_root)
    return run_with_lock(shared_root, timeout_seconds, args.command)


if __name__ == "__main__":
    raise SystemExit(main())
