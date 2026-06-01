#!/usr/bin/env bash
set -euo pipefail

BUDDYSWITCH_APP_SERVER_HELPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUDDYSWITCH_APP_SERVER_HELPER="${BUDDYSWITCH_APP_SERVER_HELPER_DIR}/app_server.py"

buddyswitch_app_server_default_socket() {
  printf '%s/runtime/app-server.sock\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

buddyswitch_app_server_pid_file() {
  printf '%s/runtime/app-server.pid\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

buddyswitch_app_server_log_file() {
  printf '%s/runtime/app-server.log\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

buddyswitch_app_server_socket_marker_file() {
  printf '%s/runtime/app-server.socket\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

_buddyswitch_app_server_effective_socket() {
  local marker_path marker_value default_socket fallback_socket
  marker_path="$(buddyswitch_app_server_socket_marker_file)"
  if [[ -f "${marker_path}" ]]; then
    marker_value="$(cat "${marker_path}" 2>/dev/null || true)"
    if [[ -n "${marker_value}" ]]; then
      printf '%s\n' "${marker_value}"
      return 0
    fi
  fi
  default_socket="$(buddyswitch_app_server_default_socket)"
  if [[ ${#default_socket} -lt 104 ]]; then
    printf '%s\n' "${default_socket}"
    return 0
  fi
  fallback_socket="$(python3 - "${BUDDYSWITCH_ACTOR_ID}" <<'PY'
import hashlib
import os
import sys

actor_id = sys.argv[1]
digest = hashlib.sha1(actor_id.encode("utf-8")).hexdigest()[:12]
tmp_root = os.path.realpath("/tmp") if os.path.exists("/tmp") else os.path.realpath(os.getenv("TMPDIR", "/tmp"))
print(os.path.join(tmp_root, "buddyswitch-app-server", f"buddyswitch-app-server-{digest}.sock"))
PY
)"
  printf '%s\n' "${fallback_socket}"
}

buddyswitch_app_server_socket() {
  _buddyswitch_app_server_effective_socket
}

_buddyswitch_app_server_json_field() {
  local payload="$1"
  local field_name="$2"
  python3 - "${payload}" "${field_name}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
field_name = sys.argv[2]
value = payload.get(field_name)
if value is None:
    raise SystemExit(0)
if isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
PY
}

_buddyswitch_app_server_status_json() {
  local socket_path pid_file marker_file log_file
  socket_path="$(_buddyswitch_app_server_effective_socket)"
  pid_file="$(buddyswitch_app_server_pid_file)"
  marker_file="$(buddyswitch_app_server_socket_marker_file)"
  log_file="$(buddyswitch_app_server_log_file)"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" status \
    --socket "${socket_path}" \
    --pid-file "${pid_file}" \
    --marker-file "${marker_file}" \
    --log-file "${log_file}"
}

buddyswitch_app_server_status_json() {
  _buddyswitch_app_server_status_json
}

buddyswitch_app_server_is_active() {
  _buddyswitch_app_server_status_json >/dev/null
}

buddyswitch_app_server_ensure() {
  local output socket_path app_server_pid app_server_log active_role tmp_prefix
  active_role="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"
  if [[ -n "${BUDDYSWITCH_INSTANCE_TMP:-}" ]]; then
    tmp_prefix="${BUDDYSWITCH_INSTANCE_TMP}/zsh"
  else
    tmp_prefix="${TMPPREFIX:-}"
  fi
  output="$(
    TMPDIR="${BUDDYSWITCH_INSTANCE_TMP:-${TMPDIR:-}}" \
    TMP="${BUDDYSWITCH_INSTANCE_TMP:-${TMP:-}}" \
    TEMP="${BUDDYSWITCH_INSTANCE_TMP:-${TEMP:-}}" \
    TMPPREFIX="${tmp_prefix}" \
    HOME="${BUDDYSWITCH_HOME}" \
    CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
    XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
    BUDDYSWITCH_ROLE_ID="${active_role}" \
    BUDDYSWITCH_ACTOR_PRIVATE_DIR="${BUDDYSWITCH_ACTOR_PRIVATE_DIR:-${BUDDYSWITCH_WORKSPACE_DIR}/private}" \
    BUDDYSWITCH_ACTOR_ID="${BUDDYSWITCH_ACTOR_ID}" \
    BUDDYSWITCH_INSTANCE_JSON="${BUDDYSWITCH_INSTANCE_JSON}" \
    BUDDYSWITCH_INSTANCE_TMP="${BUDDYSWITCH_INSTANCE_TMP:-}" \
    BUDDYSWITCH_PROJECT_WORKSPACE_DIR="${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}" \
    BUDDYSWITCH_RUNTIME_BROKER_SOCKET="${BUDDYSWITCH_RUNTIME_BROKER_SOCKET:-}" \
    python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" ensure \
      --actor-id "${BUDDYSWITCH_ACTOR_ID}" \
      --instance-root "${BUDDYSWITCH_INSTANCE_ROOT}"
  )" || {
    if [[ -n "${output:-}" ]]; then
      echo "${output}" >&2
    fi
    return 1
  }
  socket_path="$(_buddyswitch_app_server_json_field "${output}" "socket_path")"
  app_server_pid="$(_buddyswitch_app_server_json_field "${output}" "pid")"
  app_server_log="$(_buddyswitch_app_server_json_field "${output}" "log_file")"
  if [[ -z "${socket_path}" || -z "${app_server_pid}" || -z "${app_server_log}" ]]; then
    echo "App-server ensure did not return required fields." >&2
    if [[ -n "${output}" ]]; then
      echo "${output}" >&2
    fi
    return 1
  fi
  export BUDDYSWITCH_APP_SERVER_SOCKET="${socket_path}"
  export BUDDYSWITCH_APP_SERVER_PID="${app_server_pid}"
  export BUDDYSWITCH_APP_SERVER_LOG="${app_server_log}"
  printf '%s\n' "${output}"
}

buddyswitch_app_server_stop() {
  local socket_path pid_file marker_file log_file
  socket_path="$(_buddyswitch_app_server_effective_socket)"
  pid_file="$(buddyswitch_app_server_pid_file)"
  marker_file="$(buddyswitch_app_server_socket_marker_file)"
  log_file="$(buddyswitch_app_server_log_file)"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" stop \
    --socket "${socket_path}" \
    --pid-file "${pid_file}" \
    --marker-file "${marker_file}" \
    --log-file "${log_file}" >/dev/null
  unset BUDDYSWITCH_APP_SERVER_SOCKET
  unset BUDDYSWITCH_APP_SERVER_PID
  unset BUDDYSWITCH_APP_SERVER_LOG
}

buddyswitch_app_server_thread_start() {
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" thread-start \
    --socket "$(buddyswitch_app_server_socket)" \
    --workspace-dir "${BUDDYSWITCH_WORKSPACE_DIR}" \
    --shared-project-workspace-dir "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}" \
    --permissions "buddyswitch-runtime"
}

buddyswitch_app_server_thread_clear() {
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" thread-start \
    --socket "$(buddyswitch_app_server_socket)" \
    --workspace-dir "${BUDDYSWITCH_WORKSPACE_DIR}" \
    --shared-project-workspace-dir "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}" \
    --permissions "buddyswitch-runtime" \
    --session-start-source "clear"
}

buddyswitch_app_server_thread_resume() {
  local thread_id="$1"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" thread-resume \
    --socket "$(buddyswitch_app_server_socket)" \
    --thread-id "${thread_id}" \
    --workspace-dir "${BUDDYSWITCH_WORKSPACE_DIR}" \
    --shared-project-workspace-dir "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}" \
    --permissions "buddyswitch-runtime"
}

buddyswitch_app_server_thread_bootstrap() {
  local thread_id="$1"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" thread-bootstrap \
    --socket "$(buddyswitch_app_server_socket)" \
    --thread-id "${thread_id}" \
    --timeout-seconds "${BUDDYSWITCH_THREAD_BOOTSTRAP_TIMEOUT_SECONDS:-30}"
}

buddyswitch_app_server_thread_read() {
  local thread_id="$1"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" thread-read \
    --socket "$(buddyswitch_app_server_socket)" \
    --thread-id "${thread_id}"
}

buddyswitch_app_server_input() {
  local thread_id="$1"
  local text="$2"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" input \
    --socket "$(buddyswitch_app_server_socket)" \
    --thread-id "${thread_id}" \
    --text "${text}" \
    --permissions "buddyswitch-runtime"
}

buddyswitch_app_server_side_start() {
  local parent_thread_id="$1"
  local text="$2"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" side-start \
    --socket "$(buddyswitch_app_server_socket)" \
    --parent-thread-id "${parent_thread_id}" \
    --text "${text}" \
    --workspace-dir "${BUDDYSWITCH_WORKSPACE_DIR}" \
    --shared-project-workspace-dir "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}" \
    --permissions "buddyswitch-runtime"
}

