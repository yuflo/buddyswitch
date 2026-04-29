#!/usr/bin/env python3
"""Run a command while holding the BuddySwitch runtime lock."""

from __future__ import annotations

import argparse
import fcntl
import math
import os
import signal
import secrets
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_TIMEOUT_SECONDS = 30.0
LOCK_WAIT_POLL_SECONDS = 0.05
BUSY_EXIT_CODE = 4
TIMEOUT_ENV = "BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"
SHARED_ROOT_ENV = "BUDDYSWITCH_SHARED_ROOT"
LOCK_PROOF_ENV = "BUDDYSWITCH_RUNTIME_LOCK_PROOF"
LOCK_TOKEN_ENV = "BUDDYSWITCH_RUNTIME_LOCK_TOKEN"


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


def runtime_proof_path(shared_root: str) -> Path:
    return runtime_lock_dir(shared_root) / f"runtime.{os.getpid()}.proof"


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
    proof_path = runtime_proof_path(shared_root)
    child: subprocess.Popen[bytes] | None = None
    received_signal: int | None = None
    try:
        lock_result = acquire_runtime_lock(lock_fd, lock_path, timeout_seconds)
        if lock_result != 0:
            return lock_result
        proof_token = secrets.token_urlsafe(24)
        proof_path.write_text(proof_token, encoding="utf-8")
        os.chmod(proof_path, 0o600)
        child_env = os.environ.copy()
        child_env[LOCK_PROOF_ENV] = str(proof_path)
        child_env[LOCK_TOKEN_ENV] = proof_token

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
        proof_path.unlink(missing_ok=True)
        os.close(lock_fd)


def assert_runtime_lock_held(shared_root: str) -> int:
    proof_path_raw = os.environ.get(LOCK_PROOF_ENV)
    proof_token = os.environ.get(LOCK_TOKEN_ENV)
    if not proof_path_raw or not proof_token:
        print("runtime lock required: missing inherited lock context", file=sys.stderr)
        return 2

    proof_path = Path(proof_path_raw)
    try:
        stored_token = proof_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"runtime lock required: invalid inherited lock context: {exc}", file=sys.stderr)
        return 2

    if not secrets.compare_digest(stored_token, proof_token):
        print("runtime lock required: inherited lock proof mismatch", file=sys.stderr)
        return 2

    lock_path = runtime_lock_path(shared_root)
    probe_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
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
