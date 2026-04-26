#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LAUNCHER_ENV_SH="${SOURCE_REPO_ROOT}/tools/launcher/env.sh"
LAUNCHER_BROWSER_SH="${SOURCE_REPO_ROOT}/tools/launcher/browser_cockpit.sh"

if [[ ! -f "${LAUNCHER_ENV_SH}" || ! -f "${LAUNCHER_BROWSER_SH}" ]]; then
  echo "Launcher helpers are missing under tools/launcher." >&2
  exit 1
fi

source "${LAUNCHER_ENV_SH}"
source "${LAUNCHER_BROWSER_SH}"

buddyswitch_cleanup_strip_legacy_runtime_excludes() {
  local repo_root="$1"
  local exclude_path="${repo_root}/.git/info/exclude"
  local temp_path

  if [[ ! -f "${exclude_path}" ]]; then
    return 0
  fi

  temp_path="$(mktemp)"
  grep -Fvx "# BuddySwitch runtime-only excludes" "${exclude_path}" \
    | grep -Fvx "buddyswitch/content/runs/**" \
    | grep -Fvx "buddyswitch/objects/tracks/**" \
    | grep -Fvx "buddyswitch/objects/tasks/**" \
    | grep -Fvx "buddyswitch/objects/artifacts/**" \
    | grep -Fvx "runs/raw/**" \
    | grep -Fvx "projects/app/.runtime/**" > "${temp_path}" || true
  mv "${temp_path}" "${exclude_path}"
}

buddyswitch_cleanup_requests_all_storage() {
  local arg
  for arg in "$@"; do
    if [[ "${arg}" == "--all-storage" ]]; then
      return 0
    fi
  done
  return 1
}

buddyswitch_cleanup_requests_execute() {
  local arg
  for arg in "$@"; do
    if [[ "${arg}" == "--execute" ]]; then
      return 0
    fi
  done
  return 1
}

BUDDYSWITCH_CLEANUP_SCOPE=""
BUDDYSWITCH_CLEANUP_BUDDY=""
BUDDYSWITCH_CLEANUP_PROJECT=""
BUDDYSWITCH_CLEANUP_COMMON_ARGS=()

buddyswitch_cleanup_parse_args() {
  BUDDYSWITCH_CLEANUP_SCOPE=""
  BUDDYSWITCH_CLEANUP_BUDDY=""
  BUDDYSWITCH_CLEANUP_PROJECT=""
  BUDDYSWITCH_CLEANUP_COMMON_ARGS=()

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --agent)
        BUDDYSWITCH_CLEANUP_SCOPE="agent"
        shift
        if [[ "$#" -gt 0 ]]; then
          BUDDYSWITCH_CLEANUP_BUDDY="$1"
          shift
        else
          BUDDYSWITCH_CLEANUP_BUDDY=""
        fi
        ;;
      --all-agents)
        BUDDYSWITCH_CLEANUP_SCOPE="all-agents"
        shift
        ;;
      --project)
        BUDDYSWITCH_CLEANUP_SCOPE="project"
        shift
        if [[ "$#" -gt 0 ]]; then
          BUDDYSWITCH_CLEANUP_PROJECT="$1"
          shift
        else
          BUDDYSWITCH_CLEANUP_PROJECT=""
        fi
        ;;
      --all-storage)
        BUDDYSWITCH_CLEANUP_SCOPE="all-storage"
        shift
        ;;
      *)
        BUDDYSWITCH_CLEANUP_COMMON_ARGS+=("$1")
        shift
        ;;
    esac
  done
}

buddyswitch_cleanup_run_env_cleanup() {
  local repo_root="$1"
  local scope="$2"
  local -a target_args

  case "${scope}" in
    agent)
      target_args=(--agent "${BUDDYSWITCH_CLEANUP_BUDDY}")
      ;;
    all-agents)
      target_args=(--all-agents)
      ;;
    project)
      target_args=(--project "${BUDDYSWITCH_CLEANUP_PROJECT:-app}")
      ;;
    all-storage)
      target_args=(--all-storage)
      ;;
    *)
      echo "Cleanup blocked: unsupported cleanup scope '${scope}'." >&2
      return 2
      ;;
  esac

  python3 "${SCRIPT_DIR}/env_cleanup.py" \
    --repo-root "${repo_root}" \
    "${target_args[@]}" \
    "${BUDDYSWITCH_CLEANUP_COMMON_ARGS[@]}"
}

buddyswitch_count_active_browsers() {
  if buddyswitch_browser_is_active; then
    echo "1"
    return 0
  fi
  echo "0"
}

buddyswitch_cleanup_first_instance_workspace() {
  local instances_root="$1"
  local instance_root workspace_dir

  if [[ ! -d "${instances_root}" ]]; then
    return 1
  fi

  for instance_root in "${instances_root}"/inst-*; do
    if [[ ! -d "${instance_root}" ]]; then
      continue
    fi
    workspace_dir="${instance_root}/workspace"
    if [[ -d "${workspace_dir}" ]]; then
      printf '%s\n' "${workspace_dir}"
      return 0
    fi
  done
  return 1
}

buddyswitch_cleanup_instance_buddy() {
  local instance_root="$1"
  local instance_json="${instance_root}/instance.json"

  if [[ ! -f "${instance_json}" ]]; then
    return 0
  fi

  python3 - "${instance_json}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
try:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(0)
if isinstance(payload, dict):
    buddy = payload.get("buddy")
    if isinstance(buddy, str):
        print(buddy.strip())
PY
}