buddyswitch_app_server_interrupt() {
  local thread_id="$1"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" interrupt \
    --socket "$(buddyswitch_app_server_socket)" \
    --thread-id "${thread_id}"
}

buddyswitch_app_server_side_close() {
  local side_thread_id="$1"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" side-close \
    --socket "$(buddyswitch_app_server_socket)" \
    --side-thread-id "${side_thread_id}"
}

buddyswitch_app_server_goal_get() {
  local thread_id="$1"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" goal-get \
    --socket "$(buddyswitch_app_server_socket)" \
    --thread-id "${thread_id}"
}

buddyswitch_app_server_goal_set() {
  local thread_id="$1"
  local objective="${2:-}"
  local status="${3:-}"
  local token_budget="${4:-}"
  local -a command=(
    python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" goal-set
    --socket "$(buddyswitch_app_server_socket)"
    --thread-id "${thread_id}"
  )
  if [[ -n "${objective}" ]]; then
    command+=(--objective "${objective}")
  fi
  if [[ -n "${status}" ]]; then
    command+=(--status "${status}")
  fi
  if [[ -n "${token_budget}" ]]; then
    command+=(--token-budget "${token_budget}")
  fi
  "${command[@]}"
}

buddyswitch_app_server_goal_clear() {
  local thread_id="$1"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" goal-clear \
    --socket "$(buddyswitch_app_server_socket)" \
    --thread-id "${thread_id}"
}

buddyswitch_app_server_compact() {
  local thread_id="$1"
  python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" compact \
    --socket "$(buddyswitch_app_server_socket)" \
    --thread-id "${thread_id}"
}
