from __future__ import annotations

from dataclasses import dataclass, field
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from typing import IO, Any, Mapping, Sequence
import uuid

import buddyswitch.foundation.process_runtime.process_identity as process_identity


POLL_INTERVAL = 0.02
VALID_CLEANUP_STRATEGIES = frozenset(
    {
        "central_daemon_stop",
        "instance_daemon_stop",
        "runtime_broker_stop",
        "app_server_stop",
        "browser_stop",
        "terminate_owned_pgid",
        "git_worktree_remove",
    }
)


class SystemLock:
    def __init__(self, path: Path) -> None:
        self.path = Path(path).resolve(strict=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        self._locked = False

    @classmethod
    def for_repo(cls, repo_root: Path) -> "SystemLock":
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"cannot resolve Git common directory: {completed.stderr.strip()}"
            )
        common_dir = Path(completed.stdout.strip())
        if not common_dir.is_absolute():
            common_dir = Path(repo_root) / common_dir
        return cls(common_dir / "buddyswitch-test-system.lock")

    def acquire(self, *, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._locked = True
                return
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"system test lock is held: {self.path}")
                time.sleep(POLL_INTERVAL)

    def release(self) -> None:
        if self._fd < 0:
            return
        if self._locked:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            self._locked = False
        os.close(self._fd)
        self._fd = -1


def process_start_identity(pid: int) -> str | None:
    return process_identity.start_identity(pid)


def _wait_for_start_identity(pid: int, timeout: float = 1.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        identity = process_start_identity(pid)
        if identity is not None:
            return identity
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"could not read start identity for PID {pid}")


def _pid_matches(pid: int, expected_start_identity: str) -> bool:
    return process_identity.matches(
        process_identity.RecordedProcess(pid, expected_start_identity)
    )


def _process_is_running(pid: int, expected_start_identity: str) -> bool:
    return process_identity.is_running(
        process_identity.RecordedProcess(pid, expected_start_identity)
    )


def _reap_if_child(pid: int) -> None:
    process_identity.reap_if_child(pid)


def _wait_for_identity_exit(pid: int, identity: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _reap_if_child(pid)
        if not _process_is_running(pid, identity):
            return True
        time.sleep(POLL_INTERVAL)
    _reap_if_child(pid)
    return not _process_is_running(pid, identity)


@dataclass
class CleanupReport:
    terminated_pids: list[int] = field(default_factory=list)
    killed_pids: list[int] = field(default_factory=list)
    identity_mismatches: list[int] = field(default_factory=list)
    removed_paths: list[str] = field(default_factory=list)
    residuals: list[str] = field(default_factory=list)


class ResourceMonitor:
    def __init__(self, ledger: "ResourceLedger", *, poll_interval: float = 0.05) -> None:
        self.ledger = ledger
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._error: BaseException | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="buddyswitch-test-resource-monitor",
            daemon=True,
        )

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self.ledger.reconcile_descriptors()
                self._stop.wait(self.poll_interval)
            self.ledger.reconcile_descriptors()
        except BaseException as exc:
            self._error = exc

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        if self._thread.is_alive():
            raise RuntimeError("resource monitor did not stop")
        if self._error is not None:
            raise RuntimeError(f"resource monitor failed: {self._error}") from self._error


