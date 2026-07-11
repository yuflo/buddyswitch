#!/usr/bin/env bash
set -euo pipefail

buddyswitch_instance_usage() {
  cat <<EOF
Usage:
  buddyswitch-codex instance roles [--json]
  buddyswitch-codex instance start --role <role> [--json]
  buddyswitch-codex instance input <actor-id> --text <text> [--json]
  buddyswitch-codex instance side <actor-id> --text <text> [--capability <level>] [--json]
  buddyswitch-codex instance side <actor-id> --side-thread-id <side-thread-id> --text <text> [--json]
  buddyswitch-codex instance side close <actor-id> --side-thread-id <side-thread-id> [--json]
  buddyswitch-codex instance capabilities <actor-id> get [--json]
  buddyswitch-codex instance capabilities <actor-id> set --parent <level> --side <level> [--json]
  buddyswitch-codex instance goal <actor-id> get|set|clear [--json]
  buddyswitch-codex instance compact <actor-id> [--json]
  buddyswitch-codex instance clear <actor-id> [--json]
  buddyswitch-codex instance attach <actor-id>
  buddyswitch-codex instance resume <actor-id> [--json]
  buddyswitch-codex instance stop <actor-id> [--json]
  buddyswitch-codex instance status <actor-id> [--json]
  buddyswitch-codex instance interrupt <actor-id> [--json]
  buddyswitch-codex instance list [--role <role>] [--json]
  buddyswitch-codex instance delete <actor-id> [--yes] [--json]
  buddyswitch-codex instance help

Commands:
  roles Print valid roles from buddyswitch/manifest.toml.
  start   Start a fresh product-mode app-server service.
  input   Send text to a running product-mode instance.
  side    Create, continue, or close a side conversation child thread.
  capabilities
          Get or replace actor Parent/Side capability levels.
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
        echo "Unknown instance roles option: ${arg}" >&2
        buddyswitch_instance_usage >&2
        return 2
        ;;
    esac
  done

  if [[ "${json}" -eq 1 ]]; then
    python3 "${REPO_ROOT}/scripts/env_manifest.py" list-roles --json
    return 0
  fi
  python3 "${REPO_ROOT}/scripts/env_manifest.py" list-roles
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
    --role|--role=*)
      start_codex "$@"
      ;;
    *)
      echo "instance start requires --role <role>" >&2
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
  local role_filter="" json=0
  local found=0 printed_header=0 instance_json meta kind actor_id status_json row_json
  local -a instance_rows=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --role)
        [[ $# -ge 2 && -n "${2:-}" && "${2:-}" != --* ]] || {
          echo "Missing value for --role" >&2
          buddyswitch_instance_usage >&2
          return 2
        }
        role_filter="$2"
        buddyswitch_validate_role_id "${role_filter}" || return $?
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
      python3 - "${instance_json}" "${role_filter}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
role_filter = sys.argv[2]

try:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"invalid\t{instance_json.parent.name}\tinvalid-json:{exc}")
    raise SystemExit(0)

role = payload.get("role")
if role_filter and role != role_filter:
    raise SystemExit(0)

actor_id = payload.get("actor_id", instance_json.parent.name)
print(f"ok\t{actor_id}")
PY
    )"
    [[ -n "${meta}" ]] || continue
    kind="${meta%%$'\t'*}"
    if [[ "${kind}" == "invalid" ]]; then
      actor_id="${meta#*$'\t'}"
      if [[ "${json}" -eq 1 ]]; then
        row_json="$(
          python3 - "${actor_id%%$'\t'*}" "${actor_id#*$'\t'}" <<'PY'
import json
import sys

