#!/usr/bin/env bash
set -euo pipefail

buddyswitch_instance_usage() {
  cat <<EOF
Usage:
  buddyswitch-codex instance buddies [--json]
  buddyswitch-codex instance start --buddy <buddy> [--json]
  buddyswitch-codex instance input <instance-id> --text <text> [--input-wrapper raw|task-tui] [--json]
  buddyswitch-codex instance side <instance-id> --text <text> [--json]
  buddyswitch-codex instance side <instance-id> --side-thread-id <side-thread-id> --text <text> [--json]
  buddyswitch-codex instance side close <instance-id> --side-thread-id <side-thread-id> [--json]
  buddyswitch-codex instance goal <instance-id> get|set|clear [--json]
  buddyswitch-codex instance compact <instance-id> [--json]
  buddyswitch-codex instance clear <instance-id> [--json]
  buddyswitch-codex instance attach <instance-id>
  buddyswitch-codex instance resume <instance-id> [--json]
  buddyswitch-codex instance stop <instance-id> [--json]
  buddyswitch-codex instance status <instance-id> [--json]
  buddyswitch-codex instance interrupt <instance-id> [--json]
  buddyswitch-codex instance list [--buddy <buddy>] [--json]
  buddyswitch-codex instance delete <instance-id> [--yes] [--json]
  buddyswitch-codex instance help

Commands:
  buddies Print valid buddies from buddyswitch/manifest.toml.
  start   Start a fresh product-mode app-server service.
  input   Send text to a running product-mode instance.
  side    Create, continue, or close a side conversation child thread.
  goal    Get, set, or clear the running instance goal.
  compact Start app-server thread compaction for a running instance.
  clear   Clear the running instance conversation with a fresh thread.
  attach  Attach a TUI to a running product-mode instance.
  resume  Resume a stopped product-mode instance service.
  stop    Stop a running product-mode instance service.
  status  Show product-mode instance service state.
  interrupt Interrupt the active turn on a running product-mode instance.
  list    List stored product-mode instances.
  delete  Delete one stored inactive instance without deleting shared state.
  help    Show this help message.
EOF
}

buddyswitch_instance_buddies() {
  local json=0 arg
  while [[ $# -gt 0 ]]; do
    arg="$1"
    case "${arg}" in
      --json)
        json=1
        shift
        ;;
      help|-h|--help)
        buddyswitch_instance_usage
        return 0
        ;;
      *)
        echo "Unknown instance buddies option: ${arg}" >&2
        buddyswitch_instance_usage >&2
        return 2
        ;;
    esac
  done

  if [[ "${json}" -eq 1 ]]; then
    python3 "${REPO_ROOT}/scripts/env_manifest.py" list-buddies --json
    return 0
  fi
  python3 "${REPO_ROOT}/scripts/env_manifest.py" list-buddies
}

buddyswitch_instance_start() {
  local arg
  for arg in "$@"; do
    case "${arg}" in
      --)
        break
        ;;
      help|-h|--help)
        buddyswitch_instance_usage
        return 0
        ;;
    esac
  done

  case "${1:-}" in
    --buddy|--buddy=*)
      start_codex "$@"
      ;;
    *)
      echo "instance start requires --buddy <buddy>" >&2
      buddyswitch_instance_usage >&2
      return 2
      ;;
  esac
}

buddyswitch_instance_json_files() {
  local instance_json
  for instance_json in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/instance.json; do
    [[ -f "${instance_json}" ]] || continue
    printf '%s\n' "${instance_json}"
  done
}

buddyswitch_instance_list() {
  local buddy_filter="" json=0
  local found=0 printed_header=0 instance_json meta kind instance_id status_json row_json
  local -a instance_rows=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --buddy)
        [[ $# -ge 2 && -n "${2:-}" && "${2:-}" != --* ]] || {
          echo "Missing value for --buddy" >&2
          buddyswitch_instance_usage >&2
          return 2
        }
        buddy_filter="$2"
        buddyswitch_validate_buddy_id "${buddy_filter}" || return $?
        shift 2
        ;;
      --json)
        json=1
        shift
        ;;
      *)
        echo "Unknown instance list option: $1" >&2
        buddyswitch_instance_usage >&2
        return 2
        ;;
    esac
  done

  while IFS= read -r instance_json; do
    meta="$(
      python3 - "${instance_json}" "${buddy_filter}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
