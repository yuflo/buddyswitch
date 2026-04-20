#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LAUNCHER_ENV_SH="${SOURCE_REPO_ROOT}/tools/launcher/env.sh"

if [[ ! -f "${LAUNCHER_ENV_SH}" ]]; then
  echo "Launcher env helper is missing under tools/launcher." >&2
  exit 1
fi

source "${LAUNCHER_ENV_SH}"

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

export BUDDYSWITCH_REPO_ROOT="${SOURCE_REPO_ROOT}"
buddyswitch_env_init

TARGET_ROOT="${BUDDYSWITCH_WORKSPACE_DIR}"

if [[ ! -d "${TARGET_ROOT}" ]]; then
  echo "Cleanup blocked: launcher runtime workspace not found at '${TARGET_ROOT}'." >&2
  echo "Run './buddyswitch-codex start' or './buddyswitch-codex browser ensure' first." >&2
  exit 1
fi

buddyswitch_cleanup_strip_legacy_runtime_excludes "${SOURCE_REPO_ROOT}"

if buddyswitch_cleanup_requests_all_storage "$@" && [[ "${SOURCE_REPO_ROOT}" != "${TARGET_ROOT}" ]]; then
  python3 "${SCRIPT_DIR}/env_cleanup.py" --repo-root "${SOURCE_REPO_ROOT}" --all-storage --execute --force >/dev/null
fi

cd "${SOURCE_REPO_ROOT}"
python3 "${SCRIPT_DIR}/env_cleanup.py" --repo-root "${TARGET_ROOT}" "$@"
