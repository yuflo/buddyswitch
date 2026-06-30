#!/usr/bin/env bash
set -euo pipefail

buddyswitch_runtime_broker_socket() {
  local marker_path default_path
  marker_path="$(buddyswitch_runtime_broker_socket_marker_file)"
  if [[ -f "${marker_path}" ]]; then
    cat "${marker_path}"
    return 0
  fi
  default_path="${BUDDYSWITCH_INSTANCE_ROOT}/runtime/runtime-broker.sock"
  printf '%s\n' "${default_path}"
}

buddyswitch_runtime_broker_default_socket() {
  printf '%s/runtime/runtime-broker.sock\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

buddyswitch_runtime_broker_pid_file() {
  printf '%s/runtime/runtime-broker.pid\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

buddyswitch_runtime_broker_log_file() {
  printf '%s/runtime/runtime-broker.log\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

buddyswitch_runtime_broker_socket_marker_file() {
  printf '%s/runtime/runtime-broker.socket\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

_buddyswitch_runtime_broker_manifest_path() {
  local manifest_path
  if [[ -n "${BUDDYSWITCH_MANIFEST_PATH:-}" ]]; then
    manifest_path="${BUDDYSWITCH_MANIFEST_PATH}"
  else
    manifest_path="${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/manifest.toml"
  fi
  if [[ ! -f "${manifest_path}" ]]; then
    echo "Runtime broker manifest missing in workspace: ${manifest_path}" >&2
    return 1
  fi
  printf '%s\n' "${manifest_path}"
}

_buddyswitch_runtime_broker_script_path() {
  local broker_script
  broker_script="${BUDDYSWITCH_WORKSPACE_DIR}/scripts/runtime_kernel/broker.py"
  if [[ ! -f "${broker_script}" ]]; then
    echo "Runtime broker script missing in workspace: ${broker_script}" >&2
    return 1
  fi
  printf '%s\n' "${broker_script}"
}

_buddyswitch_runtime_broker_effective_socket() {
  local default_socket marker_path marker_value fallback_socket
  marker_path="$(buddyswitch_runtime_broker_socket_marker_file)"
  default_socket="$(buddyswitch_runtime_broker_default_socket)"
  if [[ -f "${marker_path}" ]]; then
    marker_value="$(cat "${marker_path}" 2>/dev/null || true)"
    if [[ -n "${marker_value}" ]]; then
      printf '%s\n' "${marker_value}"
      return 0
    fi
  fi
  if [[ ${#default_socket} -lt 100 ]]; then
    printf '%s\n' "${default_socket}"
    return 0
  fi
  fallback_socket="$(python3 - "${BUDDYSWITCH_ACTOR_ID}" <<'PY'
import hashlib
import sys
actor_id = sys.argv[1]
digest = hashlib.sha1(actor_id.encode("utf-8")).hexdigest()[:12]
print(f"/tmp/buddyswitch-runtime-{digest}.sock")
PY
)"
  printf '%s\n' "${fallback_socket}"
}

_buddyswitch_runtime_broker_lifecycle_json() {
  # lifecycle commands: status ensure stop
  local command="$1"
  local socket_path="$2"
  local pid_file="$3"
  local marker_file="$4"
  local log_file="$5"
  local broker_script manifest_path
  broker_script="$(_buddyswitch_runtime_broker_script_path)" || return 1
  manifest_path="$(_buddyswitch_runtime_broker_manifest_path)" || return 1
  (
    cd "${BUDDYSWITCH_WORKSPACE_DIR}"
    export BUDDYSWITCH_STATE_ROOT="${BUDDYSWITCH_SHARED_ROOT}/state"
    python3 "${broker_script}" "${command}" \
      --socket "${socket_path}" \
      --pid-file "${pid_file}" \
      --marker-file "${marker_file}" \
      --log-file "${log_file}" \
      --instance-json "${BUDDYSWITCH_INSTANCE_JSON}" \
      --manifest "${manifest_path}" \
      --repo-root "${BUDDYSWITCH_REPO_ROOT}"
  )
}

_buddyswitch_runtime_broker_cleanup_local_files() {
  local socket_path="$1"
  local pid_file="$2"
  local marker_file="$3"
  rm -f "${pid_file}" "${marker_file}" "${socket_path}" >/dev/null 2>&1 || true
}

_buddyswitch_runtime_broker_lifecycle_available() {
  local manifest_path
  if [[ -z "${BUDDYSWITCH_WORKSPACE_DIR:-}" || ! -d "${BUDDYSWITCH_WORKSPACE_DIR}" ]]; then
    return 1
  fi
  if [[ ! -f "${BUDDYSWITCH_WORKSPACE_DIR}/scripts/runtime_kernel/broker.py" ]]; then
    return 1
  fi
  if [[ -n "${BUDDYSWITCH_MANIFEST_PATH:-}" ]]; then
    manifest_path="${BUDDYSWITCH_MANIFEST_PATH}"
  else
    manifest_path="${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/manifest.toml"
  fi
  [[ -f "${manifest_path}" ]]
}

buddyswitch_runtime_broker_is_active() {
  local socket_path pid_file marker_path log_file
  socket_path="$(_buddyswitch_runtime_broker_effective_socket)"
  pid_file="$(buddyswitch_runtime_broker_pid_file)"
  marker_path="$(buddyswitch_runtime_broker_socket_marker_file)"
  log_file="$(buddyswitch_runtime_broker_log_file)"
  _buddyswitch_runtime_broker_lifecycle_json "status" "${socket_path}" "${pid_file}" "${marker_path}" "${log_file}" >/dev/null
}

buddyswitch_runtime_broker_status_json() {
  local socket_path pid_file marker_path log_file output
  socket_path="$(_buddyswitch_runtime_broker_effective_socket)"
  pid_file="$(buddyswitch_runtime_broker_pid_file)"
  marker_path="$(buddyswitch_runtime_broker_socket_marker_file)"
  log_file="$(buddyswitch_runtime_broker_log_file)"
  if output="$(_buddyswitch_runtime_broker_lifecycle_json "status" "${socket_path}" "${pid_file}" "${marker_path}" "${log_file}" 2>/dev/null)"; then
    printf '%s\n' "${output}"
    return 0
  fi
  if [[ -n "${output:-}" ]]; then
    printf '%s\n' "${output}"
    return 0
  fi
  python3 - "${socket_path}" "${pid_file}" "${marker_path}" "${log_file}" <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

socket_path, pid_file, marker_path, log_file = (Path(value) for value in sys.argv[1:5])

def log_metadata(path: Path) -> dict[str, object]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"path": str(path), "exists": False, "size_bytes": 0, "mtime": None, "last_event": None}
    last_event = None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("service"), str) and isinstance(payload.get("event"), str):
                last_event = payload
    except OSError:
        last_event = None
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "last_event": last_event,
    }

print(json.dumps({
    "ok": False,
    "protocol": None,
    "pid": None,
    "pid_live": False,
    "socket_path": str(socket_path),
    "marker_path": str(marker_path),
    "marker_value": None,
    "log_file": str(log_file),
    "log": log_metadata(log_file),
    "healthy": False,
    "error": {
        "code": "E_RUNTIME_BROKER_UNAVAILABLE",
        "message": "runtime broker status unavailable",
        "retriable": True,
    },
}, ensure_ascii=True))
PY
}

buddyswitch_runtime_broker_ensure() {
  local socket_path pid_file log_file marker_path output ensured_socket
  socket_path="$(_buddyswitch_runtime_broker_effective_socket)"
  pid_file="$(buddyswitch_runtime_broker_pid_file)"
  log_file="$(buddyswitch_runtime_broker_log_file)"
  marker_path="$(buddyswitch_runtime_broker_socket_marker_file)"
  output="$(_buddyswitch_runtime_broker_lifecycle_json "ensure" "${socket_path}" "${pid_file}" "${marker_path}" "${log_file}")" || {
    if [[ -n "${output:-}" ]]; then
      echo "${output}" >&2
    fi
    return 1
  }
  ensured_socket="$(python3 - "${output}" <<'PY'
import json
import sys
try:
    payload = json.loads(sys.argv[1])
except json.JSONDecodeError:
    print("")
    raise SystemExit(0)
value = payload.get("socket_path")
print(value.strip() if isinstance(value, str) else "")
PY
)"
  if [[ -z "${ensured_socket}" ]]; then
    echo "Runtime broker ensure did not return socket_path." >&2
    if [[ -n "${output}" ]]; then
      echo "${output}" >&2
    fi
    return 1
  fi
  export BUDDYSWITCH_RUNTIME_BROKER_SOCKET="${ensured_socket}"
}

buddyswitch_runtime_broker_stop() {
  local socket_path pid_file marker_path log_file output
  socket_path="$(_buddyswitch_runtime_broker_effective_socket)"
  pid_file="$(buddyswitch_runtime_broker_pid_file)"
  marker_path="$(buddyswitch_runtime_broker_socket_marker_file)"
  log_file="$(buddyswitch_runtime_broker_log_file)"
  if ! _buddyswitch_runtime_broker_lifecycle_available; then
    _buddyswitch_runtime_broker_cleanup_local_files "${socket_path}" "${pid_file}" "${marker_path}"
    unset BUDDYSWITCH_RUNTIME_BROKER_SOCKET
    return 0
  fi
  output="$(_buddyswitch_runtime_broker_lifecycle_json "stop" "${socket_path}" "${pid_file}" "${marker_path}" "${log_file}")" || {
    if [[ -n "${output:-}" ]]; then
      echo "${output}" >&2
    fi
    _buddyswitch_runtime_broker_cleanup_local_files "${socket_path}" "${pid_file}" "${marker_path}"
    unset BUDDYSWITCH_RUNTIME_BROKER_SOCKET
    return 0
  }
  unset BUDDYSWITCH_RUNTIME_BROKER_SOCKET
}