class ResourceLedger:
    def __init__(self, path: Path, run_root: Path) -> None:
        self.path = Path(path).resolve(strict=False)
        self.run_root = Path(run_root).resolve(strict=False)
        if self.path != self.run_root / "owned-resources.jsonl":
            raise ValueError("resource ledger must be the canonical file under the run root")
        if not self.run_root.is_dir():
            raise ValueError(f"run root does not exist: {self.run_root}")
        self.path.touch(exist_ok=True)

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "ResourceLedger":
        values = os.environ if environ is None else environ
        return cls(
            Path(values["BUDDYSWITCH_TEST_RESOURCE_LEDGER"]),
            Path(values["BUDDYSWITCH_TEST_RUN_ROOT"]),
        )

    def _append(self, record: Mapping[str, Any]) -> None:
        payload = (json.dumps(dict(record), ensure_ascii=True, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            written = os.write(fd, payload)
            if written != len(payload):
                raise OSError(f"short resource-ledger write: {written}/{len(payload)}")
            os.fsync(fd)
        finally:
            os.close(fd)

    def records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"invalid resource-ledger line {line_number}: {exc}"
                ) from exc
            if not isinstance(payload, dict):
                raise RuntimeError(f"resource-ledger line {line_number} is not an object")
            records.append(payload)
        return records

    def register_process(
        self,
        *,
        pid: int,
        pgid: int,
        start_identity: str,
        command: Sequence[str],
        cleanup_strategy: str,
        cleanup_args: Mapping[str, Any],
        descriptor_id: str | None = None,
    ) -> None:
        if cleanup_strategy not in VALID_CLEANUP_STRATEGIES:
            raise ValueError(f"unsupported cleanup strategy: {cleanup_strategy}")
        record: dict[str, Any] = {
            "kind": "process",
            "pid": pid,
            "pgid": pgid,
            "start_identity": start_identity,
            "command": list(command),
            "cleanup_strategy": cleanup_strategy,
            "cleanup_args": dict(cleanup_args),
        }
        if descriptor_id is not None:
            record["descriptor_id"] = descriptor_id
        self._append(record)

    def register_path(self, path: Path, *, path_type: str) -> None:
        resolved = Path(path).resolve(strict=False)
        if not self._path_is_cleanup_safe(resolved):
            raise ValueError(f"owned path is outside exact cleanup roots: {resolved}")
        if resolved == self.path:
            raise ValueError("the active ledger cannot be registered as an owned path")
        self._append(
            {
                "kind": "path",
                "path": str(resolved),
                "path_type": path_type,
            }
        )

    def register_cleanup_action(
        self,
        *,
        cleanup_strategy: str,
        cleanup_args: Mapping[str, Any],
    ) -> None:
        if cleanup_strategy not in VALID_CLEANUP_STRATEGIES:
            raise ValueError(f"unsupported cleanup strategy: {cleanup_strategy}")
        if cleanup_strategy == "terminate_owned_pgid":
            raise ValueError("terminate_owned_pgid requires an exact process record")
        self._append(
            {
                "kind": "cleanup_action",
                "cleanup_strategy": cleanup_strategy,
                "cleanup_args": dict(cleanup_args),
            }
        )

    def _path_is_cleanup_safe(self, path: Path) -> bool:
        if path != self.run_root and path.is_relative_to(self.run_root):
            return True
        temp_roots = {
            Path("/tmp").resolve(strict=False),
            Path("/private/tmp").resolve(strict=False),
            Path(tempfile.gettempdir()).resolve(strict=False),
        }
        return any(
            path != temp_root
            and path.is_relative_to(temp_root)
            and any(part.startswith("buddyswitch-") for part in path.parts)
            for temp_root in temp_roots
        )

    def register_process_descriptor(
        self,
        *,
        pid_file: Path,
        cleanup_strategy: str,
        cleanup_args: Mapping[str, Any],
        command: Sequence[str],
        owned_paths: Mapping[str, Path],
    ) -> str:
        if cleanup_strategy not in VALID_CLEANUP_STRATEGIES:
            raise ValueError(f"unsupported cleanup strategy: {cleanup_strategy}")
        descriptor_id = uuid.uuid4().hex
        resolved_pid_file = Path(pid_file).resolve(strict=False)
        registered_paths: set[Path] = set()
        for path_type, path in owned_paths.items():
            self.register_path(path, path_type=path_type)
            registered_paths.add(Path(path).resolve(strict=False))
        identity_path = process_identity.identity_file(resolved_pid_file).resolve(
            strict=False
        )
        if identity_path not in registered_paths:
            self.register_path(identity_path, path_type="pid_identity")
        self._append(
            {
                "kind": "process_descriptor",
                "descriptor_id": descriptor_id,
                "pid_file": str(resolved_pid_file),
                "cleanup_strategy": cleanup_strategy,
                "cleanup_args": dict(cleanup_args),
                "command": list(command),
            }
        )
        return descriptor_id

    def reconcile_descriptors(self) -> None:
        records = self.records()
        captured = {
            (
                str(record["descriptor_id"]),
                int(record["pid"]),
                str(record["start_identity"]),
            )
            for record in records
            if record.get("kind") == "process" and record.get("descriptor_id")
        }
        for descriptor in records:
            if descriptor.get("kind") != "process_descriptor":
                continue
            descriptor_id = str(descriptor["descriptor_id"])
            pid_file = Path(str(descriptor["pid_file"])).resolve(strict=False)
            recorded = process_identity.read_record(pid_file)
            if recorded is None or not process_identity.matches(recorded):
                continue
            pid = recorded.pid
            identity = recorded.start_identity
            process_key = (descriptor_id, pid, identity)
            if process_key in captured:
                continue
            try:
                pgid = os.getpgid(pid)
            except ProcessLookupError:
                continue
            self.register_process(
                pid=pid,
                pgid=pgid,
                start_identity=identity,
                command=[str(value) for value in descriptor.get("command", [])],
                cleanup_strategy=str(descriptor["cleanup_strategy"]),
                cleanup_args=dict(descriptor.get("cleanup_args", {})),
                descriptor_id=descriptor_id,
            )
            captured.add(process_key)

    def start_process(
        self,
        command: Sequence[str],
        *,
        cwd: Path | str | None = None,
        env: Mapping[str, str] | None = None,
        stdin: int | IO[Any] | None = subprocess.DEVNULL,
        stdout: int | IO[Any] | None = None,
        stderr: int | IO[Any] | None = None,
        text: bool = True,
        start_new_session: bool = True,
        cleanup_strategy: str = "terminate_owned_pgid",
        cleanup_args: Mapping[str, Any] | None = None,
    ) -> subprocess.Popen[str]:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=None if env is None else dict(env),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            text=text,
            start_new_session=start_new_session,
        )
        try:
            identity = _wait_for_start_identity(process.pid)
            pgid = os.getpgid(process.pid)
            self.register_process(
                pid=process.pid,
                pgid=pgid,
                start_identity=identity,
                command=list(command),
                cleanup_strategy=cleanup_strategy,
                cleanup_args={} if cleanup_args is None else cleanup_args,
            )
        except BaseException:
            try:
                if start_new_session:
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
            process.wait()
            raise
        return process

    def _dispatch_normal_stop(self, record: Mapping[str, Any], report: CleanupReport) -> None:
        strategy = record["cleanup_strategy"]
        if strategy == "terminate_owned_pgid":
            return
        args = dict(record.get("cleanup_args", {}))
        owner = (
            f"PID {record['pid']}"
            if "pid" in record
            else "serialized cleanup action"
        )
        try:
            if strategy == "central_daemon_stop":
                from buddyswitch.launcher import central_daemon
                from buddyswitch.launcher import central_daemon_core

                paths = central_daemon_core.central_daemon_paths(
                    Path(str(args["shared_root"]))
                )
                result = central_daemon.stop_central_daemon(paths)
            elif strategy == "instance_daemon_stop":
                from buddyswitch.launcher import daemon_core

                result = daemon_core.stop_daemon(Path(str(args["instance_json"])))
            elif strategy == "runtime_broker_stop":
                from buddyswitch.foundation.runtime_broker import lifecycle

                result = lifecycle.stop_broker(
                    lifecycle.BrokerPaths(
                        socket_path=Path(str(args["socket_path"])),
                        pid_file=Path(str(args["pid_file"])),
                        marker_file=Path(str(args["marker_file"])),
                        log_file=Path(str(args["log_file"])),
                    )
                )
            elif strategy == "app_server_stop":
                from buddyswitch.launcher import app_server

                result = app_server.stop_app_server(
                    Path(str(args["socket_path"])),
                    Path(str(args["pid_file"])),
                    Path(str(args["marker_file"])),
                    Path(str(args["log_file"])),
                )
            elif strategy == "browser_stop":
                from buddyswitch.foundation.browser_runtime import runtime as browser_runtime_manager

                result = browser_runtime_manager.release(
                    instance_root=Path(str(args["instance_root"])),
                    actor_id=str(args["actor_id"]),
                    reason="test_supervisor_cleanup",
                )
            elif strategy == "git_worktree_remove":
                repo_root = Path(str(args["repo_root"]))
                worktree = Path(str(args["worktree"])).resolve(strict=False)
                listed = subprocess.run(
                    ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                registered = {
                    Path(line.removeprefix("worktree ")).resolve(strict=False)
                    for line in listed.stdout.splitlines()
                    if line.startswith("worktree ")
                }
                if listed.returncode == 0 and worktree not in registered:
                    result = {"ok": True, "removed": False}
                else:
                    completed = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(repo_root),
                            "worktree",
                            "remove",
                            "--force",
                            str(worktree),
                        ],
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    result = {
                        "ok": completed.returncode == 0,
                        "error": completed.stderr.strip(),
                    }
            else:
                raise ValueError(f"unsupported cleanup strategy: {strategy}")
        except Exception as exc:
            report.residuals.append(
                f"normal cleanup strategy {strategy} failed for {owner}: {exc}"
            )
            return
        if not isinstance(result, dict) or result.get("ok") is not True:
            report.residuals.append(
                f"normal cleanup strategy {strategy} returned failure for {owner}: {result!r}"
            )

    def _cleanup_process(
        self,
        record: Mapping[str, Any],
        report: CleanupReport,
        *,
        term_timeout: float,
        kill_timeout: float,
    ) -> None:
        pid = int(record["pid"])
        pgid = int(record["pgid"])
        identity = str(record["start_identity"])
        current_identity = process_start_identity(pid)
        if current_identity is None:
            _reap_if_child(pid)
            return
        if current_identity != identity:
            report.identity_mismatches.append(pid)
            return

        self._dispatch_normal_stop(record, report)
        if not _process_is_running(pid, identity):
            _reap_if_child(pid)
            return
        try:
            current_pgid = os.getpgid(pid)
        except ProcessLookupError:
            _reap_if_child(pid)
            return
        if current_pgid != pgid:
            report.residuals.append(
                f"refused changed process group for PID {pid}: "
                f"recorded={pgid} current={current_pgid}"
            )
            return
        if current_pgid == os.getpgrp():
            report.residuals.append(
                f"refused runner process group for PID {pid}: pgid={current_pgid}"
            )
            return
        try:
            os.killpg(pgid, signal.SIGTERM)
            report.terminated_pids.append(pid)
        except ProcessLookupError:
            _reap_if_child(pid)
            return
        except PermissionError as exc:
            report.residuals.append(
                f"cannot terminate owned process group {pgid} for PID {pid}: {exc}"
            )
            return
        if _wait_for_identity_exit(pid, identity, term_timeout):
            return
        if not _process_is_running(pid, identity):
            return
        try:
            current_pgid = os.getpgid(pid)
        except ProcessLookupError:
            _reap_if_child(pid)
            return
        if current_pgid != pgid:
            report.residuals.append(
                f"refused changed process group for PID {pid}: "
                f"recorded={pgid} current={current_pgid}"
            )
            return
        if current_pgid == os.getpgrp():
            report.residuals.append(
                f"refused runner process group for PID {pid}: pgid={current_pgid}"
            )
            return
        try:
            os.killpg(pgid, signal.SIGKILL)
            report.killed_pids.append(pid)
        except ProcessLookupError:
            _reap_if_child(pid)
            return
        except PermissionError as exc:
            report.residuals.append(
                f"cannot kill owned process group {pgid} for PID {pid}: {exc}"
            )
            return
        if not _wait_for_identity_exit(pid, identity, kill_timeout):
            report.residuals.append(
                f"owned process remains: pid={pid} pgid={pgid} identity={identity}"
            )

    def _cleanup_path(self, record: Mapping[str, Any], report: CleanupReport) -> None:
        path = Path(str(record["path"])).resolve(strict=False)
        if not self._path_is_cleanup_safe(path):
            report.residuals.append(f"refused unsafe owned path: {path}")
            return
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        except FileNotFoundError:
            return
        except OSError as exc:
            report.residuals.append(f"failed to remove owned path {path}: {exc}")
            return
        if path.exists() or path.is_symlink():
            report.residuals.append(f"owned path remains: {path}")
        else:
            report.removed_paths.append(str(path))

    def cleanup_registered_process(
        self,
        pid: int,
        *,
        expected_pgid: int | None = None,
        term_timeout: float = 2.0,
        kill_timeout: float = 1.0,
    ) -> CleanupReport:
        """Clean one live process only when this ledger owns its exact identity."""

        report = CleanupReport()
        self.reconcile_descriptors()
        records = [
            record
            for record in self.records()
            if record.get("kind") == "process" and int(record["pid"]) == pid
        ]
        if not records:
            report.residuals.append(
                f"refused process missing from exact ledger: pid={pid}"
            )
            return report

        current_identity = process_start_identity(pid)
        if current_identity is None:
            _reap_if_child(pid)
            return report
        record = next(
            (
                candidate
                for candidate in reversed(records)
                if str(candidate["start_identity"]) == current_identity
            ),
            None,
        )
        if record is None:
            report.identity_mismatches.append(pid)
            return report
        if expected_pgid is not None and int(record["pgid"]) != expected_pgid:
            report.residuals.append(
                f"refused unexpected process group for PID {pid}: "
                f"ledger={record['pgid']} expected={expected_pgid}"
            )
            return report

        self._cleanup_process(
            record,
            report,
            term_timeout=term_timeout,
            kill_timeout=kill_timeout,
        )
        return report

    def cleanup(
        self,
        *,
        term_timeout: float = 2.0,
        kill_timeout: float = 1.0,
    ) -> CleanupReport:
        report = CleanupReport()
        self.reconcile_descriptors()
        records = self.records()
        seen_processes: set[tuple[int, str]] = set()
        # Direct runner children are registered before services they spawn. Stop
        # those owners first so detached descendants are reparented and can be
        # reaped after their exact process group is terminated.
        for record in records:
            if record.get("kind") != "process":
                continue
            key = (int(record["pid"]), str(record["start_identity"]))
            if key in seen_processes:
                continue
            seen_processes.add(key)
            self._cleanup_process(
                record,
                report,
                term_timeout=term_timeout,
                kill_timeout=kill_timeout,
            )
        for record in reversed(records):
            if record.get("kind") == "cleanup_action":
                self._dispatch_normal_stop(record, report)
        seen_paths: set[str] = set()
        for record in reversed(records):
            if record.get("kind") != "path":
                continue
            path = str(record["path"])
            if path in seen_paths:
                continue
            seen_paths.add(path)
            self._cleanup_path(record, report)
        return report