buddy_filter = sys.argv[2]

try:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"invalid\t{instance_json.parent.name}\tinvalid-json:{exc}")
    raise SystemExit(0)

buddy = payload.get("buddy")
if buddy_filter and buddy != buddy_filter:
    raise SystemExit(0)

instance_id = payload.get("instance_id", instance_json.parent.name)
print(f"ok\t{instance_id}")
PY
    )"
    [[ -n "${meta}" ]] || continue
    kind="${meta%%$'\t'*}"
    if [[ "${kind}" == "invalid" ]]; then
      instance_id="${meta#*$'\t'}"
      if [[ "${json}" -eq 1 ]]; then
        row_json="$(
          python3 - "${instance_id%%$'\t'*}" "${instance_id#*$'\t'}" <<'PY'
import json
import sys

payload = {
    "instance_id": sys.argv[1],
    "buddy": "invalid",
    "status": "invalid",
    "app_server_health": "invalid",
    "thread_id": None,
    "browser_port": None,
    "updated_at": "",
    "workspace_dir": sys.argv[2],
}
print(json.dumps(payload, ensure_ascii=True))
PY
        )"
        instance_rows+=("${row_json}")
      else
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "${instance_id%%$'\t'*}" "invalid" "invalid" "invalid" "" "" "" "${instance_id#*$'\t'}"
      fi
      found=1
      continue
    fi
    instance_id="${meta#*$'\t'}"
    status_json="$(instance_status_json "${instance_id}")" || return $?
    if [[ "${json}" -eq 1 ]]; then
      row_json="$(
        python3 - "${status_json}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
app_server = payload.get("app_server")
healthy = False
if isinstance(app_server, dict):
    healthy = bool(app_server.get("healthy"))
thread_id = payload.get("thread_id")
browser_port = payload.get("browser_port")
row = {
    "instance_id": payload.get("instance_id", ""),
    "buddy": payload.get("buddy", ""),
    "status": payload.get("status", ""),
    "app_server_health": "healthy" if healthy else "unhealthy",
    "thread_id": thread_id if isinstance(thread_id, str) else None,
    "browser_port": browser_port if isinstance(browser_port, int) else None,
    "updated_at": payload.get("updated_at", ""),
    "workspace_dir": payload.get("workspace_dir", ""),
}
print(json.dumps(row, ensure_ascii=True))
PY
      )"
      instance_rows+=("${row_json}")
    else
      if [[ "${printed_header}" -eq 0 ]]; then
        printf 'instance_id\tbuddy\tstatus\tapp_server_health\tthread_id\tbrowser_port\tupdated_at\tworkspace_dir\n'
        printed_header=1
      fi
      python3 - "${status_json}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
app_server = payload.get("app_server")
healthy = False
if isinstance(app_server, dict):
    healthy = bool(app_server.get("healthy"))
thread_id = payload.get("thread_id")
row = (
    payload.get("instance_id", ""),
    payload.get("buddy", ""),
    payload.get("status", ""),
    "healthy" if healthy else "unhealthy",
    thread_id if isinstance(thread_id, str) else "",
    str(payload.get("browser_port") or ""),
    payload.get("updated_at", ""),
    payload.get("workspace_dir", ""),
)
print("\t".join(str(item) for item in row))
PY
    fi
    found=1
  done < <(buddyswitch_instance_json_files)

  if [[ "${json}" -eq 1 ]]; then
    if [[ "${#instance_rows[@]}" -eq 0 ]]; then
      printf '%s\n' '{"instances":[]}'
      return 0
    fi
    python3 - "${instance_rows[@]}" <<'PY'
import json
import sys

rows = [json.loads(arg) for arg in sys.argv[1:]]
print(json.dumps({"instances": rows}, ensure_ascii=True))
PY
    return 0
  fi

  if [[ "${found}" -eq 0 ]]; then
    echo "No BuddySwitch instances found."
    echo "Start one with: ./buddyswitch-codex instance start --buddy <buddy>"
  fi
}