payload = {
    "actor_id": sys.argv[1],
    "role": "invalid",
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
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "${actor_id%%$'\t'*}" "invalid" "invalid" "invalid" "" "" "" "${actor_id#*$'\t'}"
      fi
      found=1
      continue
    fi
    actor_id="${meta#*$'\t'}"
    status_json="$(instance_status_json "${actor_id}")" || return $?
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
    "actor_id": payload.get("actor_id", ""),
    "role": payload.get("role", ""),
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
        printf 'actor_id\tbuddy\tstatus\tapp_server_health\tthread_id\tbrowser_port\tupdated_at\tworkspace_dir\n'
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
    payload.get("actor_id", ""),
    payload.get("role", ""),
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
    echo "Start one with: ./buddyswitch-codex instance start --role <role>"
  fi
}

buddyswitch_instance_record_json() {
  local actor_id="$1"
  local instance_json

  buddyswitch_validate_actor_id "${actor_id}" || return $?
  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"
  if [[ ! -f "${instance_json}" ]]; then
    echo "Instance record missing: ${instance_json}" >&2
    return 2
  fi
  printf '%s\n' "${instance_json}"
}

buddyswitch_instance_record_field() {
  local actor_id="$1"
  local field_name="$2"
  local instance_json

  instance_json="$(buddyswitch_instance_record_json "${actor_id}")" || return $?
  python3 - "${instance_json}" "${actor_id}" "${field_name}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
field_name = sys.argv[3]
payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    print(f"Actor id mismatch in {instance_json}", file=sys.stderr)
    raise SystemExit(2)
value = payload.get(field_name)
if value is None:
    raise SystemExit(0)
print(value)
PY
}

buddyswitch_instance_validate_record() {
  local actor_id="$1"
  local instance_json

  instance_json="$(buddyswitch_instance_record_json "${actor_id}")" || return $?
  python3 - "${instance_json}" "${actor_id}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
actor_id = sys.argv[2]
payload = json.loads(instance_json.read_text(encoding="utf-8"))
if payload.get("actor_id") != actor_id:
    print(f"Actor id mismatch in {instance_json}", file=sys.stderr)
    raise SystemExit(2)
role = payload.get("role")
if not isinstance(role, str) or not role:
    print(f"Instance record missing role: {instance_json}", file=sys.stderr)
    raise SystemExit(2)
print(role)
PY
}

buddyswitch_instance_require_safe_delete_root() {
  local actor_id="$1"
  local instances_root="${BUDDYSWITCH_SHARED_ROOT}/instances"
  local instance_root
  local normalized_instances_root normalized_instance_root

  if [[ -L "${BUDDYSWITCH_SHARED_ROOT}" ]]; then
    echo "Instance delete blocked: unsafe shared root for ${actor_id}." >&2
    return 3
  fi

  instance_root="$(buddyswitch_instance_root "${actor_id}")"
  if [[ -L "${instances_root}" || -L "${instance_root}" ]]; then
    echo "Instance delete blocked: unsafe instance root for ${actor_id}." >&2
    return 3
  fi
  if [[ -d "${instance_root}" ]]; then
    normalized_instances_root="$(buddyswitch_workspace_canonical_path "${instances_root}")"
    normalized_instance_root="$(buddyswitch_workspace_canonical_path "${instance_root}")"
    case "${normalized_instance_root}" in
      "${normalized_instances_root}/"*)
        ;;
      *)
        echo "Instance delete blocked: unsafe instance root for ${actor_id}." >&2
        return 3
        ;;
    esac
  fi

  printf '%s\n' "${instance_root}"
}

buddyswitch_instance_capabilities_emit() {
  local actor_id="$1" output="$2" json="$3"
  python3 - "${actor_id}" "${output}" "${json}" <<'PY'
import json
import sys

actor_id = sys.argv[1]
payload = json.loads(sys.argv[2])
json_output = sys.argv[3] == "1"
payload["actor_id"] = actor_id

if json_output:
    print(json.dumps(payload, ensure_ascii=True))
    raise SystemExit(0)

capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}

def _value(section_name: str, field_name: str) -> str:
    section = capabilities.get(section_name) if isinstance(capabilities.get(section_name), dict) else {}
    value = section.get(field_name)
    return str(value) if isinstance(value, str) and value else "(missing)"

