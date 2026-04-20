#!/usr/bin/env bash
set -euo pipefail

BUDDYSWITCH_LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUDDYSWITCH_WORKSPACE_HELPER="${BUDDYSWITCH_LAUNCHER_DIR}/workspace.sh"

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

  export BUDDYSWITCH_HOME="${shared_root}/home"
  export BUDDYSWITCH_CODEX_HOME="${shared_root}/codex-home"
  export BUDDYSWITCH_XDG_CONFIG_HOME="${BUDDYSWITCH_HOME}/.config"
  export BUDDYSWITCH_RUN_STATE_DIR="${shared_root}/run"
  export BUDDYSWITCH_REPO_ROOT="${BUDDYSWITCH_REPO_ROOT:-${REPO_ROOT:-$(cd "${BUDDYSWITCH_LAUNCHER_DIR}/../.." && pwd)}}"

  buddyswitch_workspace_init_defaults
}

buddyswitch_ensure_shared_env() {
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

  buddyswitch_workspace_prepare_execution_worktree
}

buddyswitch_codex_config_path() {
  printf '%s/config.toml\n' "${BUDDYSWITCH_CODEX_HOME}"
}

buddyswitch_run_codex() {
  HOME="${BUDDYSWITCH_HOME}" \
  CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
  XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
  codex "$@"
}

buddyswitch_write_launcher_marker() {
  local marker_path="${BUDDYSWITCH_RUN_STATE_DIR}/launcher-$$.pid"
  printf '%s\n' "$$" > "${marker_path}"
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
