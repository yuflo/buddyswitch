#!/usr/bin/env bash
set -euo pipefail

BUDDYSWITCH_CLEANUP_HELPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUDDYSWITCH_CLEANUP_REPO_ROOT="$(cd "${BUDDYSWITCH_CLEANUP_HELPER_DIR}/../.." && pwd)"
BUDDYSWITCH_CLEANUP_ENV_CLEANUP="${BUDDYSWITCH_CLEANUP_REPO_ROOT}/scripts/env_cleanup.py"
BUDDYSWITCH_CLEANUP_MANIFEST="${BUDDYSWITCH_CLEANUP_REPO_ROOT}/buddyswitch/manifest.toml"

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

buddyswitch_cleanup_requests_execute() {
  local arg
  for arg in "$@"; do
    if [[ "${arg}" == "--yes" ]]; then
      return 0
    fi
  done
  return 1
}

BUDDYSWITCH_CLEANUP_SCOPE=""
BUDDYSWITCH_CLEANUP_BUDDY=""
BUDDYSWITCH_CLEANUP_COMMON_ARGS=()

buddyswitch_cleanup_parse_args() {
  local target_seen=0
  BUDDYSWITCH_CLEANUP_SCOPE=""
  BUDDYSWITCH_CLEANUP_BUDDY=""
  BUDDYSWITCH_CLEANUP_COMMON_ARGS=()

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --buddy)
        if [[ "${target_seen}" -eq 1 ]]; then
          echo "data cleanup target must be specified exactly once" >&2
          return 2
        fi
        target_seen=1
        BUDDYSWITCH_CLEANUP_SCOPE="buddy"
        shift
        if [[ "$#" -gt 0 && -n "${1:-}" && "${1:-}" != --* ]]; then
          BUDDYSWITCH_CLEANUP_BUDDY="$1"
          shift
        else
          echo "Missing value for --buddy" >&2
          return 2
        fi
        ;;
      --app-runtime)
        if [[ "${target_seen}" -eq 1 ]]; then
          echo "data cleanup target must be specified exactly once" >&2
          return 2
        fi
        target_seen=1
        BUDDYSWITCH_CLEANUP_SCOPE="app-runtime"
        shift
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
        BUDDYSWITCH_CLEANUP_COMMON_ARGS+=("--yes")
        shift
        ;;
      --json)
        BUDDYSWITCH_CLEANUP_COMMON_ARGS+=("--json")
        shift
        ;;
      --agent | --all-agents | --project | --all-storage | --execute | --force)
        echo "Removed data cleanup option: $1" >&2
        echo "Use: buddyswitch-codex data cleanup --buddy <buddy>|--app-runtime|--all-data [--yes] [--json]" >&2
        return 2
        ;;
      *)
        echo "Unknown data cleanup option: $1" >&2
        echo "Use: buddyswitch-codex data cleanup --buddy <buddy>|--app-runtime|--all-data [--yes] [--json]" >&2
        return 2
        ;;
    esac
  done

  if [[ -z "${BUDDYSWITCH_CLEANUP_SCOPE}" ]]; then
    echo "data cleanup target is required" >&2
    echo "Use: buddyswitch-codex data cleanup --buddy <buddy>|--app-runtime|--all-data [--yes] [--json]" >&2
    return 2
  fi
}

buddyswitch_cleanup_run_env_cleanup() {
  local repo_root="$1"
  local scope="$2"
  local -a target_args

  case "${scope}" in
    buddy)
      target_args=(--buddy "${BUDDYSWITCH_CLEANUP_BUDDY}")
      ;;
    app-runtime)
      target_args=(--app-runtime)
      ;;
    all-data)
      target_args=(--all-data)
      ;;
    *)
      echo "Cleanup blocked: unsupported cleanup scope '${scope}'." >&2
      return 2
      ;;
  esac

  if [[ "${#BUDDYSWITCH_CLEANUP_COMMON_ARGS[@]}" -gt 0 ]]; then
    python3 "${BUDDYSWITCH_CLEANUP_ENV_CLEANUP}" \
      --repo-root "${repo_root}" \
      --shared-root "${BUDDYSWITCH_SHARED_ROOT}" \
      --manifest "${BUDDYSWITCH_CLEANUP_MANIFEST}" \
      "${target_args[@]}" \
      "${BUDDYSWITCH_CLEANUP_COMMON_ARGS[@]}"
  else
    python3 "${BUDDYSWITCH_CLEANUP_ENV_CLEANUP}" \
      --repo-root "${repo_root}" \
      --shared-root "${BUDDYSWITCH_SHARED_ROOT}" \
      --manifest "${BUDDYSWITCH_CLEANUP_MANIFEST}" \
      "${target_args[@]}"
  fi
}

