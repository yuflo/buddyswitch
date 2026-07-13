#!/usr/bin/env bash
set -euo pipefail

BUDDYSWITCH_LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUDDYSWITCH_WORKSPACE_HELPER="${BUDDYSWITCH_LAUNCHER_DIR}/workspace.sh"
BUDDYSWITCH_RUNTIME_LOCK_HELPER_DEFAULT="${BUDDYSWITCH_LAUNCHER_DIR}/runtime_lock.py"
BUDDYSWITCH_CODEX_CONFIG_HELPER="${BUDDYSWITCH_LAUNCHER_DIR}/codex_config.py"
BUDDYSWITCH_ENV_PROFILES_HELPER_REL="scripts/env_profiles.py"

if [[ ! -f "${BUDDYSWITCH_WORKSPACE_HELPER}" ]]; then
  echo "Workspace helper is missing under tools/launcher." >&2
  exit 1
fi

source "${BUDDYSWITCH_WORKSPACE_HELPER}"

buddyswitch_resolve_python() {
  local python_path

  python_path="$(type -P python 2>/dev/null || true)"
  if [[ -z "${python_path}" || ! -x "${python_path}" ]]; then
    echo "BuddySwitch requires an executable 'python' on PATH." >&2
    return 1
  fi

  if [[ "${python_path}" != /* ]]; then
    case "${python_path}" in
      */*) python_path="$(cd "${python_path%/*}" && pwd)/${python_path##*/}" ;;
      *) python_path="$(pwd)/${python_path}" ;;
    esac
  fi

  if ! "${python_path}" -c 'import tomllib' >/dev/null 2>&1; then
    echo "BuddySwitch could not execute PATH python: ${python_path}" >&2
    return 1
  fi

  export BUDDYSWITCH_PYTHON="${python_path}"
}

buddyswitch_env_init() {
  local source_home source_codex_home shared_root

  buddyswitch_resolve_python || return $?
  source_home="${BUDDYSWITCH_SOURCE_HOME:-${HOME}}"
  source_codex_home="${BUDDYSWITCH_SOURCE_CODEX_HOME:-${CODEX_HOME:-${source_home}/.codex}}"
  shared_root="${BUDDYSWITCH_SHARED_ROOT:-${source_home}/.codex-buddyswitch}"
  shared_root="${shared_root%/}"

  export BUDDYSWITCH_SOURCE_HOME="${source_home}"
  export BUDDYSWITCH_SOURCE_CODEX_HOME="${source_codex_home}"
  export BUDDYSWITCH_SHARED_ROOT="${shared_root}"

  export BUDDYSWITCH_HOME="${BUDDYSWITCH_HOME:-${shared_root}/home}"
  export BUDDYSWITCH_CODEX_HOME="${BUDDYSWITCH_CODEX_HOME:-${shared_root}/codex-home}"
  export BUDDYSWITCH_XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME:-${BUDDYSWITCH_HOME}/.config}"
  export BUDDYSWITCH_RUN_STATE_DIR="${shared_root}/run"
  export BUDDYSWITCH_RUNTIME_LOCK_HELPER="${BUDDYSWITCH_RUNTIME_LOCK_HELPER:-${BUDDYSWITCH_RUNTIME_LOCK_HELPER_DEFAULT}}"
  export BUDDYSWITCH_REPO_ROOT="${BUDDYSWITCH_REPO_ROOT:-${REPO_ROOT:-$(cd "${BUDDYSWITCH_LAUNCHER_DIR}/../.." && pwd)}}"
  export BUDDYSWITCH_ENV_MCP_NAME="${BUDDYSWITCH_ENV_MCP_NAME:-buddyswitch-env}"
  export BUDDYSWITCH_ENV_MCP_SERVER="${BUDDYSWITCH_ENV_MCP_SERVER:-${BUDDYSWITCH_REPO_ROOT}/tools/launcher/env_tool_mcp_server.py}"

  buddyswitch_workspace_init_defaults
}

buddyswitch_with_runtime_lock() {
  if [[ ! -f "${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" ]]; then
    echo "Runtime lock helper missing: ${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" >&2
    return 1
  fi
  "${BUDDYSWITCH_PYTHON}" "${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" -- "$@"
}

