#!/usr/bin/env bash
set -euo pipefail

BUDDYSWITCH_LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUDDYSWITCH_WORKSPACE_HELPER="${BUDDYSWITCH_LAUNCHER_DIR}/workspace.sh"
BUDDYSWITCH_RUNTIME_LOCK_HELPER_DEFAULT="${BUDDYSWITCH_LAUNCHER_DIR}/runtime_lock.py"

if [[ ! -f "${BUDDYSWITCH_WORKSPACE_HELPER}" ]]; then
  echo "Workspace helper is missing under tools/launcher." >&2
  exit 1
fi

source "${BUDDYSWITCH_WORKSPACE_HELPER}"

buddyswitch_env_init() {
  local source_home source_codex_home shared_root

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

  buddyswitch_workspace_init_defaults
}

buddyswitch_with_runtime_lock() {
  if [[ ! -f "${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" ]]; then
    echo "Runtime lock helper missing: ${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" >&2
    return 1
  fi
  python3 "${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" -- "$@"
}

buddyswitch_require_runtime_lock() {
  if [[ ! -f "${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" ]]; then
    echo "Runtime lock helper missing: ${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" >&2
    return 1
  fi
  python3 "${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" --assert-held
  unset BUDDYSWITCH_RUNTIME_LOCK_PROOF
  unset BUDDYSWITCH_RUNTIME_LOCK_TOKEN
}

buddyswitch_ensure_shared_env() {
  buddyswitch_workspace_validate_workspace_dir

  mkdir -p \
    "${BUDDYSWITCH_HOME}" \
    "${BUDDYSWITCH_XDG_CONFIG_HOME}" \
    "${BUDDYSWITCH_CODEX_HOME}" \
    "${BUDDYSWITCH_RUN_STATE_DIR}"

  if [[ ! -f "${BUDDYSWITCH_CODEX_HOME}/config.toml" ]]; then
    cat > "${BUDDYSWITCH_CODEX_HOME}/config.toml" <<'EOF'
[skills.bundled]
enabled = false

[features]
plugins = false
EOF
  fi

  if [[ ! -f "${BUDDYSWITCH_CODEX_HOME}/auth.json" && -f "${BUDDYSWITCH_SOURCE_CODEX_HOME}/auth.json" ]]; then
    cp "${BUDDYSWITCH_SOURCE_CODEX_HOME}/auth.json" "${BUDDYSWITCH_CODEX_HOME}/auth.json"
  fi

}

buddyswitch_codex_config_path() {
  printf '%s/config.toml\n' "${BUDDYSWITCH_CODEX_HOME}"
}

buddyswitch_validate_buddy_id() {
  local buddy_id="$1"
  local manifest_helper manifest_path

  manifest_helper="${BUDDYSWITCH_REPO_ROOT}/scripts/env_manifest.py"
  manifest_path="${BUDDYSWITCH_REPO_ROOT}/buddyswitch/manifest.toml"

  if [[ -z "${buddy_id}" ]]; then
    echo "Buddy id must not be empty." >&2
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

  python3 "${manifest_helper}" --manifest "${manifest_path}" show-buddy "${buddy_id}" >/dev/null
}

buddyswitch_buddy_agents_template_path() {
  local buddy_id="$1"
  printf '%s/tools/launcher/assets/buddies/%s/AGENTS.md\n' "${BUDDYSWITCH_REPO_ROOT}" "${buddy_id}"
}

buddyswitch_require_buddy_agents_template() {
  local buddy_id="$1"
  local template_path

  template_path="$(buddyswitch_buddy_agents_template_path "${buddy_id}")"
  if [[ ! -f "${template_path}" ]]; then
    echo "Buddy AGENTS template not found: ${template_path}" >&2
    return 1
  fi
  export BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE="${template_path}"
}

buddyswitch_instance_json_path() {
  local instance_id="$1"
  printf '%s/instances/%s/instance.json\n' "${BUDDYSWITCH_SHARED_ROOT}" "${instance_id}"
}

buddyswitch_instance_root() {
  local instance_id="$1"
  printf '%s/instances/%s\n' "${BUDDYSWITCH_SHARED_ROOT}" "${instance_id}"
}

buddyswitch_validate_instance_id() {
  local instance_id="$1"

  if [[ -z "${instance_id}" ]]; then
    echo "Invalid instance id: must not be empty." >&2
    return 2
  fi
  if [[ ! "${instance_id}" =~ ^inst-[A-Za-z0-9._-]+$ ]]; then
    echo "Invalid instance id: ${instance_id}" >&2
    return 2
  fi
}