buddyswitch_cleanup_apply_instance_local_cleanup() {
  local instances_root="$1"
  local scope="$2"
  local buddy="$3"
  local instance_root instance_workspace instance_buddy

  if [[ ! -d "${instances_root}" ]]; then
    return 0
  fi

  for instance_root in "${instances_root}"/inst-*; do
    if [[ ! -d "${instance_root}" ]]; then
      continue
    fi

    if [[ "${scope}" == "agent" ]]; then
      instance_buddy="$(buddyswitch_cleanup_instance_buddy "${instance_root}" || true)"
      if [[ "${instance_buddy}" != "${buddy}" ]]; then
        continue
      fi
    fi

    case "${scope}" in
      agent)
        instance_workspace="${instance_root}/workspace"
        rm -rf "${instance_workspace}/runs/raw/${buddy}"
        mkdir -p "${instance_workspace}/runs/raw"
        ;;
      all-agents)
        instance_workspace="${instance_root}/workspace"
        rm -rf "${instance_workspace}/runs/raw"
        mkdir -p "${instance_workspace}/runs/raw"
        ;;
      project)
        instance_workspace="${instance_root}/workspace"
        rm -rf "${instance_workspace}/projects/app/.runtime"
        mkdir -p "${instance_workspace}/projects/app/.runtime"
        ;;
      all-storage)
        buddyswitch_workspace_remove_registered_worktrees_under "${instance_root}"
        rm -rf "${instance_root}"
        ;;
    esac
  done
}

buddyswitch_cleanup_trim_state_skeleton() {
  local state_root="$1"
  rm -rf "${state_root}/runs" "${state_root}/projects"
}

export BUDDYSWITCH_REPO_ROOT="${SOURCE_REPO_ROOT}"
buddyswitch_env_init
buddyswitch_browser_init_defaults

run_cleanup_locked() {
  local legacy_workspace_root="${BUDDYSWITCH_WORKSPACE_DIR}"
  local state_root="${BUDDYSWITCH_SHARED_ROOT}/state"
  local instances_root="${BUDDYSWITCH_SHARED_ROOT}/instances"
  local target_root=""
  local target_scope=""
  local first_instance_workspace=""
  local active_count active_browser_count

  buddyswitch_require_runtime_lock

  active_count="$(buddyswitch_count_active_launchers)"
  if [[ "${active_count}" -gt 0 ]]; then
    echo "Cleanup blocked: ${active_count} active buddyswitch-codex instance(s) detected." >&2
    echo "Close active launcher sessions and retry." >&2
    return 3
  fi

  active_browser_count="$(buddyswitch_count_active_browsers)"
  if [[ "${active_browser_count}" -gt 0 ]]; then
    echo "Cleanup blocked: ${active_browser_count} active browser instance(s) detected." >&2
    echo "Close active browser sessions and retry." >&2
    return 3
  fi

  buddyswitch_cleanup_parse_args "$@"
  first_instance_workspace="$(buddyswitch_cleanup_first_instance_workspace "${instances_root}" || true)"

  if [[ -d "${state_root}" ]]; then
    case "${BUDDYSWITCH_CLEANUP_SCOPE}" in
      agent | all-agents | all-storage)
        target_root="${state_root}"
        target_scope="${BUDDYSWITCH_CLEANUP_SCOPE}"
        ;;
    esac
  fi

  if [[ -z "${target_root}" && -d "${legacy_workspace_root}" ]]; then
    target_root="${legacy_workspace_root}"
    target_scope="${BUDDYSWITCH_CLEANUP_SCOPE}"
  fi

  if [[ -z "${target_root}" && "${BUDDYSWITCH_CLEANUP_SCOPE}" == "project" && -n "${first_instance_workspace}" ]]; then
    target_root="${first_instance_workspace}"
    target_scope="project"
  fi

  if [[ -z "${target_root}" ]]; then
    echo "Cleanup blocked: launcher runtime workspace not found at '${target_root}'." >&2
    echo "Run './buddyswitch-codex start' or './buddyswitch-codex browser ensure' first." >&2
    return 1
  fi

  if buddyswitch_cleanup_requests_execute "${BUDDYSWITCH_CLEANUP_COMMON_ARGS[@]}"; then
    buddyswitch_cleanup_strip_legacy_runtime_excludes "${SOURCE_REPO_ROOT}"
    if buddyswitch_cleanup_requests_all_storage "$@" && [[ "${SOURCE_REPO_ROOT}" != "${legacy_workspace_root}" ]]; then
      python3 "${SCRIPT_DIR}/env_cleanup.py" --repo-root "${SOURCE_REPO_ROOT}" --all-storage --execute --force >/dev/null
    fi
  fi

  cd "${SOURCE_REPO_ROOT}"
  buddyswitch_cleanup_run_env_cleanup "${target_root}" "${target_scope}"

  if buddyswitch_cleanup_requests_execute "${BUDDYSWITCH_CLEANUP_COMMON_ARGS[@]}"; then
    buddyswitch_cleanup_apply_instance_local_cleanup \
      "${instances_root}" \
      "${BUDDYSWITCH_CLEANUP_SCOPE}" \
      "${BUDDYSWITCH_CLEANUP_BUDDY}"
    if [[ "${target_root}" == "${state_root}" ]]; then
      buddyswitch_cleanup_trim_state_skeleton "${state_root}"
    fi
  fi
}

main() {
  if [[ "${1:-}" == "__locked-cleanup" ]]; then
    shift || true
    run_cleanup_locked "$@"
    return
  fi

  buddyswitch_with_runtime_lock "${SCRIPT_DIR}/cleanup_buddyswitch.sh" "__locked-cleanup" "$@"
}

main "$@"
