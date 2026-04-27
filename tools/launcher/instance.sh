#!/usr/bin/env bash
set -euo pipefail

buddyswitch_instance_usage() {
  cat <<EOF
Usage:
  buddyswitch-codex instance list [--buddy <buddy>]
  buddyswitch-codex instance open <instance-id> [codex args...]
  buddyswitch-codex instance delete <instance-id> --yes
  buddyswitch-codex instance help

Commands:
  list    List stored product-mode instances.
  open    Launch Codex in an existing inactive instance.
  delete  Delete one stored inactive instance without deleting shared state.
  help    Show this help message.
EOF
}

buddyswitch_instance_json_files() {
  local instance_json
  for instance_json in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/instance.json; do
    [[ -f "${instance_json}" ]] || continue
    printf '%s\n' "${instance_json}"
  done
}

buddyswitch_instance_list() {
  local buddy_filter=""
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
      *)
        echo "Unknown instance list option: $1" >&2
        buddyswitch_instance_usage >&2
        return 2
        ;;
    esac
  done

  python3 - "${BUDDYSWITCH_SHARED_ROOT}" "${buddy_filter}" <<'PY'
import json
import sys
from pathlib import Path

shared_root = Path(sys.argv[1])
buddy_filter = sys.argv[2]
rows = []
for instance_json in sorted((shared_root / "instances").glob("*/instance.json")):
    try:
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
    except Exception as exc:
        rows.append((instance_json.parent.name, "invalid", "invalid", "", "", "", "", f"invalid-json:{exc}"))
        continue
    buddy = payload.get("buddy")
    if buddy_filter and buddy != buddy_filter:
        continue
    rows.append(
        (
            payload.get("instance_id", instance_json.parent.name),
            buddy or "",
            payload.get("status", ""),
            payload.get("current_task_id") or "",
            payload.get("current_track_id") or "",
            str(payload.get("browser_port") or ""),
            payload.get("updated_at", ""),
            payload.get("workspace_dir", ""),
        )
    )

if not rows:
    print("No BuddySwitch instances found.")
    print("Start one with: ./buddyswitch-codex start --buddy <buddy>")
    raise SystemExit(0)

print("instance_id\tbuddy\tstatus\tcurrent_task_id\tcurrent_track_id\tbrowser_port\tupdated_at\tworkspace_dir")
for row in rows:
    print("\t".join(str(item) for item in row))
PY
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

buddyswitch_instance_live_target_launcher_marker_exists() {
  local instance_id="$1"
  python3 - "${BUDDYSWITCH_RUN_STATE_DIR}" "${instance_id}" <<'PY'
import json
import os
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
instance_id = sys.argv[2]
found = False

for marker in run_dir.glob("launcher-*.json"):
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        pid = payload.get("pid")
    except Exception:
        marker.unlink(missing_ok=True)
        continue
    if not isinstance(pid, int) or pid <= 0:
        marker.unlink(missing_ok=True)
        continue
    try:
        os.kill(pid, 0)
    except OSError:
        marker.unlink(missing_ok=True)
        continue
    if payload.get("instance_id") == instance_id:
        found = True

raise SystemExit(0 if found else 1)
PY
}

buddyswitch_instance_live_legacy_launcher_marker_exists() {
  local marker_file marker_pid

  if [[ ! -d "${BUDDYSWITCH_RUN_STATE_DIR}" ]]; then
    return 1
  fi

  for marker_file in "${BUDDYSWITCH_RUN_STATE_DIR}"/launcher-*.pid; do
    [[ -e "${marker_file}" ]] || continue
    marker_pid="$(cat "${marker_file}" 2>/dev/null || true)"
    if [[ -n "${marker_pid}" ]] && kill -0 "${marker_pid}" 2>/dev/null; then
      return 0
    fi
    rm -f "${marker_file}"
  done

  return 1
}

buddyswitch_instance_require_safe_delete_root() {
  local instance_id="$1"
  local instances_root="${BUDDYSWITCH_SHARED_ROOT}/instances"
  local instance_root
  local normalized_instances_root normalized_instance_root

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
    list)
      shift || true
      buddyswitch_instance_list "$@"
      ;;
    open)
      shift || true
      if [[ $# -lt 1 ]]; then
        echo "instance id is required" >&2
        buddyswitch_instance_usage >&2
        return 2
      fi
      instance_open "$@"
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