buddyswitch_require_runtime_lock() {
  if [[ ! -f "${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" ]]; then
    echo "Runtime lock helper missing: ${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" >&2
    return 1
  fi
  "${BUDDYSWITCH_PYTHON}" "${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" --assert-held
}

buddyswitch_patch_codex_config() {
  local config_path
  local active_role
  local local_default_tmp_root
  local -a patch_args=()
  local -a temp_root_args=()
  config_path="${BUDDYSWITCH_CODEX_HOME}/config.toml"
  active_role="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"
  local_default_tmp_root="/tmp"

  patch_args=(
    --config "${config_path}"
    --repo-root "${BUDDYSWITCH_REPO_ROOT}"
    --shared-root "${BUDDYSWITCH_SHARED_ROOT}"
    --source-codex-home "${BUDDYSWITCH_SOURCE_CODEX_HOME}"
  )

  if [[ -n "${active_role}" ]]; then
    temp_root_args=(--temp-root "${BUDDYSWITCH_INSTANCE_TMP}")
    patch_args+=(
      --manifest "${BUDDYSWITCH_REPO_ROOT}/buddyswitch/manifest.toml"
      --role "${active_role}"
      --instance-root "${BUDDYSWITCH_INSTANCE_ROOT}"
      --workspace-dir "${BUDDYSWITCH_WORKSPACE_DIR}"
      --project-workspace-dir "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
      --home "${BUDDYSWITCH_HOME}"
      --codex-home "${BUDDYSWITCH_CODEX_HOME}"
      --xdg-config-home "${BUDDYSWITCH_XDG_CONFIG_HOME}"
    )
    if [[ -n "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET:-}" ]]; then
      patch_args+=(--broker-socket "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}")
    fi
  else
    temp_root_args=(--temp-root "${local_default_tmp_root}")
    if [[ -n "${TMPDIR:-}" ]]; then
      temp_root_args+=(--temp-root "${TMPDIR}")
    fi
  fi

  "${BUDDYSWITCH_PYTHON}" "${BUDDYSWITCH_CODEX_CONFIG_HELPER}" \
    "${patch_args[@]}" \
    "${temp_root_args[@]}"
}

buddyswitch_ensure_shared_env() {
  local shared_codex_home

  buddyswitch_workspace_validate_workspace_dir

  mkdir -p \
    "${BUDDYSWITCH_HOME}" \
    "${BUDDYSWITCH_XDG_CONFIG_HOME}" \
    "${BUDDYSWITCH_CODEX_HOME}" \
    "${BUDDYSWITCH_RUN_STATE_DIR}"

  shared_codex_home="${BUDDYSWITCH_SHARED_ROOT}/codex-home"
  mkdir -p "${shared_codex_home}"

  if [[ ! -f "${BUDDYSWITCH_CODEX_HOME}/config.toml" ]]; then
    cat > "${BUDDYSWITCH_CODEX_HOME}/config.toml" <<'EOF'
[skills.bundled]
enabled = false

[features]
plugins = false
EOF
  fi

  buddyswitch_patch_codex_config

  if [[ ! -f "${shared_codex_home}/auth.json" && -f "${BUDDYSWITCH_SOURCE_CODEX_HOME}/auth.json" ]]; then
    cp "${BUDDYSWITCH_SOURCE_CODEX_HOME}/auth.json" "${shared_codex_home}/auth.json"
  fi

  if [[ "${BUDDYSWITCH_CODEX_HOME}" == "${shared_codex_home}" ]]; then
    return 0
  fi

  if [[ -f "${shared_codex_home}/auth.json" ]]; then
    rm -f "${BUDDYSWITCH_CODEX_HOME}/auth.json"
    ln -s "${shared_codex_home}/auth.json" "${BUDDYSWITCH_CODEX_HOME}/auth.json"
  fi

}

buddyswitch_codex_config_path() {
  printf '%s/config.toml\n' "${BUDDYSWITCH_CODEX_HOME}"
}

buddyswitch_env_mcp_has_server() {
  local server_name="$1"
  local config_path

  config_path="$(buddyswitch_codex_config_path)"
  if [[ ! -f "${config_path}" ]]; then
    return 1
  fi

  grep -Eq "^\\[mcp_servers\\.${server_name}\\]$" "${config_path}"
}