buddyswitch_instance_record_json() {
  local instance_id="$1"
  local instance_json

  buddyswitch_validate_instance_id "${instance_id}" || return $?
  instance_json="$(buddyswitch_instance_json_path "${instance_id}")"
  if [[ ! -f "${instance_json}" ]]; then
    echo "Instance record missing: ${instance_json}" >&2
    return 2
  fi
  printf '%s\n' "${instance_json}"
}

buddyswitch_instance_record_field() {
  local instance_id="$1"
  local field_name="$2"
  local instance_json

  instance_json="$(buddyswitch_instance_record_json "${instance_id}")" || return $?
  python3 - "${instance_json}" "${instance_id}" "${field_name}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
instance_id = sys.argv[2]
field_name = sys.argv[3]
payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("instance_id") != instance_id:
    print(f"Instance id mismatch in {instance_json}", file=sys.stderr)
    raise SystemExit(2)
value = payload.get(field_name)
if value is None:
    raise SystemExit(0)
print(value)
PY
}

buddyswitch_instance_validate_record() {
  local instance_id="$1"
  local instance_json

  instance_json="$(buddyswitch_instance_record_json "${instance_id}")" || return $?
  python3 - "${instance_json}" "${instance_id}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
instance_id = sys.argv[2]
payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("instance_id") != instance_id:
    print(f"Instance id mismatch in {instance_json}", file=sys.stderr)
    raise SystemExit(2)
buddy = payload.get("buddy")
if not isinstance(buddy, str) or not buddy:
    print(f"Instance record missing buddy: {instance_json}", file=sys.stderr)
    raise SystemExit(2)
print(buddy)
PY
}

buddyswitch_instance_require_safe_delete_root() {
  local instance_id="$1"
  local instances_root="${BUDDYSWITCH_SHARED_ROOT}/instances"
  local instance_root
  local normalized_instances_root normalized_instance_root

  if [[ -L "${BUDDYSWITCH_SHARED_ROOT}" ]]; then
    echo "Instance delete blocked: unsafe shared root for ${instance_id}." >&2
    return 3
  fi

  instance_root="$(buddyswitch_instance_root "${instance_id}")"
  if [[ -L "${instances_root}" || -L "${instance_root}" ]]; then
    echo "Instance delete blocked: unsafe instance root for ${instance_id}." >&2
    return 3
  fi
  if [[ -d "${instance_root}" ]]; then
    normalized_instances_root="$(buddyswitch_workspace_canonical_path "${instances_root}")"
    normalized_instance_root="$(buddyswitch_workspace_canonical_path "${instance_root}")"
    case "${normalized_instance_root}" in
      "${normalized_instances_root}/"*)
        ;;
      *)
        echo "Instance delete blocked: unsafe instance root for ${instance_id}." >&2
        return 3
        ;;
    esac
  fi

  printf '%s\n' "${instance_root}"
}

buddyswitch_instance_main() {
  local command="${1:-}"
  case "${command}" in
    buddies)
      shift || true
      buddyswitch_instance_buddies "$@"
      ;;
    start)
      shift || true
      buddyswitch_instance_start "$@"
      ;;
    list)
      shift || true
      buddyswitch_instance_list "$@"
      ;;
    input)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_input "$@"
      ;;
    side)
      shift || true
      if [[ "${1:-}" == "close" ]]; then
        shift || true
        if [[ $# -lt 1 ]]; then
          echo "instance id is required" >&2
          buddyswitch_instance_usage >&2
          return 2
        fi
        instance_side_close "$@"
        return $?
      fi
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_side "$@"
      ;;
    goal)
      shift || true
      if [[ $# -lt 2 ]]; then
        echo "instance id and goal action are required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_goal "$@"
      ;;
    compact)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_compact "$@"
      ;;
    clear)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_clear "$@"
      ;;
    attach)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_attach "$@"
      ;;
    resume)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_resume "$@"
      ;;
    stop)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_stop "$@"
      ;;
    status)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_status "$@"
      ;;
    interrupt)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_interrupt "$@"
      ;;
    delete)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_delete "$@"
      ;;
    help|-h|--help)
      buddyswitch_instance_usage
      ;;
    "")
      echo "instance command is required" >&2
      buddyswitch_instance_usage >&2
      return 2
      ;;
    *)
      echo "Unknown instance command: ${command}" >&2
      buddyswitch_instance_usage >&2
      return 2
      ;;
  esac
}
