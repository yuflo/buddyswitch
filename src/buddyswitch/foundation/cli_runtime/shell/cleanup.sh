#!/usr/bin/env bash
set -euo pipefail

buddyswitch_cleanup_usage_hint() {
  echo "Use: buddyswitch-codex data cleanup --role <role>|--all-data [--yes]" >&2
}

BUDDYSWITCH_CLEANUP_SCOPE=""
BUDDYSWITCH_CLEANUP_ROLE=""
BUDDYSWITCH_CLEANUP_YES=0

buddyswitch_cleanup_parse_args() {
  local target_seen=0
  BUDDYSWITCH_CLEANUP_SCOPE=""
  BUDDYSWITCH_CLEANUP_ROLE=""
  BUDDYSWITCH_CLEANUP_YES=0

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --role)
        if [[ "${target_seen}" -eq 1 ]]; then
          echo "data cleanup target must be specified exactly once" >&2
          return 2
        fi
        target_seen=1
        BUDDYSWITCH_CLEANUP_SCOPE="role"
        shift
        if [[ "$#" -gt 0 && -n "${1:-}" && "${1:-}" != --* ]]; then
          BUDDYSWITCH_CLEANUP_ROLE="$1"
          shift
        else
          echo "Missing value for --role" >&2
          return 2
        fi
        ;;
      --all-data)
        if [[ "${target_seen}" -eq 1 ]]; then
          echo "data cleanup target must be specified exactly once" >&2
          return 2
        fi
        target_seen=1
        BUDDYSWITCH_CLEANUP_SCOPE="all-data"
        shift
        ;;
      --yes)
        BUDDYSWITCH_CLEANUP_YES=1
        shift
        ;;
      *)
        echo "Unknown data cleanup option: $1" >&2
        buddyswitch_cleanup_usage_hint
        return 2
        ;;
    esac
  done

  if [[ -z "${BUDDYSWITCH_CLEANUP_SCOPE}" ]]; then
    echo "data cleanup target is required" >&2
    buddyswitch_cleanup_usage_hint
    return 2
  fi
}

buddyswitch_cleanup_run_env_cleanup() {
  local repo_root="$1"
  local scope="$2"
  local -a target_args
  local -a execute_args=()

  case "${scope}" in
    role)
      target_args=(--role "${BUDDYSWITCH_CLEANUP_ROLE}")
      ;;
    all-data)
      target_args=(--all-data)
      ;;
    *)
      echo "Cleanup blocked: unsupported cleanup scope '${scope}'." >&2
      return 2
      ;;
  esac

  if [[ "${BUDDYSWITCH_CLEANUP_YES}" -eq 1 ]]; then
    execute_args=(--yes)
  fi
  "${BUDDYSWITCH_PYTHON}" -m "${BUDDYSWITCH_CLI_RUNTIME_CLEANUP_MODULE:?}" \
    --state-root "${repo_root}" \
    --shared-root "${BUDDYSWITCH_SHARED_ROOT}" \
    "${target_args[@]}" \
    "${execute_args[@]}"
}

buddyswitch_count_active_browsers() {
  if buddyswitch_browser_pid_marker_is_active "$(buddyswitch_browser_pid_marker)"; then
    echo "1"
    return 0
  fi
  if buddyswitch_browser_any_instance_pid_marker_is_active; then
    echo "1"
    return 0
  fi
  if buddyswitch_browser_any_recorded_instance_endpoint_is_active; then
    echo "1"
    return 0
  fi
  if buddyswitch_browser_check_endpoint 2>/dev/null; then
    echo "1"
    return 0
  fi
  echo "0"
}

buddyswitch_count_active_browsers_for_role() {
  local role="$1"
  local instance_json actor_id instance_role

  if buddyswitch_browser_pid_marker_is_active "$(buddyswitch_browser_pid_marker)"; then
    echo "1"
    return 0
  fi
  if buddyswitch_browser_check_endpoint 2>/dev/null; then
    echo "1"
    return 0
  fi

  for instance_json in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/instance.json; do
    [[ -f "${instance_json}" ]] || continue
    instance_role="$(
      "${BUDDYSWITCH_PYTHON}" - "${instance_json}" <<'PY'
import json
import sys
from pathlib import Path

try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
role = payload.get("role")
if isinstance(role, str):
    print(role)
PY
    )"
    [[ "${instance_role}" == "${role}" ]] || continue
    actor_id="$(basename "$(dirname "${instance_json}")")"
    if buddyswitch_browser_instance_pid_marker_is_active "${actor_id}"; then
      echo "1"
      return 0
    fi
    if buddyswitch_browser_instance_endpoint_is_active "${actor_id}"; then
      echo "1"
      return 0
    fi
  done

  echo "0"
}

buddyswitch_cleanup_validate_shared_root() {
  local shared_root="${BUDDYSWITCH_SHARED_ROOT:-}"

  if [[ -L "${shared_root}" ]]; then
    echo "Cleanup blocked: shared root is a symlink (${shared_root})." >&2
    return 1
  fi
}

buddyswitch_cleanup_run_locked() {
  local state_root="${BUDDYSWITCH_SHARED_ROOT}/state"
  local target_root=""
  local target_scope=""
  local active_count active_browser_count

  buddyswitch_require_runtime_lock
  buddyswitch_cleanup_validate_shared_root || return $?
  buddyswitch_cleanup_parse_args "$@" || return $?

  if [[ "${BUDDYSWITCH_CLEANUP_SCOPE}" == "role" ]]; then
    active_count="$(buddyswitch_count_active_app_servers_for_role "${BUDDYSWITCH_CLEANUP_ROLE}")"
  else
    active_count="$(buddyswitch_count_active_app_servers)"
  fi
  if [[ "${active_count}" -gt 0 ]]; then
    echo "Cleanup blocked: ${active_count} active buddyswitch-codex instance(s) detected." >&2
    echo "Close active launcher sessions and retry." >&2
    return 3
  fi

  if [[ "${BUDDYSWITCH_CLEANUP_SCOPE}" == "role" ]]; then
    active_browser_count="$(buddyswitch_count_active_browsers_for_role "${BUDDYSWITCH_CLEANUP_ROLE}")"
  else
    active_browser_count="$(buddyswitch_count_active_browsers)"
  fi
  if [[ "${active_browser_count}" -gt 0 ]]; then
    echo "Cleanup blocked: ${active_browser_count} active browser instance(s) detected." >&2
    echo "Close active browser sessions and retry." >&2
    return 3
  fi

  target_root="${state_root}"
  target_scope="${BUDDYSWITCH_CLEANUP_SCOPE}"

  buddyswitch_cleanup_run_env_cleanup "${target_root}" "${target_scope}"
}