buddyswitch_env_mcp_matches_instance() {
  local server_name="$1"
  local config_path
  local active_role

  config_path="$(buddyswitch_codex_config_path)"
  active_role="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"
  if [[ ! -f "${config_path}" ]]; then
    return 1
  fi
  if [[ -z "${BUDDYSWITCH_ACTOR_ID:-}" || -z "${active_role}" || -z "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET:-}" ]]; then
    return 1
  fi

  "${BUDDYSWITCH_PYTHON}" - "${config_path}" "${server_name}" "${BUDDYSWITCH_PYTHON}" "${BUDDYSWITCH_ENV_MCP_SERVER}" "${BUDDYSWITCH_REPO_ROOT}" "${BUDDYSWITCH_ACTOR_ID}" "${active_role}" "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}" <<'PY'
import sys
import tomllib
from pathlib import Path

config_path = Path(sys.argv[1])
server_name = sys.argv[2]
expected_python = sys.argv[3]
server_path = sys.argv[4]
repo_root = sys.argv[5]
actor_id = sys.argv[6]
role = sys.argv[7]
broker_socket = sys.argv[8]

try:
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)

server = payload.get("mcp_servers", {}).get(server_name)
if not isinstance(server, dict):
    raise SystemExit(1)
args = server.get("args")
if server.get("command") != expected_python or not isinstance(args, list):
    raise SystemExit(1)

expected_args = [
    server_path,
    "--repo-root",
    repo_root,
    "--actor-id",
    actor_id,
    "--role",
    role,
    "--broker-socket",
    broker_socket,
]
if args != expected_args:
    raise SystemExit(1)
PY
}

buddyswitch_env_mcp_remove_server() {
  local server_name="$1"
  buddyswitch_run_codex mcp remove "${server_name}"
}

buddyswitch_env_mcp_add_server() {
  local server_name="$1"
  local active_role
  active_role="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"

  if [[ -z "${active_role}" ]]; then
    echo "BuddySwitch env MCP registration requires an active role." >&2
    return 2
  fi
  if [[ -z "${BUDDYSWITCH_ACTOR_ID:-}" ]]; then
    echo "BuddySwitch env MCP registration requires BUDDYSWITCH_ACTOR_ID." >&2
    return 2
  fi
  if [[ -z "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET:-}" ]]; then
    echo "BuddySwitch env MCP registration requires BUDDYSWITCH_RUNTIME_BROKER_SOCKET." >&2
    return 2
  fi

  buddyswitch_run_codex mcp add "${server_name}" -- \
    "${BUDDYSWITCH_PYTHON}" \
    "${BUDDYSWITCH_ENV_MCP_SERVER}" \
    --repo-root "${BUDDYSWITCH_REPO_ROOT}" \
    --actor-id "${BUDDYSWITCH_ACTOR_ID}" \
    --role "${active_role}" \
    --broker-socket "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}" || return $?
  buddyswitch_patch_codex_config
}

buddyswitch_env_mcp_ensure() {
  local server_name
  server_name="${BUDDYSWITCH_ENV_MCP_NAME}"

  if buddyswitch_env_mcp_has_server "${server_name}"; then
    if buddyswitch_env_mcp_matches_instance "${server_name}"; then
      return 0
    fi
    buddyswitch_env_mcp_remove_server "${server_name}" || return $?
  fi

  buddyswitch_env_mcp_add_server "${server_name}"
}

buddyswitch_validate_role_id() {
  local role_id="$1"
  local manifest_helper manifest_path

  manifest_helper="${BUDDYSWITCH_REPO_ROOT}/scripts/env_manifest.py"
  manifest_path="${BUDDYSWITCH_REPO_ROOT}/buddyswitch/manifest.toml"

  if [[ -z "${role_id}" ]]; then
    echo "Role id must not be empty." >&2
    return 2
  fi
  if [[ ! -f "${manifest_helper}" ]]; then
    echo "Manifest helper missing: ${manifest_helper}" >&2
    return 1
  fi
  if [[ ! -f "${manifest_path}" ]]; then
    echo "Manifest missing: ${manifest_path}" >&2
    return 1
  fi

  "${BUDDYSWITCH_PYTHON}" "${manifest_helper}" --manifest "${manifest_path}" show-role "${role_id}" >/dev/null
}

