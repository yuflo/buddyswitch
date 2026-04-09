#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

CONFIRM_PHRASE="DELETE_BUDDYSWITCH_DATA"

MODE_AGENT=""
MODE_ALL_AGENTS=0
MODE_PROJECT=""
MODE_ALL_STORAGE=0

EXECUTE=0
FORCE=0

TARGET_DIRS=()
DELETE_PATHS=()

usage() {
  cat <<'EOF'
BuddySwitch cleanup utility (manual use only)

Usage:
  scripts/cleanup_buddyswitch.sh [target] [mode]

Targets:
  --agent <buddy>                       Clean one buddy's runs and artifact objects/files
  --all-agents                          Clean all buddies' runs and all artifact objects/files
  --project app                         Clean project runtime data (projects/app/.runtime)
  --all-storage                         Clean all local storage data, including env object dumps

Modes:
  --dry-run                             Preview only (default)
  --execute                             Execute deletion (requires confirmation)
  --force                               Skip interactive confirmation (requires --execute)

Examples:
  scripts/cleanup_buddyswitch.sh --agent market
  scripts/cleanup_buddyswitch.sh --all-agents
  scripts/cleanup_buddyswitch.sh --project app --execute
  scripts/cleanup_buddyswitch.sh --all-storage --execute --force
EOF
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

load_valid_buddies() {
  python3 - <<'PY'
import sys, tomllib
from pathlib import Path
manifest = Path("buddyswitch/manifest.toml")
if not manifest.exists():
    sys.exit(1)
data = tomllib.loads(manifest.read_text(encoding="utf-8"))
for buddy in data.get("buddies", []):
    buddy_id = buddy.get("id")
    if isinstance(buddy_id, str):
        print(buddy_id)
PY
}

is_valid_buddy() {
  local needle="$1"
  local buddy
  while IFS= read -r buddy; do
    [[ -z "${buddy}" ]] && continue
    if [[ "${buddy}" == "${needle}" ]]; then
      return 0
    fi
  done < <(load_valid_buddies || true)
  return 1
}

add_target_dir() {
  local dir="$1"
  local existing
  for existing in "${TARGET_DIRS[@]:-}"; do
    if [[ "${existing}" == "${dir}" ]]; then
      return 0
    fi
  done
  TARGET_DIRS+=("${dir}")
}

rel_path() {
  local p="$1"
  echo "${p#${REPO_ROOT}/}"
}

is_safe_delete_path() {
  local p="$1"
  case "${p}" in
    artifacts/*) return 0 ;;
    runs/raw/*) return 0 ;;
    runs/summaries/*) return 0 ;;
    projects/app/.runtime/*) return 0 ;;
    buddyswitch/objects/*) return 0 ;;
    *) return 1 ;;
  esac
}

count_entries() {
  local dir="$1"
  if [[ ! -d "${dir}" ]]; then
    echo 0
    return 0
  fi
  local count=0
  local path
  while IFS= read -r path; do
    count=$((count + 1))
  done < <(find "${dir}" -mindepth 1 \( -type f -o -type l \) ! -name ".gitkeep" -print)
  echo "${count}"
}

gather_delete_paths() {
  local dir path
  DELETE_PATHS=()
  for dir in "${TARGET_DIRS[@]}"; do
    if [[ ! -d "${dir}" ]]; then
      continue
    fi
    while IFS= read -r path; do
      [[ -z "${path}" ]] && continue
      DELETE_PATHS+=("${path}")
    done < <(find "${dir}" -mindepth 1 \( -type f -o -type l \) ! -name ".gitkeep" -print)
  done
}

print_env_cleanup_plan() {
  echo "Env object cleanup:"
  if [[ -n "${MODE_AGENT}" ]]; then
    python3 scripts/env_artifacts.py cleanup-buddy --buddy "${MODE_AGENT}" --delete-files --dry-run
    return 0
  fi
  if [[ ${MODE_ALL_AGENTS} -eq 1 ]]; then
    python3 scripts/env_artifacts.py cleanup-all --delete-files --dry-run
    if [[ -d "buddyswitch/objects/tracks" ]]; then
      echo "Would delete track objects under buddyswitch/objects/tracks/"
    fi
    return 0
  fi
  if [[ ${MODE_ALL_STORAGE} -eq 1 ]]; then
    echo "Would delete all object dumps under buddyswitch/objects/"
    return 0
  fi
  echo "No env object changes."
}

print_plan() {
  local dir count
  echo "BuddySwitch cleanup plan"
  echo "Repo root: ${REPO_ROOT}"
  echo
  echo "Targets:"
  for dir in "${TARGET_DIRS[@]}"; do
    count="$(count_entries "${dir}")"
    echo "  - ${dir} (entries to delete: ${count})"
  done
  echo
  echo "Delete candidates (excluding .gitkeep): ${#DELETE_PATHS[@]}"
  if [[ ${#DELETE_PATHS[@]} -gt 0 ]]; then
    local p
    for p in "${DELETE_PATHS[@]}"; do
      echo "  - $(rel_path "${p}")"
    done
  fi
  print_env_cleanup_plan
  echo
}

ensure_required_skeleton() {
  mkdir -p \
    artifacts \
    runs/raw \
    runs/summaries \
    projects/app/.runtime \
    buddyswitch/objects/tracks \
    buddyswitch/objects/artifacts

  : > runs/raw/.gitkeep
  : > runs/summaries/.gitkeep
  : > projects/app/.runtime/.gitkeep
  : > buddyswitch/objects/tracks/.gitkeep
  : > buddyswitch/objects/artifacts/.gitkeep
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent)
        [[ $# -lt 2 ]] && fail "--agent requires a value"
        MODE_AGENT="$2"
        shift 2
        ;;
      --all-agents)
        MODE_ALL_AGENTS=1
        shift
        ;;
      --project)
        [[ $# -lt 2 ]] && fail "--project requires a value"
        MODE_PROJECT="$2"
        shift 2
        ;;
      --all-storage)
        MODE_ALL_STORAGE=1
        shift
        ;;
      --dry-run)
        EXECUTE=0
        shift
        ;;
      --execute)
        EXECUTE=1
        shift
        ;;
      --force)
        FORCE=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown argument: $1 (use --help)"
        ;;
    esac
  done
}

validate_modes() {
  local target_count=0

  [[ -n "${MODE_AGENT}" ]] && target_count=$((target_count + 1))
  [[ ${MODE_ALL_AGENTS} -eq 1 ]] && target_count=$((target_count + 1))
  [[ -n "${MODE_PROJECT}" ]] && target_count=$((target_count + 1))
  [[ ${MODE_ALL_STORAGE} -eq 1 ]] && target_count=$((target_count + 1))

  [[ ${target_count} -eq 0 ]] && fail "No cleanup target provided"
  [[ ${target_count} -gt 1 ]] && fail "Conflicting targets. Choose one of --agent, --all-agents, --project, --all-storage"

  if [[ -n "${MODE_AGENT}" ]] && ! is_valid_buddy "${MODE_AGENT}"; then
    fail "Invalid buddy '${MODE_AGENT}'. Check buddyswitch/manifest.toml"
  fi

  if [[ -n "${MODE_PROJECT}" ]] && [[ "${MODE_PROJECT}" != "app" ]]; then
    fail "Invalid project '${MODE_PROJECT}'. Only 'app' is supported"
  fi

  if [[ ${FORCE} -eq 1 && ${EXECUTE} -ne 1 ]]; then
    fail "--force can only be used with --execute"
  fi
}

build_targets() {
  if [[ -n "${MODE_AGENT}" ]]; then
    add_target_dir "runs/raw/${MODE_AGENT}"
    add_target_dir "runs/summaries/${MODE_AGENT}"
    return 0
  fi

  if [[ ${MODE_ALL_AGENTS} -eq 1 ]]; then
    local buddy
    while IFS= read -r buddy; do
      [[ -z "${buddy}" ]] && continue
      add_target_dir "runs/raw/${buddy}"
      add_target_dir "runs/summaries/${buddy}"
    done < <(load_valid_buddies || true)
    return 0
  fi

  if [[ -n "${MODE_PROJECT}" ]]; then
    add_target_dir "projects/app/.runtime"
    return 0
  fi

  if [[ ${MODE_ALL_STORAGE} -eq 1 ]]; then
    add_target_dir "artifacts"
    add_target_dir "runs/raw"
    add_target_dir "runs/summaries"
    add_target_dir "projects/app/.runtime"
    add_target_dir "buddyswitch/objects/tracks"
    add_target_dir "buddyswitch/objects/artifacts"
  fi
}

confirm_execute() {
  if [[ ${FORCE} -eq 1 ]]; then
    return 0
  fi

  if [[ ! -t 0 ]]; then
    fail "--execute requires interactive confirmation, or use --force"
  fi

  echo "Type '${CONFIRM_PHRASE}' to confirm deletion:"
  local answer=""
  read -r answer
  if [[ "${answer}" != "${CONFIRM_PHRASE}" ]]; then
    fail "Confirmation phrase mismatch. Aborted."
  fi
}

run_delete() {
  local p
  if [[ ${#DELETE_PATHS[@]} -eq 0 ]]; then
    return 0
  fi

  for p in "${DELETE_PATHS[@]:-}"; do
    [[ -z "${p}" ]] && continue
    p="$(rel_path "${p}")"
    if ! is_safe_delete_path "${p}"; then
      fail "Unsafe delete path blocked: ${p}"
    fi
    rm -rf "${p}"
  done
}

run_env_cleanup() {
  if [[ -n "${MODE_AGENT}" ]]; then
    python3 scripts/env_artifacts.py cleanup-buddy --buddy "${MODE_AGENT}" --delete-files
    return 0
  fi

  if [[ ${MODE_ALL_AGENTS} -eq 1 ]]; then
    python3 scripts/env_artifacts.py cleanup-all --delete-files
    if [[ -d "buddyswitch/objects/tracks" ]]; then
      find "buddyswitch/objects/tracks" -mindepth 1 -type f ! -name ".gitkeep" -delete
    fi
    return 0
  fi

  return 0
}

main() {
  parse_args "$@"
  validate_modes
  build_targets
  gather_delete_paths
  print_plan

  if [[ ${EXECUTE} -ne 1 ]]; then
    echo "Dry-run mode: no files were deleted."
    exit 0
  fi

  confirm_execute
  run_delete
  run_env_cleanup
  ensure_required_skeleton
  echo "Cleanup completed."
}

main "$@"