buddyswitch_env_bind_instance() {
  local instance_id="$1"
  local instance_root

  buddyswitch_validate_instance_id "${instance_id}" || return $?
  instance_root="$(buddyswitch_instance_root "${instance_id}")"
  export BUDDYSWITCH_INSTANCE_ID="${instance_id}"
  export BUDDYSWITCH_INSTANCE_JSON="$(buddyswitch_instance_json_path "${instance_id}")"
  export BUDDYSWITCH_INSTANCE_ROOT="${instance_root}"
  export BUDDYSWITCH_WORKSPACE_DIR="${instance_root}/workspace"
  export BUDDYSWITCH_HOME="${instance_root}/home"
  export BUDDYSWITCH_CODEX_HOME="${instance_root}/codex-home"
  export BUDDYSWITCH_XDG_CONFIG_HOME="${instance_root}/xdg-config"
}

buddyswitch_generate_instance_id() {
  local buddy="$1"
  python3 -c 'import sys, uuid; print(f"inst-{sys.argv[1]}-{uuid.uuid4().hex[:12]}")' "${buddy}"
}

buddyswitch_instance_activate() {
  local instance_id="$1"
  local buddy="$2"
  local instance_json instance_dir

  instance_json="$(buddyswitch_instance_json_path "${instance_id}")"
  instance_dir="$(dirname "${instance_json}")"
  mkdir -p "${instance_dir}"

  python3 - "${instance_json}" "${instance_id}" "${buddy}" "${BUDDYSWITCH_WORKSPACE_DIR}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
instance_id = sys.argv[2]
buddy = sys.argv[3]
workspace_dir = sys.argv[4]
now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
payload = {
    "instance_id": instance_id,
    "buddy": buddy,
    "status": "active",
    "current_task_id": None,
    "current_track_id": None,
    "workspace_dir": workspace_dir,
    "browser_port": None,
    "created_at": now,
    "updated_at": now,
}
temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY

  printf '%s\n' "${instance_json}"
}

buddyswitch_instance_set_status() {
  local instance_id="$1"
  local status="$2"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${instance_id}")"

  python3 - "${instance_json}" "${instance_id}" "${status}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
instance_id = sys.argv[2]
status = sys.argv[3]
if not instance_json.exists():
    raise SystemExit(f"Instance record missing: {instance_json}")
payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("instance_id") != instance_id:
    raise SystemExit(f"Instance id mismatch in {instance_json}")
payload["status"] = status
payload["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY
}

buddyswitch_instance_set_browser_port() {
  local instance_id="$1"
  local browser_port="$2"
  local instance_json

  instance_json="$(buddyswitch_instance_json_path "${instance_id}")"

  python3 - "${instance_json}" "${instance_id}" "${browser_port}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
instance_id = sys.argv[2]
try:
    browser_port = int(sys.argv[3])
except ValueError as exc:
    raise SystemExit(f"Invalid browser port: {sys.argv[3]}") from exc
if browser_port < 1 or browser_port > 65535:
    raise SystemExit(f"Invalid browser port: {browser_port}")
if not instance_json.exists():
    raise SystemExit(f"Instance record missing: {instance_json}")
payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("instance_id") != instance_id:
    raise SystemExit(f"Instance id mismatch in {instance_json}")
payload["browser_port"] = browser_port
payload["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
temp_path = instance_json.with_suffix(".tmp")
temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
temp_path.replace(instance_json)
PY
}

buddyswitch_run_codex() {
  HOME="${BUDDYSWITCH_HOME}" \
  CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
  XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
  codex "$@"
}

buddyswitch_write_launcher_marker() {
  local marker_pid="${1:-${BUDDYSWITCH_LAUNCHER_MARKER_PID:-$$}}"
  local marker_path="${BUDDYSWITCH_RUN_STATE_DIR}/launcher-${marker_pid}.pid"
  printf '%s\n' "${marker_pid}" > "${marker_path}"
  printf '%s\n' "${marker_path}"
}

buddyswitch_cleanup_pid_marker() {
  local marker_path="$1"
  rm -f "${marker_path}"
}

buddyswitch_count_active_launchers() {
  local active_count=0
  local marker_file marker_pid

  if [[ ! -d "${BUDDYSWITCH_RUN_STATE_DIR}" ]]; then
    echo "0"
    return
  fi

  for marker_file in "${BUDDYSWITCH_RUN_STATE_DIR}"/launcher-*.pid; do
    if [[ ! -e "${marker_file}" ]]; then
      continue
    fi

    marker_pid="$(cat "${marker_file}" 2>/dev/null || true)"
    if [[ -n "${marker_pid}" ]] && kill -0 "${marker_pid}" 2>/dev/null; then
      active_count=$((active_count + 1))
    else
      rm -f "${marker_file}"
    fi
  done

  echo "${active_count}"
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
