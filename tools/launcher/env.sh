#!/usr/bin/env bash
set -euo pipefail

BUDDYSWITCH_LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUDDYSWITCH_WORKSPACE_HELPER="${BUDDYSWITCH_LAUNCHER_DIR}/workspace.sh"
BUDDYSWITCH_RUNTIME_LOCK_HELPER_DEFAULT="${BUDDYSWITCH_LAUNCHER_DIR}/runtime_lock.py"
BUDDYSWITCH_CODEX_CONFIG_HELPER="${BUDDYSWITCH_LAUNCHER_DIR}/codex_config.py"
BUDDYSWITCH_ENV_PROFILES_HELPER_REL="scripts/env_profiles.py"
BUDDYSWITCH_RUNTIME_AGENTS_HELPER_REL="scripts/runtime_agents.py"

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
}

buddyswitch_patch_codex_config() {
  local config_path
  local active_buddy
  local -a patch_args=()
  local -a temp_root_args=()
  config_path="${BUDDYSWITCH_CODEX_HOME}/config.toml"
  active_buddy="${BUDDYSWITCH_ACTIVE_BUDDY:-${BUDDYSWITCH_START_BUDDY:-}}"

  if [[ -n "${TMPDIR:-}" ]]; then
    temp_root_args+=(--temp-root "${TMPDIR}")
  fi

  patch_args=(
    --config "${config_path}"
    --repo-root "${BUDDYSWITCH_REPO_ROOT}"
    --shared-root "${BUDDYSWITCH_SHARED_ROOT}"
    --source-codex-home "${BUDDYSWITCH_SOURCE_CODEX_HOME}"
  )

  if [[ -n "${active_buddy}" ]]; then
    patch_args+=(
      --manifest "${BUDDYSWITCH_REPO_ROOT}/buddyswitch/manifest.toml"
      --buddy "${active_buddy}"
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
  fi

  python3 "${BUDDYSWITCH_CODEX_CONFIG_HELPER}" \
    "${patch_args[@]}" \
    --temp-root "/tmp" \
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

buddyswitch_require_env_profile() {
  local buddy_id="$1"
  local helper manifest_path

  helper="${BUDDYSWITCH_REPO_ROOT}/${BUDDYSWITCH_ENV_PROFILES_HELPER_REL}"
  manifest_path="${BUDDYSWITCH_REPO_ROOT}/buddyswitch/manifest.toml"

  if [[ ! -f "${helper}" ]]; then
    echo "Env profile helper missing: ${helper}" >&2
    return 1
  fi
  python3 "${helper}" --manifest "${manifest_path}" validate --buddy "${buddy_id}" >/dev/null
}

buddyswitch_buddy_agents_template_path() {
  local buddy_id="$1"
  printf '%s/tools/launcher/assets/buddies/%s/AGENTS.md\n' "${BUDDYSWITCH_REPO_ROOT}" "${buddy_id}"
}

buddyswitch_require_buddy_agents_template() {
  local buddy_id="$1"
  local template_path helper manifest_path

  template_path="$(buddyswitch_buddy_agents_template_path "${buddy_id}")"
  if [[ ! -f "${template_path}" ]]; then
    echo "Buddy AGENTS template not found: ${template_path}" >&2
    return 1
  fi
  helper="${BUDDYSWITCH_REPO_ROOT}/${BUDDYSWITCH_RUNTIME_AGENTS_HELPER_REL}"
  manifest_path="${BUDDYSWITCH_REPO_ROOT}/buddyswitch/manifest.toml"
  if [[ ! -f "${helper}" ]]; then
    echo "Runtime AGENTS helper missing: ${helper}" >&2
    return 1
  fi
  python3 "${helper}" --manifest "${manifest_path}" validate --buddy "${buddy_id}" --template "${template_path}" >/dev/null
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
  local status="${3:-active}"
  local instance_json instance_dir

  instance_json="$(buddyswitch_instance_json_path "${instance_id}")"
  instance_dir="$(dirname "${instance_json}")"
  mkdir -p "${instance_dir}"

  python3 - "${instance_json}" "${instance_id}" "${buddy}" "${status}" "${BUDDYSWITCH_WORKSPACE_DIR}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

instance_json = Path(sys.argv[1])
instance_id = sys.argv[2]
buddy = sys.argv[3]
status = sys.argv[4]
workspace_dir = sys.argv[5]
now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
payload = {
    "instance_id": instance_id,
    "buddy": buddy,
    "status": status,
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
  local marker_path="${BUDDYSWITCH_RUN_STATE_DIR}/launcher-${marker_pid}.json"
  mkdir -p "${BUDDYSWITCH_RUN_STATE_DIR}"
  python3 - \
    "${marker_path}" \
    "${marker_pid}" \
    "${BUDDYSWITCH_START_INSTANCE_ID:-${BUDDYSWITCH_INSTANCE_ID:-}}" \
    "${BUDDYSWITCH_START_BUDDY:-${BUDDYSWITCH_ACTIVE_BUDDY:-}}" \
    "${BUDDYSWITCH_WORKSPACE_DIR:-}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "pid": int(sys.argv[2]),
    "instance_id": sys.argv[3] or None,
    "buddy": sys.argv[4] or None,
    "workspace_dir": sys.argv[5] or None,
    "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
PY
  printf '%s\n' "${marker_path}"
}

buddyswitch_cleanup_pid_marker() {
  local marker_path="$1"
  rm -f "${marker_path}"
}

buddyswitch_count_active_launchers() {
  if [[ ! -d "${BUDDYSWITCH_RUN_STATE_DIR}" ]]; then
    echo "0"
    return
  fi

  python3 - "${BUDDYSWITCH_RUN_STATE_DIR}" <<'PY'
import json
import os
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
live_pids = set()


def pid_is_live(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def mark_pid(path, pid):
    if pid is not None and pid > 0 and pid_is_live(pid):
        live_pids.add(pid)
        return
    path.unlink(missing_ok=True)


for marker in run_dir.glob("launcher-*.json"):
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        pid = payload.get("pid")
    except Exception:
        pid = None
    mark_pid(marker, pid if isinstance(pid, int) else None)

for marker in run_dir.glob("launcher-*.pid"):
    try:
        pid = int(marker.read_text(encoding="utf-8").strip())
    except Exception:
        pid = None
    mark_pid(marker, pid)

print(len(live_pids))
PY
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