buddyswitch_count_active_launchers_for_buddy() {
  local buddy="$1"
  if [[ ! -d "${BUDDYSWITCH_RUN_STATE_DIR}" ]]; then
    echo "0"
    return
  fi

  python3 - "${BUDDYSWITCH_RUN_STATE_DIR}" "${BUDDYSWITCH_SHARED_ROOT}" "${buddy}" <<'PY'
import json
import os
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
shared_root = Path(sys.argv[2])
target_buddy = sys.argv[3]
live_pids = set()


def pid_is_live(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def marker_matches_target(payload):
    buddy = payload.get("buddy")
    if buddy == target_buddy:
        return True
    if isinstance(buddy, str) and buddy:
        return False
    instance_id = payload.get("instance_id")
    if not isinstance(instance_id, str) or not instance_id:
        return True
    instance_json = shared_root / "instances" / instance_id / "instance.json"
    try:
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
    except Exception:
        return True
    return instance_payload.get("buddy") == target_buddy


for marker in run_dir.glob("launcher-*.json"):
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        pid = payload.get("pid")
    except Exception:
        marker.unlink(missing_ok=True)
        continue
    if not isinstance(pid, int) or pid <= 0 or not pid_is_live(pid):
        marker.unlink(missing_ok=True)
        continue
    if marker_matches_target(payload):
        live_pids.add(pid)

for marker in run_dir.glob("launcher-*.pid"):
    try:
        pid = int(marker.read_text(encoding="utf-8").strip())
    except Exception:
        marker.unlink(missing_ok=True)
        continue
    if not pid_is_live(pid):
        marker.unlink(missing_ok=True)
        continue
    live_pids.add(pid)

print(len(live_pids))
PY
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

buddyswitch_count_active_browsers_for_buddy() {
  local buddy="$1"
  local instance_json instance_id instance_buddy

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
    instance_buddy="$(
      python3 - "${instance_json}" <<'PY'
import json
import sys
from pathlib import Path

try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
buddy = payload.get("buddy")
if isinstance(buddy, str):
    print(buddy)
PY
    )"
    [[ "${instance_buddy}" == "${buddy}" ]] || continue
    instance_id="$(basename "$(dirname "${instance_json}")")"
    if buddyswitch_browser_instance_pid_marker_is_active "${instance_id}"; then
      echo "1"
      return 0
    fi
    if buddyswitch_browser_instance_endpoint_is_active "${instance_id}"; then
      echo "1"
      return 0
    fi
  done

  echo "0"
}

buddyswitch_cleanup_trim_state_skeleton() {
  local state_root="$1"
  rm -rf "${state_root}/runs" "${state_root}/projects"
}

buddyswitch_cleanup_validate_shared_root() {
  local shared_root="${BUDDYSWITCH_SHARED_ROOT:-}"

  if [[ -L "${shared_root}" ]]; then
    echo "Cleanup blocked: shared root is a symlink (${shared_root})." >&2
    return 1
  fi
}

buddyswitch_cleanup_main() {
  buddyswitch_with_runtime_lock "${BUDDYSWITCH_CLEANUP_REPO_ROOT}/buddyswitch-codex" "__locked-cleanup" "$@"
}

buddyswitch_cleanup_run_locked() {
  local state_root="${BUDDYSWITCH_SHARED_ROOT}/state"
  local target_root=""
  local target_scope=""
  local active_count active_browser_count

  buddyswitch_require_runtime_lock
  buddyswitch_cleanup_validate_shared_root || return $?
  buddyswitch_cleanup_parse_args "$@" || return $?

  if [[ "${BUDDYSWITCH_CLEANUP_SCOPE}" == "buddy" ]]; then
    active_count="$(buddyswitch_count_active_launchers_for_buddy "${BUDDYSWITCH_CLEANUP_BUDDY}")"
  else
    active_count="$(buddyswitch_count_active_launchers)"
  fi
  if [[ "${active_count}" -gt 0 ]]; then
    echo "Cleanup blocked: ${active_count} active buddyswitch-codex instance(s) detected." >&2
    echo "Close active launcher sessions and retry." >&2
    return 3
  fi

  if [[ "${BUDDYSWITCH_CLEANUP_SCOPE}" == "buddy" ]]; then
    active_browser_count="$(buddyswitch_count_active_browsers_for_buddy "${BUDDYSWITCH_CLEANUP_BUDDY}")"
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

  cd "${BUDDYSWITCH_CLEANUP_REPO_ROOT}"
  buddyswitch_cleanup_run_env_cleanup "${target_root}" "${target_scope}"
}