def run_process(
    command: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    input: str | bytes | None = None,
    stdin: int | IO[Any] | None = None,
    stdout: int | IO[Any] | None = None,
    stderr: int | IO[Any] | None = None,
    capture_output: bool = False,
    text: bool = False,
    timeout: float | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[Any]:
    """Run one exact ledger-owned child with subprocess.run-compatible basics."""

    if input is not None and stdin is not None:
        raise ValueError("stdin and input arguments may not both be used")
    if capture_output and (stdout is not None or stderr is not None):
        raise ValueError("stdout and stderr arguments may not be used with capture_output")
    if capture_output:
        stdout = subprocess.PIPE
        stderr = subprocess.PIPE
    if input is not None:
        stdin = subprocess.PIPE

    ledger = ResourceLedger.from_environment()
    process = ledger.start_process(
        command,
        cwd=cwd,
        env=env,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        text=text,
    )
    try:
        captured_stdout, captured_stderr = process.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        captured_stdout, captured_stderr = process.communicate()
        exc.stdout = captured_stdout
        exc.stderr = captured_stderr
        raise
    finally:
        ledger.reconcile_descriptors()

    completed = subprocess.CompletedProcess(
        list(command),
        process.returncode,
        captured_stdout,
        captured_stderr,
    )
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            completed.args,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed
