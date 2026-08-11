#!/usr/bin/env bash
set -euo pipefail

HOST_CONTROL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_CONTROL_SELF="${HOST_CONTROL_DIR}/host_control.sh"
ENV_HELPER="${HOST_CONTROL_DIR}/env.sh"
BROWSER_HELPER="${HOST_CONTROL_DIR}/browser_cockpit.sh"
APP_SERVER_HELPER="${HOST_CONTROL_DIR}/../../foundation/app_server/shell/app_server.sh"
DAEMON_HELPER="${HOST_CONTROL_DIR}/daemon.sh"
RUNTIME_BROKER_HELPER="${HOST_CONTROL_DIR}/runtime_broker.sh"

source "${ENV_HELPER}"
source "${BROWSER_HELPER}"
source "${APP_SERVER_HELPER}"
source "${DAEMON_HELPER}"
source "${RUNTIME_BROKER_HELPER}"

buddyswitch_env_init

host_control_error_code_for_status() {
  case "${1:-1}" in
    2)
      printf '%s\n' "INVALID_REQUEST"
      ;;
    3)
      printf '%s\n' "LIFECYCLE_BLOCKED"
      ;;
    4)
      printf '%s\n' "LOCK_BUSY"
      ;;
    5)
      printf '%s\n' "RUNTIME_MISMATCH"
      ;;
    *)
      printf '%s\n' "COMMAND_FAILED"
      ;;
  esac
}

host_control_emit_error_json() {
  local code="$1" message="$2"
  "${BUDDYSWITCH_PYTHON}" - "${code}" "${message}" <<'PY'
import json
import sys

print(json.dumps({"error": {"code": sys.argv[1], "message": sys.argv[2]}}, ensure_ascii=True))
PY
}

host_control_output_has_error_json() {
  local output="$1"
  if "${BUDDYSWITCH_PYTHON}" - "${output}" >/dev/null 2>&1 <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
error = payload.get("error") if isinstance(payload, dict) else None
raise SystemExit(0 if isinstance(error, dict) else 1)
PY
  then
    return 0
  fi
  return 1
}

host_control_emit_error_for_output() {
  local status="$1" output="$2" code
  if host_control_output_has_error_json "${output}"; then
    printf '%s\n' "${output}"
    return 0
  fi
  code="$(host_control_error_code_for_status "${status}")"
  host_control_emit_error_json "${code}" "${output:-Host control operation failed.}"
}

host_control_require_internal_dispatch() {
  if [[ "${BUDDYSWITCH_HOST_CONTROL_INTERNAL:-}" != "1" ]]; then
    echo "host control internal operation is not public" >&2
    return 2
  fi
}

host_control_seed_actor_capabilities() {
  local instance_json="$1"
  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" <<'PY'
from pathlib import Path
import sys

from buddyswitch.foundation.actor_runtime import capability as actor_capability

actor_capability.seed_actor_capabilities(Path(sys.argv[1]))
PY
}

buddyswitch_instance_json_files() {
  local instance_json
  for instance_json in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/instance.json; do
    [[ -f "${instance_json}" ]] || continue
    printf '%s\n' "${instance_json}"
  done
}

buddyswitch_instance_list() {
  local role_filter="${1:-}"
  local instance_json meta kind actor_id status_json row_json
  local -a instance_rows=()
  [[ $# -le 1 ]] || {
    echo "list accepts optional <role-id>" >&2
    return 2
  }
  if [[ -n "${role_filter}" ]]; then
    buddyswitch_validate_role_id "${role_filter}" || return $?
  fi

  while IFS= read -r instance_json; do
    meta="$(
      "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${role_filter}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
role_filter = sys.argv[2]

try:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
except FileNotFoundError:
    raise SystemExit(0)
except Exception as exc:
    print(f"invalid\t{instance_json.parent.name}\tinvalid-json:{exc}")
    raise SystemExit(0)

role = payload.get("role")
if role_filter and role != role_filter:
    raise SystemExit(0)

actor_id = payload.get("actor_id", instance_json.parent.name)
print(f"ok\t{actor_id}")
PY
    )"
    [[ -n "${meta}" ]] || continue
    kind="${meta%%$'\t'*}"
    if [[ "${kind}" == "invalid" ]]; then
      actor_id="${meta#*$'\t'}"
      row_json="$(
        "${BUDDYSWITCH_PYTHON}" - "${actor_id%%$'\t'*}" "${actor_id#*$'\t'}" <<'PY'
import json
import sys

payload = {
    "actor_id": sys.argv[1],
    "role": "invalid",
    "status": "invalid",
    "app_server_health": "invalid",
    "thread_id": None,
    "browser_port": None,
    "updated_at": "",
    "workspace_dir": sys.argv[2],
    "last_failure": None,
}
print(json.dumps(payload, ensure_ascii=True))
PY
      )"
      instance_rows+=("${row_json}")
      continue
    fi
    actor_id="${meta#*$'\t'}"
    status_json="$(instance_status_json "${actor_id}")" || return $?
    row_json="$(
      "${BUDDYSWITCH_PYTHON}" - "${status_json}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
app_server = payload.get("app_server")
healthy = False
if isinstance(app_server, dict):
    healthy = bool(app_server.get("healthy"))
thread_id = payload.get("thread_id")
browser_port = payload.get("browser_port")
row = {
    "actor_id": payload.get("actor_id", ""),
    "role": payload.get("role", ""),
    "status": payload.get("status", ""),
    "app_server_health": "healthy" if healthy else "unhealthy",
    "thread_id": thread_id if isinstance(thread_id, str) else None,
    "browser_port": browser_port if isinstance(browser_port, int) else None,
    "updated_at": payload.get("updated_at", ""),
    "workspace_dir": payload.get("workspace_dir", ""),
    "last_failure": payload.get("last_failure"),
}
print(json.dumps(row, ensure_ascii=True))
PY
    )"
    instance_rows+=("${row_json}")
  done < <(buddyswitch_instance_json_files)

  if [[ "${#instance_rows[@]}" -eq 0 ]]; then
    printf '%s\n' '{"instances":[]}'
    return 0
  fi
  "${BUDDYSWITCH_PYTHON}" - "${instance_rows[@]}" <<'PY'
