"""Exact process-start identity records for safe lifecycle ownership."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys


@dataclass(frozen=True)
class RecordedProcess:
    pid: int
    start_identity: str


class _DarwinProcBsdInfo(ctypes.Structure):
    _fields_ = [
        ("pbi_flags", ctypes.c_uint32),
        ("pbi_status", ctypes.c_uint32),
        ("pbi_xstatus", ctypes.c_uint32),
        ("pbi_pid", ctypes.c_uint32),
        ("pbi_ppid", ctypes.c_uint32),
        ("pbi_uid", ctypes.c_uint32),
        ("pbi_gid", ctypes.c_uint32),
        ("pbi_ruid", ctypes.c_uint32),
        ("pbi_rgid", ctypes.c_uint32),
        ("pbi_svuid", ctypes.c_uint32),
        ("pbi_svgid", ctypes.c_uint32),
        ("rfu_1", ctypes.c_uint32),
        ("pbi_comm", ctypes.c_char * 16),
        ("pbi_name", ctypes.c_char * 32),
        ("pbi_nfiles", ctypes.c_uint32),
        ("pbi_pgid", ctypes.c_uint32),
        ("pbi_pjobc", ctypes.c_uint32),
        ("e_tdev", ctypes.c_uint32),
        ("e_tpgid", ctypes.c_uint32),
        ("pbi_nice", ctypes.c_int32),
        ("pbi_start_tvsec", ctypes.c_uint64),
        ("pbi_start_tvusec", ctypes.c_uint64),
    ]


def _darwin_info(pid: int) -> _DarwinProcBsdInfo | None:
    try:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    except OSError:
        return None
    proc_pidinfo = libproc.proc_pidinfo
    proc_pidinfo.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint64,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    proc_pidinfo.restype = ctypes.c_int
    info = _DarwinProcBsdInfo()
    size = ctypes.sizeof(info)
    result = proc_pidinfo(pid, 3, 0, ctypes.byref(info), size)
    if result != size or info.pbi_pid != pid:
        return None
    return info


def _darwin_start_identity(pid: int) -> str | None:
    info = _darwin_info(pid)
    if info is None:
        return None
    return f"darwin:{info.pbi_start_tvsec}:{info.pbi_start_tvusec}"


def _linux_start_identity(pid: int) -> str | None:
    try:
        raw = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
    except OSError:
        return None
    close_paren = raw.rfind(")")
    if close_paren < 0:
        return None
    fields_after_command = raw[close_paren + 2 :].split()
    if len(fields_after_command) <= 19:
        return None
    return f"linux:{fields_after_command[19]}"


def start_identity(pid: int) -> str | None:
    if pid <= 0:
        return None
    if sys.platform == "darwin":
        return _darwin_start_identity(pid)
    if Path("/proc").is_dir():
        return _linux_start_identity(pid)
    completed = subprocess.run(
        ["ps", "-o", "lstart=", "-p", str(pid)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    value = " ".join(completed.stdout.split())
    return f"ps:{value}" if completed.returncode == 0 and value else None


def identity_file(pid_file: Path) -> Path:
    return Path(f"{pid_file}.identity")


def write_record(pid_file: Path, pid: int) -> RecordedProcess:
    identity = start_identity(pid)
    if identity is None:
        raise RuntimeError(f"cannot read process start identity for PID {pid}")
    record = RecordedProcess(pid=pid, start_identity=identity)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f"{pid}\n", encoding="utf-8")
    identity_file(pid_file).write_text(
        json.dumps(
            {"pid": record.pid, "start_identity": record.start_identity},
            ensure_ascii=True,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return record


def read_record(pid_file: Path) -> RecordedProcess | None:
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        payload = json.loads(identity_file(pid_file).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    identity = payload.get("start_identity")
    recorded_pid = payload.get("pid")
    if recorded_pid != pid or not isinstance(identity, str) or not identity:
        return None
    return RecordedProcess(pid=pid, start_identity=identity)


def matches(record: RecordedProcess) -> bool:
    return start_identity(record.pid) == record.start_identity


def is_running(record: RecordedProcess) -> bool:
    if not matches(record):
        return False
    if sys.platform == "darwin":
        info = _darwin_info(record.pid)
        return info is not None and info.pbi_status != 5
    if Path("/proc").is_dir():
        try:
            raw = (Path("/proc") / str(record.pid) / "stat").read_text(
                encoding="utf-8"
            )
        except OSError:
            return False
        close_paren = raw.rfind(")")
        fields_after_command = raw[close_paren + 2 :].split() if close_paren >= 0 else []
        return bool(fields_after_command and fields_after_command[0] != "Z")
    completed = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(record.pid)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    state = completed.stdout.strip()
    return completed.returncode == 0 and bool(state) and not state.startswith("Z")


def reap_if_child(pid: int) -> None:
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass


def remove_record(pid_file: Path) -> None:
    pid_file.unlink(missing_ok=True)
    identity_file(pid_file).unlink(missing_ok=True)