buddyswitch_require_env_profile() {
  local role_id="$1"
  local helper manifest_path

  helper="${BUDDYSWITCH_REPO_ROOT}/${BUDDYSWITCH_ENV_PROFILES_HELPER_REL}"
  manifest_path="${BUDDYSWITCH_REPO_ROOT}/buddyswitch/manifest.toml"

  if [[ ! -f "${helper}" ]]; then
    echo "Env profile helper missing: ${helper}" >&2
    return 1
  fi
  "${BUDDYSWITCH_PYTHON}" "${helper}" --manifest "${manifest_path}" validate --role "${role_id}" >/dev/null
}

buddyswitch_role_agents_template_path() {
  local role_id="$1"
  printf '%s/tools/launcher/assets/roles/%s/AGENTS.md\n' "${BUDDYSWITCH_REPO_ROOT}" "${role_id}"
}

buddyswitch_require_role_agents_template() {
  local role_id="$1"
  local template_path

  template_path="$(buddyswitch_role_agents_template_path "${role_id}")"
  if [[ ! -f "${template_path}" ]]; then
    echo "Role AGENTS template not found: ${template_path}" >&2
    return 1
  fi
  export BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE="${template_path}"
}

buddyswitch_instance_json_path() {
  local actor_id="$1"
  printf '%s/instances/%s/instance.json\n' "${BUDDYSWITCH_SHARED_ROOT}" "${actor_id}"
}

buddyswitch_instance_root() {
  local actor_id="$1"
  printf '%s/instances/%s\n' "${BUDDYSWITCH_SHARED_ROOT}" "${actor_id}"
}

buddyswitch_validate_actor_id() {
  local actor_id="$1"

  if [[ -z "${actor_id}" ]]; then
    echo "Invalid actor id: must not be empty." >&2
    return 2
  fi
  if [[ ! "${actor_id}" =~ ^act-[A-Za-z0-9._-]+$ ]]; then
    echo "Invalid actor id: ${actor_id}" >&2
    return 2
  fi
}

buddyswitch_env_bind_instance() {
  local actor_id="$1"
  local instance_root

  buddyswitch_validate_actor_id "${actor_id}" || return $?
  instance_root="$(buddyswitch_instance_root "${actor_id}")"
  export BUDDYSWITCH_ACTOR_ID="${actor_id}"
  export BUDDYSWITCH_INSTANCE_JSON="$(buddyswitch_instance_json_path "${actor_id}")"
  export BUDDYSWITCH_INSTANCE_ROOT="${instance_root}"
  export BUDDYSWITCH_WORKSPACE_DIR="${instance_root}/workspace"
  export BUDDYSWITCH_ACTOR_PRIVATE_DIR="${BUDDYSWITCH_WORKSPACE_DIR}/private"
  export BUDDYSWITCH_INSTANCE_TMP="${instance_root}/tmp"
  export BUDDYSWITCH_HOME="${instance_root}/home"
  export BUDDYSWITCH_CODEX_HOME="${instance_root}/codex-home"
  export BUDDYSWITCH_XDG_CONFIG_HOME="${instance_root}/xdg-config"
}

buddyswitch_instance_ensure_private_writable_surface() {
  if [[ -z "${BUDDYSWITCH_ACTOR_PRIVATE_DIR:-}" || -z "${BUDDYSWITCH_INSTANCE_TMP:-}" ]]; then
    echo "buddyswitch: actor private workspace and tmp must be bound" >&2
    return 2
  fi
  mkdir -p "${BUDDYSWITCH_ACTOR_PRIVATE_DIR}"
  mkdir -p "${BUDDYSWITCH_INSTANCE_TMP}"
}

buddyswitch_generate_actor_id() {
  local role="$1"
  "${BUDDYSWITCH_PYTHON}" -c 'import sys, uuid; print(f"act-{sys.argv[1]}-{uuid.uuid4().hex[:12]}")' "${role}"
}

buddyswitch_instance_activate() {
  local actor_id="$1"
  local role="$2"
  local status="${3:-active}"
  local instance_json instance_dir

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"
  instance_dir="$(dirname "${instance_json}")"
  mkdir -p "${instance_dir}"

  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${actor_id}" "${role}" "${status}" "${BUDDYSWITCH_WORKSPACE_DIR}" "${BUDDYSWITCH_INSTANCE_ROOT}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
role = sys.argv[3]
status = sys.argv[4]
workspace_dir = sys.argv[5]
instance_root = sys.argv[6]
now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
payload = {
    "actor_id": actor_id,
    "role": role,
    "status": status,
    "instance_root": instance_root,
    "workspace_dir": workspace_dir,
    "browser_port": None,
    "updated_at": now,
}
temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY

  printf '%s\n' "${instance_json}"
}

buddyswitch_instance_set_status() {
  local actor_id="$1"
  local status="$2"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"

  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${actor_id}" "${status}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
status = sys.argv[3]
if not instance_json.exists():
    raise SystemExit(f"Instance record missing: {instance_json}")
payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    raise SystemExit(f"Actor id mismatch in {instance_json}")
payload["status"] = status
payload["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY
}

buddyswitch_instance_set_browser_port() {
  local actor_id="$1"
  local browser_port="$2"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"

  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${actor_id}" "${browser_port}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
try:
    browser_port = int(sys.argv[3])
except ValueError as exc:
    raise SystemExit(f"Invalid browser port: {sys.argv[3]}") from exc
if browser_port < 1 or browser_port > 65535:
    raise SystemExit(f"Invalid browser port: {browser_port}")
if not instance_json.exists():
    raise SystemExit(f"Instance record missing: {instance_json}")
payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    raise SystemExit(f"Actor id mismatch in {instance_json}")
payload["browser_port"] = browser_port
payload["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY
}

buddyswitch_instance_set_app_server() {
  local actor_id="$1"
  local thread_id="$2"
  local app_server_pid="$3"
  local app_server_socket="$4"
  local app_server_log="$5"
  local status="${6:-active}"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"

  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${actor_id}" "${thread_id}" "${app_server_pid}" "${app_server_socket}" "${app_server_log}" "${status}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
thread_id = sys.argv[3]
app_server_pid_text = sys.argv[4]
app_server_socket = sys.argv[5]
app_server_log = sys.argv[6]
status = sys.argv[7]

if not instance_json.exists():
    raise SystemExit(f"Instance record missing: {instance_json}")

payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    raise SystemExit(f"Actor id mismatch in {instance_json}")

try:
    app_server_pid = int(app_server_pid_text)
except ValueError as exc:
    raise SystemExit(f"Invalid app-server pid: {app_server_pid_text}") from exc

payload["thread_id"] = thread_id or payload.get("thread_id")
payload["app_server_pid"] = app_server_pid
payload["app_server_socket"] = app_server_socket
payload["app_server_log"] = app_server_log
payload["status"] = status
payload["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY
}

buddyswitch_instance_set_thread_id() {
  local actor_id="$1"
  local thread_id="$2"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"

  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${actor_id}" "${thread_id}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
thread_id = sys.argv[3]

if not instance_json.exists():
    raise SystemExit(f"Instance record missing: {instance_json}")
if not thread_id:
    raise SystemExit("Thread id is required")

payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    raise SystemExit(f"Actor id mismatch in {instance_json}")

payload["thread_id"] = thread_id
payload["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY
}

buddyswitch_actor_side_thread_start() {
  local actor_id="$1"
  local parent_thread_id="$2"
  local text="$3"
  local capability="${4:-}"
  local instance_json args

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"
  args=(
    "${BUDDYSWITCH_REPO_ROOT}/tools/launcher/actor_side_thread.py"
    start
    --socket "$(buddyswitch_app_server_socket)"
    --instance-json "${instance_json}"
    --actor-id "${actor_id}"
    --parent-thread-id "${parent_thread_id}"
    --text "${text}"
    --purpose "host_control.side"
    --workspace-dir "${BUDDYSWITCH_WORKSPACE_DIR}"
    --shared-project-workspace-dir "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
    --permissions "buddyswitch-runtime"
  )
  if [[ -n "${capability}" ]]; then
    args+=(--capability "${capability}")
  fi
  "${BUDDYSWITCH_PYTHON}" "${args[@]}"
}

buddyswitch_side_thread_lifecycle_send() {
  local actor_id="$1"
  local parent_thread_id="$2"
  local side_thread_id="$3"
  local text="$4"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"
  "${BUDDYSWITCH_PYTHON}" "${BUDDYSWITCH_REPO_ROOT}/tools/launcher/side_thread_lifecycle.py" send \
    --socket "$(buddyswitch_app_server_socket)" \
    --instance-json "${instance_json}" \
    --actor-id "${actor_id}" \
    --parent-thread-id "${parent_thread_id}" \
    --side-thread-id "${side_thread_id}" \
    --text "${text}" \
    --permissions "buddyswitch-runtime"
}

buddyswitch_side_thread_lifecycle_cleanup() {
  local actor_id="$1"
  local parent_thread_id="$2"
  local side_thread_id="$3"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"
  "${BUDDYSWITCH_PYTHON}" "${BUDDYSWITCH_REPO_ROOT}/tools/launcher/side_thread_lifecycle.py" cleanup \
    --socket "$(buddyswitch_app_server_socket)" \
    --instance-json "${instance_json}" \
    --actor-id "${actor_id}" \
    --parent-thread-id "${parent_thread_id}" \
    --side-thread-id "${side_thread_id}"
}

buddyswitch_instance_clear_app_server() {
  local actor_id="$1"
  local status="${2:-inactive}"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"

  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${actor_id}" "${status}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
status = sys.argv[3]

if not instance_json.exists():
    raise SystemExit(f"Instance record missing: {instance_json}")

payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    raise SystemExit(f"Actor id mismatch in {instance_json}")

payload["app_server_pid"] = None
payload["app_server_socket"] = None
payload["app_server_log"] = None
payload["status"] = status
payload["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY
}

buddyswitch_instance_clear_browser_port() {
  local actor_id="$1"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"

  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${actor_id}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]

if not instance_json.exists():
    raise SystemExit(f"Instance record missing: {instance_json}")

payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    raise SystemExit(f"Actor id mismatch in {instance_json}")

payload["browser_port"] = None
payload["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY
}

buddyswitch_instance_record_failure() {
  local actor_id="$1"
  local phase="$2"
  local message="$3"
  local thread_id="${4:-}"
  local browser_port="${5:-}"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"

  "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${actor_id}" "${phase}" "${message}" "${thread_id}" "${browser_port}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
phase = sys.argv[3]
message = sys.argv[4]
thread_id = sys.argv[5]
browser_port_text = sys.argv[6]

if not instance_json.exists():
    raise SystemExit(f"Instance record missing: {instance_json}")

payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    raise SystemExit(f"Actor id mismatch in {instance_json}")

now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
failure = {
    "phase": phase,
    "message": message,
    "failed_at": now,
}
if thread_id:
    failure["thread_id"] = thread_id
if browser_port_text:
    try:
        browser_port = int(browser_port_text)
    except ValueError:
        browser_port = None
    if browser_port is not None:
        failure["browser_port"] = browser_port

payload["last_failure"] = failure
payload["updated_at"] = now

temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY
}

buddyswitch_instance_app_server_is_active() {
  local actor_id="$1"
  if [[ -z "${actor_id}" ]]; then
    return 1
  fi
  (
    buddyswitch_validate_actor_id "${actor_id}" || exit $?
    if [[ ! -f "$(buddyswitch_instance_json_path "${actor_id}")" ]]; then
      exit 1
    fi
    buddyswitch_env_bind_instance "${actor_id}" || exit $?
    buddyswitch_app_server_is_active
  )
}

_buddyswitch_list_actor_ids_for_role() {
  local target_role="${1:-}"
  local instance_json actor_id

  for instance_json in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/instance.json; do
    [[ -f "${instance_json}" ]] || continue
    actor_id="$(
      "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${target_role}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
target_role = sys.argv[2]

try:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

role = payload.get("role")
if target_role and role != target_role:
    raise SystemExit(0)

actor_id = payload.get("actor_id", instance_json.parent.name)
if isinstance(actor_id, str) and actor_id:
    print(actor_id)
PY
    )"
    [[ -n "${actor_id}" ]] || continue
    printf '%s\n' "${actor_id}"
  done
}

buddyswitch_count_active_app_servers() {
  local count=0 actor_id
  while IFS= read -r actor_id; do
    [[ -n "${actor_id}" ]] || continue
    if buddyswitch_instance_app_server_is_active "${actor_id}"; then
      count=$((count + 1))
    fi
  done < <(_buddyswitch_list_actor_ids_for_role)
  echo "${count}"
}

buddyswitch_count_active_app_servers_for_role() {
  local role="$1"
  local count=0 actor_id
  while IFS= read -r actor_id; do
    [[ -n "${actor_id}" ]] || continue
    if buddyswitch_instance_app_server_is_active "${actor_id}"; then
      count=$((count + 1))
    fi
  done < <(_buddyswitch_list_actor_ids_for_role "${role}")
  echo "${count}"
}

buddyswitch_arg_sets_native_web_search() {
  local value="$1"
  case "${value}" in
    web_search=*|*.web_search=*|*web_search=*)
      return 0
      ;;
  esac
  return 1
}

buddyswitch_print_native_search_rejection() {
  echo "Native Codex web_search is disabled in BuddySwitch product sessions." >&2
  echo "Use chrome-devtools-cockpit for browser-native discovery." >&2
  echo "Use chrome-devtools-cockpit.search_page for browser-native search page opening." >&2
  echo "Use search__request only for non-opening URL planning." >&2
  echo "Use search__status for search capability status." >&2
  echo 'Diagnostic: "$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status' >&2
}

buddyswitch_reject_native_search_args() {
  local arg next
  while [[ $# -gt 0 ]]; do
    arg="$1"
    next="${2:-}"
    case "${arg}" in
      --search|--search=*)
        buddyswitch_print_native_search_rejection
        return 2
        ;;
      -c|--config)
        if [[ -n "${next}" ]] && buddyswitch_arg_sets_native_web_search "${next}"; then
          buddyswitch_print_native_search_rejection
          return 2
        fi
        if [[ $# -ge 2 ]]; then
          shift 2
        else
          shift
        fi
        continue
        ;;
      -c*|--config=*)
        if buddyswitch_arg_sets_native_web_search "${arg}"; then
          buddyswitch_print_native_search_rejection
          return 2
        fi
        ;;
    esac
    shift || true
  done
  return 0
}

buddyswitch_run_codex() {
  if [[ -n "${BUDDYSWITCH_ROLE_ID:-}" || -n "${BUDDYSWITCH_ACTOR_ID:-}" ]]; then
    buddyswitch_reject_native_search_args "$@" || return $?
  fi
  if [[ -n "${BUDDYSWITCH_INSTANCE_TMP:-}" ]]; then
    mkdir -p "${BUDDYSWITCH_INSTANCE_TMP}"
    TMPDIR="${BUDDYSWITCH_INSTANCE_TMP}" \
    TMP="${BUDDYSWITCH_INSTANCE_TMP}" \
    TEMP="${BUDDYSWITCH_INSTANCE_TMP}" \
    TMPPREFIX="${BUDDYSWITCH_INSTANCE_TMP}/zsh" \
    BUDDYSWITCH_ACTOR_PRIVATE_DIR="${BUDDYSWITCH_ACTOR_PRIVATE_DIR:-}" \
    HOME="${BUDDYSWITCH_HOME}" \
    CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
    XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
    codex "$@"
    return $?
  fi
  HOME="${BUDDYSWITCH_HOME}" \
  CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
  XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
  codex "$@"
}

buddyswitch_validate_reset_root() {
  local shared_root normalized_root root_name

  shared_root="${BUDDYSWITCH_SHARED_ROOT:-}"
  normalized_root="${shared_root%/}"

  if [[ -z "${normalized_root}" || "${normalized_root}" == "/" ]]; then
    echo "Reset blocked: unsafe shared root '${shared_root}'." >&2
    return 1
  fi

  root_name="$(basename "${normalized_root}")"
  if [[ "${root_name}" != ".codex-buddyswitch" ]]; then
    echo "Reset blocked: BUDDYSWITCH_SHARED_ROOT must target a '.codex-buddyswitch' directory." >&2
    echo "Current: ${normalized_root}" >&2
    return 1
  fi

  return 0
}