import json
import sys

rows = [json.loads(arg) for arg in sys.argv[1:]]
print(json.dumps({"instances": rows}, ensure_ascii=True))
PY
}

buddyswitch_instance_record_json() {
  local actor_id="$1"
  local instance_json

  buddyswitch_validate_actor_id "${actor_id}" || return $?
  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"
  if [[ ! -f "${instance_json}" ]]; then
    host_control_emit_error_json "NOT_FOUND" "Instance not found: ${actor_id}" >&2
    return 6
  fi
  printf '%s\n' "${instance_json}"
}

buddyswitch_instance_record_field() {
  local actor_id="$1"
  local field_name="$2"
  local instance_json

  instance_json="$(buddyswitch_instance_record_json "${actor_id}")" || return $?
  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${actor_id}" "${field_name}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
field_name = sys.argv[3]
payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    print(f"Actor id mismatch in {instance_json}", file=sys.stderr)
    raise SystemExit(2)
value = payload.get(field_name)
if value is None:
    raise SystemExit(0)
print(value)
PY
}

buddyswitch_instance_validate_record() {
  local actor_id="$1"
  local instance_json

  instance_json="$(buddyswitch_instance_record_json "${actor_id}")" || return $?
  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${actor_id}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    print(f"Actor id mismatch in {instance_json}", file=sys.stderr)
    raise SystemExit(2)
role = payload.get("role")
if not isinstance(role, str) or not role:
    print(f"Instance record missing role: {instance_json}", file=sys.stderr)
    raise SystemExit(2)
print(role)
PY
}

buddyswitch_instance_require_safe_delete_root() {
  local actor_id="$1"
  local instances_root="${BUDDYSWITCH_SHARED_ROOT}/instances"
  local instance_root
  local normalized_instances_root normalized_instance_root

  if [[ -L "${BUDDYSWITCH_SHARED_ROOT}" ]]; then
    echo "Instance delete blocked: unsafe shared root for ${actor_id}." >&2
    return 3
  fi

  instance_root="$(buddyswitch_instance_root "${actor_id}")"
  if [[ -L "${instances_root}" || -L "${instance_root}" ]]; then
    echo "Instance delete blocked: unsafe instance root for ${actor_id}." >&2
    return 3
  fi
  if [[ -d "${instance_root}" ]]; then
    normalized_instances_root="$(buddyswitch_canonical_path "${instances_root}")"
    normalized_instance_root="$(buddyswitch_canonical_path "${instance_root}")"
    case "${normalized_instance_root}" in
      "${normalized_instances_root}/"*)
        ;;
      *)
        echo "Instance delete blocked: unsafe instance root for ${actor_id}." >&2
        return 3
        ;;
    esac
  fi

  printf '%s\n' "${instance_root}"
}

start_codex() {
  local role="${1:-}" codex_bin="${2:-}" codex_version="${3:-}" requested_actor_id="${4:-}"
  local actor_id instance_json bootstrap_stdout bootstrap_status diagnostics_file

  actor_id=""
  instance_json=""
  if [[ $# -ne 4 ]]; then
    echo "start requires <role-id> <codex-executable> <codex-version> <actor-id>" >&2
    return 2
  fi
  if [[ -z "${role}" || "${role}" == -* ]]; then
    echo "Invalid role id: ${role}" >&2
    return 2
  fi

  buddyswitch_validate_role_id "${role}" || return $?
  if [[ "${codex_bin}" != /* || ! -x "${codex_bin}" || -z "${codex_version}" ]]; then
    echo "start requires a valid Codex runtime descriptor" >&2
    return 2
  fi
  buddyswitch_validate_actor_id "${requested_actor_id}" || return $?
  actor_id="${requested_actor_id}"
  buddyswitch_env_bind_instance "${actor_id}" || return $?
  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"

  diagnostics_file="$(mktemp "${TMPDIR:-/tmp}/buddyswitch-start-diagnostics.XXXXXX")"
  set +e
  bootstrap_stdout="$(
    (
      unset BUDDYSWITCH_ROLE_ID
      unset BUDDYSWITCH_ACTOR_ID
      unset BUDDYSWITCH_INSTANCE_JSON
      BUDDYSWITCH_START_ROLE="${role}" \
      BUDDYSWITCH_START_ACTOR_ID="${actor_id}" \
      BUDDYSWITCH_START_CODEX_BIN="${codex_bin}" \
      BUDDYSWITCH_START_CODEX_VERSION="${codex_version}" \
      BUDDYSWITCH_START_DIAGNOSTICS_FILE="${diagnostics_file}" \
      BUDDYSWITCH_HOST_CONTROL_INTERNAL=1 \
        buddyswitch_with_runtime_lock "${HOST_CONTROL_SELF}" "start-bootstrap-locked"
    )
  )"
  bootstrap_status=$?
  set -e
  if [[ "${bootstrap_status}" -ne 0 ]]; then
    if [[ -n "${bootstrap_stdout}" ]]; then
      printf '%s\n' "${bootstrap_stdout}" >&2
    fi
    rm -f "${diagnostics_file}"
    return "${bootstrap_status}"
  fi

  "${BUDDYSWITCH_PYTHON}" - "${actor_id}" "${role}" "${BUDDYSWITCH_WORKSPACE_DIR}" "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}" "${instance_json}" "${diagnostics_file:-}" <<'PY'
import json
import sys
from pathlib import Path

diagnostics_path = Path(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] else None
diagnostics = []
if diagnostics_path is not None and diagnostics_path.is_file():
    diagnostics = [line for line in diagnostics_path.read_text(encoding="utf-8").splitlines() if line.strip()]

payload = {
    "actor_id": sys.argv[1],
    "role": sys.argv[2],
    "workspace_dir": sys.argv[3],
    "project_workspace_dir": sys.argv[4],
    "instance_record": sys.argv[5],
}
if diagnostics:
    payload["diagnostics"] = diagnostics
print(json.dumps(payload, ensure_ascii=True))
PY
  rm -f "${diagnostics_file:-}"
}

buddyswitch_start_failure_cleanup() {
  local actor_id="$1"
  local phase="$2"
  local message="$3"
  local thread_id="${4:-}"
  local browser_port="${5:-}"
  local stop_output=""

  stop_output="$(buddyswitch_daemon_stop 2>&1)" || {
    echo "Warning: daemon stop failed during ${phase} cleanup for ${actor_id}." >&2
    [[ -n "${stop_output}" ]] && echo "${stop_output}" >&2
  }
  stop_output="$(buddyswitch_app_server_stop 2>&1)" || {
    echo "Warning: app-server stop failed during ${phase} cleanup for ${actor_id}." >&2
    [[ -n "${stop_output}" ]] && echo "${stop_output}" >&2
  }
  stop_output="$(buddyswitch_runtime_broker_stop 2>&1)" || {
    echo "Warning: runtime broker stop failed during ${phase} cleanup for ${actor_id}." >&2
    [[ -n "${stop_output}" ]] && echo "${stop_output}" >&2
  }
  stop_output="$(buddyswitch_browser_manager_stop_instance "${actor_id}" 2>&1)" || {
    echo "Warning: browser stop failed during ${phase} cleanup for ${actor_id}." >&2
    [[ -n "${stop_output}" ]] && echo "${stop_output}" >&2
  }
  buddyswitch_instance_record_failure "${actor_id}" "${phase}" "${message}" "${thread_id}" "${browser_port}"
}

BUDDYSWITCH_START_PHASE_OUTPUT=""

buddyswitch_run_published_start_phase() {
  local actor_id="$1" phase="$2" fallback_message="$3" thread_id="$4" browser_port="$5"
  local phase_status message output_file
  shift 5

  BUDDYSWITCH_START_PHASE_OUTPUT=""
  output_file="$(mktemp "${TMPDIR:-/tmp}/buddyswitch-start-phase.XXXXXX")" || return $?
  set +e
  "$@" >"${output_file}" 2>&1
  phase_status=$?
  set -e
  BUDDYSWITCH_START_PHASE_OUTPUT="$(cat "${output_file}")"
  rm -f "${output_file}"
  if [[ "${phase_status}" -eq 0 ]]; then
    return 0
  fi

  message="${BUDDYSWITCH_START_PHASE_OUTPUT:-${fallback_message}}"
  [[ -n "${BUDDYSWITCH_START_PHASE_OUTPUT}" ]] && printf '%s\n' "${BUDDYSWITCH_START_PHASE_OUTPUT}" >&2
  buddyswitch_start_failure_cleanup \
    "${actor_id}" \
    "${phase}" \
    "${message}" \
    "${thread_id}" \
    "${browser_port}"
  return "${phase_status}"
}

host_control_started_thread_id() {
  local thread_json="$1"
  "${BUDDYSWITCH_PYTHON}" - "${thread_json}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
thread = payload.get("thread")
thread_id = thread.get("id") if isinstance(thread, dict) else None
if not isinstance(thread_id, str) or not thread_id:
    print("App-server thread start did not return thread.id.", file=sys.stderr)
    raise SystemExit(1)
print(thread_id)
PY
}

buddyswitch_thread_bootstrap_failure_is_timeout_like() {
  local message="$1"

  [[ "${message}" == *"timed out waiting for thread/inject_items"* ]] ||
    [[ "${message}" == *"timed out waiting for thread/bootstrap"* ]] ||
    [[ "${message}" == *"AppServerTimeout"* ]]
}

buddyswitch_start_thread_bootstrap_with_retry() {
  local thread_id="$1"
  local output retry_output

  BUDDYSWITCH_LAST_THREAD_BOOTSTRAP_ERROR=""
  if output="$(buddyswitch_app_server_thread_bootstrap "${thread_id}" 2>&1)"; then
    return 0
  fi
  BUDDYSWITCH_LAST_THREAD_BOOTSTRAP_ERROR="${output}"
  if ! buddyswitch_thread_bootstrap_failure_is_timeout_like "${output}"; then
    [[ -n "${output}" ]] && echo "${output}" >&2
    return 1
  fi

  echo "Thread bootstrap timed out for ${thread_id}; retrying once." >&2
  if retry_output="$(buddyswitch_app_server_thread_bootstrap "${thread_id}" 2>&1)"; then
    BUDDYSWITCH_LAST_THREAD_BOOTSTRAP_ERROR=""
    return 0
  fi
  BUDDYSWITCH_LAST_THREAD_BOOTSTRAP_ERROR="${retry_output:-${output}}"
  [[ -n "${retry_output}" ]] && echo "${retry_output}" >&2
  return 1
}

start_locked_bootstrap() {
  local requested_role requested_actor_id requested_codex_bin requested_codex_version
  local app_server_json thread_json thread_id browser_output build_json
  buddyswitch_require_runtime_lock || return $?
  requested_role="${BUDDYSWITCH_START_ROLE:-}"
  requested_actor_id="${BUDDYSWITCH_START_ACTOR_ID:-}"
  requested_codex_bin="${BUDDYSWITCH_START_CODEX_BIN:-}"
  requested_codex_version="${BUDDYSWITCH_START_CODEX_VERSION:-}"

  if [[ -z "${requested_role}" ]]; then
    echo "BUDDYSWITCH_START_ROLE is required for product instance bootstrap." >&2
    return 2
  fi
  if [[ -z "${requested_actor_id}" ]]; then
    echo "BUDDYSWITCH_START_ACTOR_ID is required for product instance bootstrap." >&2
    return 2
  fi
  if [[ "${requested_codex_bin}" != /* || ! -x "${requested_codex_bin}" || -z "${requested_codex_version}" ]]; then
    echo "A valid Codex runtime descriptor is required for product instance bootstrap." >&2
    return 2
  fi
  export BUDDYSWITCH_CODEX_BIN="${requested_codex_bin}"
  export BUDDYSWITCH_CODEX_VERSION="${requested_codex_version}"
  buddyswitch_validate_role_id "${requested_role}" || return $?
  buddyswitch_validate_actor_id "${requested_actor_id}" || return $?
  buddyswitch_require_env_profile "${requested_role}" || return $?
  buddyswitch_require_role_agents_template "${requested_role}" || return $?
  buddyswitch_env_bind_instance "${requested_actor_id}" || return $?

  build_json="$(
    "${BUDDYSWITCH_PYTHON}" -m buddyswitch.application.entrypoints.actor_build \
      --project-source "${BUDDYSWITCH_PROJECT_SOURCE}" \
      --shared-root "${BUDDYSWITCH_SHARED_ROOT}" \
      --actor-id "${requested_actor_id}" \
      --role-id "${requested_role}" \
      --source-codex-home "${BUDDYSWITCH_SOURCE_CODEX_HOME}"
  )" || return $?
  "${BUDDYSWITCH_PYTHON}" - "${build_json}" "${BUDDYSWITCH_INSTANCE_ROOT}" "${BUDDYSWITCH_WORKSPACE_DIR}" "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
expected = {
    "actor_root": sys.argv[2],
    "workspace_dir": sys.argv[3],
    "project_workspace_dir": sys.argv[4],
}
for field, value in expected.items():
    if payload.get(field) != value:
        print(f"Actor environment result mismatch for {field}.", file=sys.stderr)
        raise SystemExit(1)
PY
  buddyswitch_instance_activate "${requested_actor_id}" "${requested_role}" "inactive" >/dev/null || return $?
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "capability_seed" "Capability seed failed." "" "" \
    host_control_seed_actor_capabilities "$(buddyswitch_instance_json_path "${requested_actor_id}")" || return $?
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "runtime_broker_ensure" "Runtime broker ensure failed." "" "" \
    buddyswitch_runtime_broker_ensure || return $?
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "codex_config_patch" "Codex config patch failed." "" "" \
    buddyswitch_patch_codex_config || return $?
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "env_mcp_ensure" "Environment MCP ensure failed." "" "" \
    buddyswitch_env_mcp_ensure || return $?
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "browser_register" "Browser cockpit registration failed." "" "" \
    buddyswitch_browser_register_cockpit_mcp || return $?
  browser_output="${BUDDYSWITCH_START_PHASE_OUTPUT}"
  if [[ -n "${browser_output}" ]]; then
    if [[ -n "${BUDDYSWITCH_START_DIAGNOSTICS_FILE:-}" ]]; then
      printf '%s\n' "${browser_output}" >>"${BUDDYSWITCH_START_DIAGNOSTICS_FILE}" || return $?
    else
      printf '%s\n' "${browser_output}" >&2
    fi
  fi
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "app_server_ensure" "App-server ensure failed." "" "" \
    buddyswitch_app_server_ensure || return $?
  app_server_json="${BUDDYSWITCH_START_PHASE_OUTPUT}"
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "thread_start" "thread/start failed." "" "" \
    buddyswitch_app_server_thread_start || return $?
  thread_json="${BUDDYSWITCH_START_PHASE_OUTPUT}"
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "thread_start" "App-server thread start did not return thread.id." "" "" \
    host_control_started_thread_id "${thread_json}" || return $?
  thread_id="${BUDDYSWITCH_START_PHASE_OUTPUT}"
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "thread_bootstrap" "Thread bootstrap failed for ${thread_id}." "${thread_id}" "" \
    buddyswitch_start_thread_bootstrap_with_retry "${thread_id}" || return $?
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "runtime_record" "Instance runtime record failed." "${thread_id}" "" \
    buddyswitch_instance_set_app_server \
    "${requested_actor_id}" \
    "${thread_id}" \
    "$(_buddyswitch_app_server_json_field "${app_server_json}" "pid")" \
    "$(_buddyswitch_app_server_json_field "${app_server_json}" "socket_path")" \
    "$(_buddyswitch_app_server_json_field "${app_server_json}" "log_file")" \
    "active" || return $?
  buddyswitch_run_published_start_phase \
    "${requested_actor_id}" "daemon_start" "Daemon start failed for ${requested_actor_id}." "${thread_id}" "" \
    buddyswitch_daemon_start || return $?
}

instance_set_inactive_locked() {
  local actor_id="${1:-}" daemon_output=""
  buddyswitch_require_runtime_lock || return $?
  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi
  buddyswitch_validate_actor_id "${actor_id}" || return $?
  buddyswitch_env_bind_instance "${actor_id}" || return $?
  daemon_output="$(buddyswitch_daemon_stop 2>&1)" || {
    echo "Warning: daemon stop failed for ${actor_id}." >&2
    [[ -n "${daemon_output}" ]] && echo "${daemon_output}" >&2
  }
  buddyswitch_app_server_stop || true
  buddyswitch_runtime_broker_stop
  buddyswitch_browser_manager_stop_instance "${actor_id}" || true
  buddyswitch_instance_clear_app_server "${actor_id}" "inactive"
}

instance_require_active_service_thread() {
  local actor_id="$1"
  local action_label="$2"
  local thread_id

  buddyswitch_validate_actor_id "${actor_id}" || return $?
  buddyswitch_instance_validate_record "${actor_id}" >/dev/null || return $?
  buddyswitch_env_bind_instance "${actor_id}" || return $?
  thread_id="$(buddyswitch_instance_record_field "${actor_id}" "thread_id" || true)"
  if [[ -z "${thread_id}" ]]; then
    echo "Instance ${action_label} blocked: ${actor_id} has no thread id; stop/delete it and start a new instance." >&2
    return 3
  fi
  if ! buddyswitch_app_server_is_active; then
    echo "Instance ${action_label} blocked: ${actor_id} is unhealthy or inactive." >&2
    return 3
  fi
  INSTANCE_ACTIVE_THREAD_ID="${thread_id}"
}

instance_compact() {
  local actor_id="${1:-}" thread_id output
  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi
  if [[ $# -ne 1 ]]; then
    echo "compact requires <actor-id>" >&2
    return 2
  fi

  instance_require_active_service_thread "${actor_id}" "compact" || return $?
  thread_id="${INSTANCE_ACTIVE_THREAD_ID}"
  output="$(buddyswitch_app_server_compact "${thread_id}" 2>&1)" || {
    [[ -n "${output}" ]] && echo "${output}" >&2
    return 1
  }
  "${BUDDYSWITCH_PYTHON}" - "${output}" "${actor_id}" "${thread_id}" <<'PY'
import json
import sys

json.loads(sys.argv[1])
print(json.dumps({"actor_id": sys.argv[2], "thread_id": sys.argv[3], "started": True}, ensure_ascii=True))
PY
}

instance_clear() {
  local actor_id="${1:-}" previous_thread_id output new_thread_id daemon_output=""
  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi
  if [[ $# -ne 1 ]]; then
    echo "clear requires <actor-id>" >&2
    return 2
  fi

  instance_require_active_service_thread "${actor_id}" "clear" || return $?
  previous_thread_id="${INSTANCE_ACTIVE_THREAD_ID}"
  daemon_output="$(buddyswitch_daemon_stop 2>&1)" || {
    echo "Warning: daemon stop failed for ${actor_id}." >&2
    [[ -n "${daemon_output}" ]] && echo "${daemon_output}" >&2
  }
  output="$(buddyswitch_app_server_thread_clear 2>&1)" || {
    [[ -n "${output}" ]] && echo "${output}" >&2
    return 1
  }
  new_thread_id="$(
    "${BUDDYSWITCH_PYTHON}" - "${output}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
thread = payload.get("thread")
if isinstance(thread, dict):
    thread_id = thread.get("id")
    if isinstance(thread_id, str):
        print(thread_id)
PY
  )"
  if [[ -z "${new_thread_id}" ]]; then
    echo "App-server clear did not return thread.id." >&2
    echo "${output}" >&2
    return 1
  fi
  buddyswitch_instance_set_thread_id "${actor_id}" "${new_thread_id}" || return $?
  if ! buddyswitch_app_server_thread_bootstrap "${new_thread_id}" >/dev/null; then
    echo "Thread bootstrap failed for ${new_thread_id}." >&2
    buddyswitch_app_server_stop || true
    buddyswitch_runtime_broker_stop
    buddyswitch_browser_manager_stop_instance "${actor_id}" || true
    buddyswitch_instance_clear_app_server "${actor_id}" "inactive"
    return 1
  fi
  if ! buddyswitch_daemon_start >/dev/null; then
    echo "Daemon start failed for ${actor_id}." >&2
    buddyswitch_app_server_stop || true
    buddyswitch_runtime_broker_stop
    buddyswitch_browser_manager_stop_instance "${actor_id}" || true
    buddyswitch_instance_clear_app_server "${actor_id}" "inactive"
    return 1
  fi
  "${BUDDYSWITCH_PYTHON}" - "${actor_id}" "${previous_thread_id}" "${new_thread_id}" <<'PY'
import json
import sys

payload = {
    "actor_id": sys.argv[1],
    "previous_thread_id": sys.argv[2],
    "thread_id": sys.argv[3],
}
print(json.dumps(payload, ensure_ascii=True))
PY
}

host_control_validate_recorded_codex_runtime() {
  local actor_id="$1" codex_bin="$2" codex_version="$3"
  if ! "${BUDDYSWITCH_PYTHON}" - \
    "$(buddyswitch_instance_json_path "${actor_id}")" \
    "${codex_bin}" \
    "${codex_version}" \
    <<'PY'
import json
import sys
from pathlib import Path

from buddyswitch.foundation.actor_runtime import codex_runtime

try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    runtime = codex_runtime.runtime_from_instance(payload)
    if str(runtime.executable) != sys.argv[2] or runtime.version != sys.argv[3]:
        raise codex_runtime.CodexRuntimeError(
            "RUNTIME_MISMATCH",
            "Supplied Codex runtime does not match the actor record.",
        )
    codex_runtime.validate_codex_runtime(runtime)
except (OSError, ValueError, codex_runtime.CodexRuntimeError) as exc:
    print(str(exc), file=sys.stderr)
    raise SystemExit(5) from None
PY
  then
    return 5
  fi
}

instance_resume() {
  local actor_id="${1:-}" codex_bin="${2:-}" codex_version="${3:-}" payload resume_status
  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi
  if [[ $# -ne 3 || "${codex_bin}" != /* || ! -x "${codex_bin}" || -z "${codex_version}" ]]; then
    echo "resume requires <actor-id> <absolute-codex-executable> <codex-version>" >&2
    return 2
  fi

  payload="$(
    BUDDYSWITCH_HOST_CONTROL_INTERNAL=1 \
      buddyswitch_with_runtime_lock \
      "${HOST_CONTROL_SELF}" \
      "instance-resume-locked" \
      "${actor_id}" \
      "${codex_bin}" \
      "${codex_version}"
  )"
  resume_status=$?
  if [[ "${resume_status}" -ne 0 ]]; then
    if [[ -n "${payload}" ]]; then
      printf '%s\n' "${payload}" >&2
    fi
    return "${resume_status}"
  fi
  printf '%s\n' "${payload}"
}

instance_resume_locked() {
  local actor_id="${1:-}" codex_bin="${2:-}" codex_version="${3:-}" role thread_id app_server_json
  local resume_json="" resumed_thread_id

  buddyswitch_require_runtime_lock || return $?
  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi

  buddyswitch_validate_actor_id "${actor_id}" || return $?
  role="$(buddyswitch_instance_validate_record "${actor_id}")" || return $?
  buddyswitch_env_bind_instance "${actor_id}" || return $?
  host_control_validate_recorded_codex_runtime "${actor_id}" "${codex_bin}" "${codex_version}" || return $?
  export BUDDYSWITCH_CODEX_BIN="${codex_bin}"
  export BUDDYSWITCH_CODEX_VERSION="${codex_version}"
  thread_id="$(buddyswitch_instance_record_field "${actor_id}" "thread_id" || true)"
  if [[ -z "${thread_id}" ]]; then
    echo "Instance resume blocked: ${actor_id} has no thread id; delete it and start a new instance." >&2
    return 3
  fi

  if buddyswitch_app_server_is_active; then
    if ! buddyswitch_daemon_start >/dev/null; then
      echo "Daemon start failed for ${actor_id}." >&2
      return 1
    fi
    "${BUDDYSWITCH_PYTHON}" - "${actor_id}" "${thread_id}" <<'PY'
import json
import sys

print(json.dumps({
    "actor_id": sys.argv[1],
    "thread_id": sys.argv[2],
    "status": "active",
}, ensure_ascii=True))
PY
    return 0
  fi

  buddyswitch_runtime_broker_ensure || return $?
  export BUDDYSWITCH_ROLE_ID="${role}"

  app_server_json="$(buddyswitch_app_server_ensure)" || {
    buddyswitch_runtime_broker_stop
    buddyswitch_browser_manager_stop_instance "${actor_id}" || true
    return 1
  }

  resume_json="$(buddyswitch_app_server_thread_resume "${thread_id}" 2>&1)" || {
    echo "thread/resume failed for ${thread_id}" >&2
    [[ -n "${resume_json}" ]] && echo "${resume_json}" >&2
    buddyswitch_app_server_stop || true
    buddyswitch_runtime_broker_stop
    buddyswitch_browser_manager_stop_instance "${actor_id}" || true
    buddyswitch_instance_clear_app_server "${actor_id}" "inactive"
    return 1
  }

  resumed_thread_id="$(
    "${BUDDYSWITCH_PYTHON}" -c 'import json, sys; print(json.load(sys.stdin).get("thread", {}).get("id", ""))' <<<"${resume_json}"
  )" || {
    echo "thread/resume returned invalid JSON for ${thread_id}" >&2
    buddyswitch_app_server_stop || true
    buddyswitch_runtime_broker_stop
    buddyswitch_browser_manager_stop_instance "${actor_id}" || true
    buddyswitch_instance_clear_app_server "${actor_id}" "inactive"
    return 1
  }

  if [[ "${resumed_thread_id}" != "${thread_id}" ]]; then
    echo "thread/resume returned unexpected thread id: ${resumed_thread_id}" >&2
    buddyswitch_app_server_stop || true
    buddyswitch_runtime_broker_stop
    buddyswitch_browser_manager_stop_instance "${actor_id}" || true
    buddyswitch_instance_clear_app_server "${actor_id}" "inactive"
    return 1
  fi

  buddyswitch_instance_set_app_server \
    "${actor_id}" \
    "${thread_id}" \
    "$(_buddyswitch_app_server_json_field "${app_server_json}" "pid")" \
    "$(_buddyswitch_app_server_json_field "${app_server_json}" "socket_path")" \
    "$(_buddyswitch_app_server_json_field "${app_server_json}" "log_file")" \
    "active"
  if ! buddyswitch_daemon_start >/dev/null; then
    echo "Daemon start failed for ${actor_id}." >&2
    buddyswitch_app_server_stop || true
    buddyswitch_runtime_broker_stop
    buddyswitch_browser_manager_stop_instance "${actor_id}" || true
    buddyswitch_instance_clear_app_server "${actor_id}" "inactive"
    return 1
  fi

  "${BUDDYSWITCH_PYTHON}" - "${actor_id}" "${thread_id}" <<'PY'
import json
import sys

print(json.dumps({
    "actor_id": sys.argv[1],
    "thread_id": sys.argv[2],
    "status": "active",
}, ensure_ascii=True))
PY
}

instance_stop() {
  local actor_id="${1:-}"
  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi
  if [[ $# -ne 1 ]]; then
    echo "stop requires <actor-id>" >&2
    return 2
  fi

  buddyswitch_validate_actor_id "${actor_id}" || return $?
  buddyswitch_instance_validate_record "${actor_id}" >/dev/null || return $?

  BUDDYSWITCH_HOST_CONTROL_INTERNAL=1 \
    buddyswitch_with_runtime_lock \
    "${HOST_CONTROL_SELF}" \
    "instance-set-inactive-locked" \
    "${actor_id}" || return $?
  "${BUDDYSWITCH_PYTHON}" - "${actor_id}" <<'PY'
import json
import sys

print(json.dumps({"actor_id": sys.argv[1], "status": "inactive"}, ensure_ascii=True))
PY
}

instance_status_json() {
  local actor_id="$1" app_status_json daemon_status_json runtime_broker_status_json thread_id thread_json=""
  buddyswitch_validate_actor_id "${actor_id}" || return $?
  buddyswitch_instance_validate_record "${actor_id}" >/dev/null || return $?
  buddyswitch_env_bind_instance "${actor_id}" || return $?
  thread_id="$(buddyswitch_instance_record_field "${actor_id}" "thread_id" || true)"
  app_status_json="$(buddyswitch_app_server_status_json 2>/dev/null || true)"
  if [[ -z "${app_status_json}" ]]; then
    app_status_json='{"healthy": false, "pid": null, "pid_live": false, "socket_path": "", "socket_exists": false, "probe": null}'
  fi
  daemon_status_json="$(buddyswitch_daemon_status_json 2>/dev/null || true)"
  if [[ -z "${daemon_status_json}" ]]; then
    daemon_status_json='{"live": false, "pid": null, "pid_live": false, "last_error": null}'
  fi
  runtime_broker_status_json="$(buddyswitch_runtime_broker_status_json 2>/dev/null || true)"
  if [[ -z "${runtime_broker_status_json}" ]]; then
    runtime_broker_status_json='{"healthy": false, "pid": null, "pid_live": false, "socket_path": "", "log_file": "", "log": {"path": "", "exists": false, "size_bytes": 0, "mtime": null, "last_event": null}}'
  fi
  if [[ -n "${thread_id}" ]]; then
    if "${BUDDYSWITCH_PYTHON}" - "${app_status_json}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
raise SystemExit(0 if payload.get("healthy") else 1)
PY
    then
      thread_json="$(buddyswitch_app_server_thread_read "${thread_id}" 2>/dev/null || true)"
    fi
  fi
  "${BUDDYSWITCH_PYTHON}" - "${BUDDYSWITCH_INSTANCE_JSON}" "${app_status_json}" "${daemon_status_json}" "${runtime_broker_status_json}" "${thread_json}" <<'PY'
import json
import sys
from pathlib import Path

instance_payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
app_server = json.loads(sys.argv[2]) if sys.argv[2] else {}
daemon = json.loads(sys.argv[3]) if sys.argv[3] else {}
runtime_broker = json.loads(sys.argv[4]) if sys.argv[4] else {}
thread_payload = json.loads(sys.argv[5]) if sys.argv[5] else {}

thread = thread_payload.get("thread") if isinstance(thread_payload, dict) else None
thread_status = None
if isinstance(thread, dict):
    raw_status = thread.get("status")
    if isinstance(raw_status, str):
        thread_status = raw_status.lower()
    elif isinstance(raw_status, dict):
        status_type = raw_status.get("type")
        if isinstance(status_type, str):
            thread_status = status_type.lower()

payload = {
    "actor_id": instance_payload.get("actor_id"),
    "role": instance_payload.get("role"),
    "status": instance_payload.get("status"),
    "workspace_dir": instance_payload.get("workspace_dir"),
    "browser_port": instance_payload.get("browser_port"),
    "updated_at": instance_payload.get("updated_at"),
    "thread_id": instance_payload.get("thread_id"),
    "codex_runtime": instance_payload.get("codex_runtime"),
    "last_failure": instance_payload.get("last_failure"),
    "app_server": app_server,
    "daemon": daemon,
    "runtime_broker": runtime_broker,
    "thread": {
        "status": thread_status,
        "raw": thread,
    },
}
print(json.dumps(payload, ensure_ascii=True))
PY
}

instance_status() {
  local actor_id="${1:-}"
  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi
  if [[ $# -ne 1 ]]; then
    echo "status requires <actor-id>" >&2
    return 2
  fi
  instance_status_json "${actor_id}"
}

instance_interrupt() {
  local actor_id="${1:-}" thread_id output
  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi
  if [[ $# -ne 1 ]]; then
    echo "interrupt requires <actor-id>" >&2
    return 2
  fi

  buddyswitch_validate_actor_id "${actor_id}" || return $?
  buddyswitch_instance_validate_record "${actor_id}" >/dev/null || return $?
  buddyswitch_env_bind_instance "${actor_id}" || return $?
  thread_id="$(buddyswitch_instance_record_field "${actor_id}" "thread_id" || true)"
  if [[ -z "${thread_id}" ]]; then
    echo "Instance interrupt blocked: ${actor_id} has no thread id; stop/delete it and start a new instance." >&2
    return 3
  fi
  if ! buddyswitch_app_server_is_active; then
    echo "Instance interrupt blocked: ${actor_id} is unhealthy or inactive." >&2
    return 3
  fi

  output="$(buddyswitch_app_server_interrupt "${thread_id}" 2>&1)" || {
    if [[ -n "${output}" ]]; then
      echo "${output}" >&2
    fi
    return 1
  }

  "${BUDDYSWITCH_PYTHON}" - "${output}" "${actor_id}" "${thread_id}" <<'PY'
import json
import sys

source = json.loads(sys.argv[1])
payload = {
    "actor_id": sys.argv[2],
    "thread_id": sys.argv[3],
    "turn_id": source.get("turn_id"),
}
print(json.dumps(payload, ensure_ascii=True))
PY
}

instance_delete() {
  local actor_id="${1:-}" delete_stdout delete_status
  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi
  if [[ $# -ne 1 ]]; then
    echo "delete requires <actor-id>" >&2
    return 2
  fi

  buddyswitch_validate_actor_id "${actor_id}" || return $?
  set +e
  delete_stdout="$(
    BUDDYSWITCH_DELETE_ACTOR_ID="${actor_id}" \
    BUDDYSWITCH_HOST_CONTROL_INTERNAL=1 \
      buddyswitch_with_runtime_lock "${HOST_CONTROL_SELF}" "instance-delete-locked"
  )"
  delete_status=$?
  set -e
  if [[ "${delete_status}" -ne 0 ]]; then
    if [[ -n "${delete_stdout}" ]]; then
      printf '%s\n' "${delete_stdout}" >&2
    fi
    return "${delete_status}"
  fi
  "${BUDDYSWITCH_PYTHON}" - "${actor_id}" <<'PY'
import json
import sys

print(json.dumps({"actor_id": sys.argv[1], "deleted": True}, ensure_ascii=True))
PY
}

instance_delete_locked() {
  local actor_id instance_root
  buddyswitch_require_runtime_lock || return $?
  actor_id="${BUDDYSWITCH_DELETE_ACTOR_ID:-}"
  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi
  buddyswitch_validate_actor_id "${actor_id}" || return $?
  buddyswitch_env_bind_instance "${actor_id}" || return $?
  instance_root="$(buddyswitch_instance_require_safe_delete_root "${actor_id}")" || return $?
  buddyswitch_instance_validate_record "${actor_id}" >/dev/null || return $?

  if buddyswitch_instance_app_server_is_active "${actor_id}"; then
    echo "Instance delete blocked: ${actor_id} is active." >&2
    return 3
  fi
  if buddyswitch_browser_instance_pid_marker_is_active "${actor_id}"; then
    echo "Instance delete blocked: active browser cockpit detected for ${actor_id}." >&2
    return 3
  fi
  local browser_ownership
  browser_ownership="$(buddyswitch_browser_instance_endpoint_ownership_state "${actor_id}")"
  if [[ "${browser_ownership}" == "owned" ]]; then
    echo "Instance delete blocked: active browser cockpit detected for ${actor_id}." >&2
    return 3
  fi
  if [[ "${browser_ownership}" == "unknown" ]]; then
    echo "Instance delete blocked: active browser cockpit ownership could not be verified for ${actor_id}." >&2
    return 3
  fi

  buddyswitch_runtime_broker_stop || return $?
  buddyswitch_remove_owned_path "${instance_root}" || return $?
}

host_control_roles() {
  if [[ $# -ne 0 ]]; then
    echo "roles accepts no arguments" >&2
    return 2
  fi
  "${BUDDYSWITCH_PYTHON}" - <<'PY'
import json
from buddyswitch.application.build import activate_application
from buddyswitch.runtime_support.env_manifest import load_manifest

activate_application()
manifest = load_manifest()
roles = [
    {"id": role["id"], "label": role["label"], "scope": role["scope"]}
    for role in manifest["roles"]
]
print(json.dumps({"roles": roles}, ensure_ascii=True, sort_keys=True))
PY
}

host_control_start() {
  if [[ $# -ne 4 ]]; then
    echo "start requires <role-id> <codex-executable> <codex-version> <actor-id>" >&2
    return 2
  fi
  start_codex "$1" "$2" "$3" "$4"
}

host_control_list() {
  case "$#" in
    0)
      buddyswitch_instance_list
      ;;
    1)
      buddyswitch_instance_list "$1"
      ;;
    *)
      echo "list accepts optional <role-id>" >&2
      return 2
      ;;
  esac
}

host_control_status() {
  if [[ $# -ne 1 ]]; then
    echo "status requires <actor-id>" >&2
    return 2
  fi
  instance_status "$1"
}

host_control_clear() {
  if [[ $# -ne 1 ]]; then
    echo "clear requires <actor-id>" >&2
    return 2
  fi
  instance_clear "$1"
}

host_control_resume() {
  if [[ $# -ne 3 ]]; then
    echo "resume requires <actor-id> <absolute-codex-executable> <codex-version>" >&2
    return 2
  fi
  instance_resume "$1" "$2" "$3"
}

host_control_stop() {
  if [[ $# -ne 1 ]]; then
    echo "stop requires <actor-id>" >&2
    return 2
  fi
  instance_stop "$1"
}

host_control_delete() {
  if [[ $# -ne 1 ]]; then
    echo "delete requires <actor-id>" >&2
    return 2
  fi
  instance_delete "$1"
}

host_control_interrupt() {
  if [[ $# -ne 1 ]]; then
    echo "interrupt requires <actor-id>" >&2
    return 2
  fi
  instance_interrupt "$1"
}

host_control_compact() {
  if [[ $# -ne 1 ]]; then
    echo "compact requires <actor-id>" >&2
    return 2
  fi
  instance_compact "$1"
}

host_control_run_raw_operation() {
  local operation="${1:-}"
  if [[ -n "${operation}" ]]; then
    shift || true
  fi
  case "${operation}" in
    roles)
      host_control_roles "$@"
      ;;
    start)
      host_control_start "$@"
      ;;
    list)
      host_control_list "$@"
      ;;
    status)
      host_control_status "$@"
      ;;
    clear)
      host_control_clear "$@"
      ;;
    resume)
      host_control_resume "$@"
      ;;
    stop)
      host_control_stop "$@"
      ;;
    delete)
      host_control_delete "$@"
      ;;
    interrupt)
      host_control_interrupt "$@"
      ;;
    compact)
      host_control_compact "$@"
      ;;
    start-bootstrap-locked)
      host_control_require_internal_dispatch || return $?
      start_locked_bootstrap "$@"
      ;;
    instance-set-inactive-locked)
      host_control_require_internal_dispatch || return $?
      instance_set_inactive_locked "$@"
      ;;
    instance-resume-locked)
      host_control_require_internal_dispatch || return $?
      instance_resume_locked "$@"
      ;;
    instance-delete-locked)
      host_control_require_internal_dispatch || return $?
      instance_delete_locked "$@"
      ;;
    "")
      echo "host control operation is required" >&2
      return 2
      ;;
    *)
      echo "unknown host control operation: ${operation}" >&2
      return 2
      ;;
  esac
}

host_control_main() {
  local stdout_file stderr_file stdout_output stderr_output error_output status emit_status
  stdout_file="$(mktemp "${TMPDIR:-/tmp}/buddyswitch-host-control-stdout.XXXXXX")" || {
    host_control_emit_error_json "COMMAND_FAILED" "Host control failed to create stdout capture."
    return 1
  }
  stderr_file="$(mktemp "${TMPDIR:-/tmp}/buddyswitch-host-control-stderr.XXXXXX")" || {
    rm -f "${stdout_file}"
    host_control_emit_error_json "COMMAND_FAILED" "Host control failed to create stderr capture."
    return 1
  }

  set +e
  if host_control_run_raw_operation "$@" >"${stdout_file}" 2>"${stderr_file}"; then
    status=0
  else
    status=$?
  fi
  set -e
  if [[ "${status}" -eq 0 ]]; then
    emit_status=0
    if [[ -s "${stderr_file}" ]]; then
      cat "${stderr_file}" >&2 || emit_status=$?
    fi
    cat "${stdout_file}" || emit_status=$?
    rm -f "${stdout_file}" "${stderr_file}"
    return "${emit_status}"
  fi

  stdout_output="$(cat "${stdout_file}")"
  stderr_output="$(cat "${stderr_file}")"
  rm -f "${stdout_file}" "${stderr_file}"
  if [[ -n "${stdout_output}" ]] && host_control_output_has_error_json "${stdout_output}"; then
    if [[ -n "${stderr_output}" ]]; then
      printf '%s\n' "${stderr_output}" >&2
    fi
    host_control_emit_error_for_output "${status}" "${stdout_output}"
    return "${status}"
  fi
  error_output="${stderr_output:-${stdout_output}}"
  host_control_emit_error_for_output "${status}" "${error_output}"
  return "${status}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  host_control_main "$@"
fi
