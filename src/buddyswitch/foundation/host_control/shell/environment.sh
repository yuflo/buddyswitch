#!/usr/bin/env bash
set -euo pipefail

BUDDYSWITCH_PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

buddyswitch_resolve_python() {
  if [[ -z "${BUDDYSWITCH_PYTHON:-}" || "${BUDDYSWITCH_PYTHON}" != /* || ! -x "${BUDDYSWITCH_PYTHON}" ]] ||
    ! "${BUDDYSWITCH_PYTHON}" -c 'import sys' >/dev/null 2>&1; then
    echo "BuddySwitch requires the verified absolute runtime Python." >&2
    return 1
  fi
}

buddyswitch_env_init() {
  local source_home source_codex_home shared_root
  buddyswitch_resolve_python || return $?
  if [[ -z "${BUDDYSWITCH_RUNTIME_IDENTITY:-}" || -z "${BUDDYSWITCH_PROJECT_SOURCE:-}" || -z "${BUDDYSWITCH_SOURCE_ROOT:-}" ]]; then
    echo "BuddySwitch verified runtime identity is not initialized." >&2
    return 1
  fi
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
  export BUDDYSWITCH_ENV_MCP_NAME="${BUDDYSWITCH_ENV_MCP_NAME:-buddyswitch-env}"
  export BUDDYSWITCH_WORKSPACE_DIR="${BUDDYSWITCH_WORKSPACE_DIR:-${shared_root}/workspace}"
  export BUDDYSWITCH_PROJECT_WORKSPACE_DIR="${shared_root}/project/workspace"
}

buddyswitch_canonical_path() {
  "${BUDDYSWITCH_PYTHON}" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve(strict=False))' "$1"
}

buddyswitch_remove_owned_path() {
  local target="$1"
  [[ -n "${target}" ]] || return 0
  if [[ -L "${target}" ]]; then
    echo "Owned path removal blocked: target is a symlink (${target})." >&2
    return 3
  fi
  if [[ -f "${target}" ]]; then
    rm -f "${target}"
    return 0
  fi
  if [[ -d "${target}" ]]; then
    chmod -R u+w "${target}" 2>/dev/null || true
    find "${target}" -type d -exec chmod u+rwx {} + 2>/dev/null || true
    rm -rf "${target}"
  fi
}

buddyswitch_with_runtime_lock() {
  buddyswitch_require_runtime_lock || return $?
  "$@"
}

buddyswitch_require_runtime_lock() {
  "${BUDDYSWITCH_PYTHON}" - "${BUDDYSWITCH_SHARED_ROOT}" <<'PY'
import sys
from buddyswitch.foundation.process_runtime import runtime_lock
raise SystemExit(runtime_lock.assert_runtime_lock_held(sys.argv[1]))
PY
}

buddyswitch_instance_json_path() {
  printf '%s/instances/%s/instance.json\n' "${BUDDYSWITCH_SHARED_ROOT}" "$1"
}

buddyswitch_instance_root() {
  printf '%s/instances/%s\n' "${BUDDYSWITCH_SHARED_ROOT}" "$1"
}

buddyswitch_validate_actor_id() {
  local actor_id="$1"
  if [[ -z "${actor_id}" || ! "${actor_id}" =~ ^act-[A-Za-z0-9._-]+$ ]]; then
    echo "Invalid actor id: ${actor_id:-must not be empty.}" >&2
    return 2
  fi
}

buddyswitch_validate_role_id() {
  local role_id="$1"
  if [[ -z "${role_id}" || ! "${role_id}" =~ ^[a-z][a-z0-9-]*$ ]]; then
    echo "Invalid role id: ${role_id}" >&2
    return 2
  fi
}

buddyswitch_env_bind_instance() {
  local actor_id="$1" instance_root
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

buddyswitch_instance_activate() {
  "${BUDDYSWITCH_PYTHON}" -m buddyswitch.foundation.host_control.state activate \
    --path "$(buddyswitch_instance_json_path "$1")" --actor-id "$1" --role "$2" --status "${3:-active}" \
    --instance-root "${BUDDYSWITCH_INSTANCE_ROOT}" --workspace-dir "${BUDDYSWITCH_WORKSPACE_DIR}" \
    --project-workspace-dir "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}" \
    --codex-executable "${BUDDYSWITCH_CODEX_BIN}" --codex-version "${BUDDYSWITCH_CODEX_VERSION}" \
    --runtime-identity "${BUDDYSWITCH_RUNTIME_IDENTITY}"
  printf '%s\n' "$(buddyswitch_instance_json_path "$1")"
}

buddyswitch_instance_set_app_server() {
  "${BUDDYSWITCH_PYTHON}" -m buddyswitch.foundation.host_control.state set-app-server \
    --path "$(buddyswitch_instance_json_path "$1")" --actor-id "$1" --thread-id "$2" \
    --pid "$3" --socket-path "$4" --log-file "$5" --status "${6:-active}"
}

buddyswitch_instance_set_thread_id() {
  "${BUDDYSWITCH_PYTHON}" -m buddyswitch.foundation.host_control.state set-thread \
    --path "$(buddyswitch_instance_json_path "$1")" --actor-id "$1" --thread-id "$2"
}

buddyswitch_instance_clear_app_server() {
  "${BUDDYSWITCH_PYTHON}" -m buddyswitch.foundation.host_control.state clear-app-server \
    --path "$(buddyswitch_instance_json_path "$1")" --actor-id "$1" --status "${2:-inactive}"
}

buddyswitch_instance_record_failure() {
  local -a args=(record-failure --path "$(buddyswitch_instance_json_path "$1")" --actor-id "$1" --phase "$2" --message "$3")
  [[ -z "${4:-}" ]] || args+=(--thread-id "$4")
  [[ -z "${5:-}" ]] || args+=(--browser-port "$5")
  "${BUDDYSWITCH_PYTHON}" -m buddyswitch.foundation.host_control.state "${args[@]}"
}

buddyswitch_instance_app_server_is_active() {
  local actor_id="$1"
  [[ -n "${actor_id}" && -f "$(buddyswitch_instance_json_path "${actor_id}")" ]] || return 1
  (buddyswitch_env_bind_instance "${actor_id}" && buddyswitch_app_server_is_active)
}