print(f"actor_id: {actor_id}")
print(f"parent level: {_value('parent', 'level')}")
print(f"parent model: {_value('parent', 'model')}")
print(f"parent effort: {_value('parent', 'effort')}")
print(f"side level: {_value('side', 'level')}")
print(f"side model: {_value('side', 'model')}")
print(f"side effort: {_value('side', 'effort')}")
PY
}

buddyswitch_instance_capabilities() {
  local actor_id="${1:-}" action="${2:-}" json=0 parent_level="" side_level="" arg instance_json output
  if [[ -z "${actor_id}" || -z "${action}" ]]; then
    echo "instance capabilities requires <actor-id> get|set" >&2
    return 2
  fi
  shift 2 || true

  case "${action}" in
    get)
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --json)
            json=1
            shift
            ;;
          *)
            echo "Unknown instance capabilities get option: $1" >&2
            return 2
            ;;
        esac
      done
      ;;
    set)
      while [[ $# -gt 0 ]]; do
        arg="$1"
        case "${arg}" in
          --parent)
            if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
              echo "instance capabilities set requires --parent <level>" >&2
              return 2
            fi
            parent_level="$2"
            shift 2
            ;;
          --side)
            if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
              echo "instance capabilities set requires --side <level>" >&2
              return 2
            fi
            side_level="$2"
            shift 2
            ;;
          --json)
            json=1
            shift
            ;;
          *)
            echo "Unknown instance capabilities set option: ${arg}" >&2
            return 2
            ;;
        esac
      done
      if [[ -z "${parent_level}" || -z "${side_level}" ]]; then
        echo "instance capabilities set requires --parent <level> and --side <level>" >&2
        return 2
      fi
      ;;
    *)
      echo "Unknown instance capabilities action: ${action}" >&2
      return 2
      ;;
  esac

  buddyswitch_validate_actor_id "${actor_id}" || return $?
  instance_json="$(buddyswitch_instance_json_path "${actor_id}")"
  if [[ ! -f "${instance_json}" ]]; then
    echo "Instance not found: ${actor_id}" >&2
    return 1
  fi
  buddyswitch_env_bind_instance "${actor_id}" || return $?

  if [[ "${action}" == "get" ]]; then
    output="$(python3 "${ACTOR_CAPABILITY_CLI_HELPER}" get --instance-json "${instance_json}")" || return $?
  else
    output="$(python3 "${ACTOR_CAPABILITY_CLI_HELPER}" replace --instance-json "${instance_json}" --parent "${parent_level}" --side "${side_level}")" || return $?
  fi
  buddyswitch_instance_capabilities_emit "${actor_id}" "${output}" "${json}"
}

buddyswitch_instance_main() {
  local command="${1:-}"
  case "${command}" in
    roles)
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
        echo "actor id is required" >&2
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
          echo "actor id is required" >&2
          buddyswitch_instance_usage >&2
          return 2
        fi
        instance_side_cleanup "$@"
        return $?
      fi
      if [[ $# -lt 1 ]]; then
        echo "actor id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_side "$@"
      ;;
    capabilities)
      shift || true
      if [[ $# -lt 2 ]]; then
        echo "actor id and capabilities action are required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      buddyswitch_instance_capabilities "$@"
      ;;
    goal)
      shift || true
      if [[ $# -lt 2 ]]; then
        echo "actor id and goal action are required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_goal "$@"
      ;;
    compact)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "actor id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_compact "$@"
      ;;
    clear)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "actor id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_clear "$@"
      ;;
    attach)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "actor id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_attach "$@"
      ;;
    resume)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "actor id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_resume "$@"
      ;;
    stop)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "actor id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_stop "$@"
      ;;
    status)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "actor id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_status "$@"
      ;;
    interrupt)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "actor id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_interrupt "$@"
      ;;
    delete)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "actor id is required" >&2
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
