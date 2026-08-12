#!/usr/bin/env bash
set -euo pipefail

buddyswitch_browser_status_json() {
  "${BUDDYSWITCH_PYTHON}" -m buddyswitch.foundation.browser_runtime.runtime status \
    --instance-root "$(buddyswitch_instance_root "$1")" --actor-id "$1"
}

buddyswitch_browser_manager_stop_instance() {
  local actor_id="$1" root="$(buddyswitch_instance_root "$1")"
  [[ -f "${root}/instance.json" ]] || return 0
  "${BUDDYSWITCH_PYTHON}" -m buddyswitch.foundation.browser_runtime.runtime stop \
    --instance-root "${root}" --actor-id "${actor_id}" >/dev/null
}

buddyswitch_browser_instance_ownership_state() {
  local output
  output="$(buddyswitch_browser_status_json "$1" 2>/dev/null || true)"
  [[ -n "${output}" ]] || output="{}"
  "${BUDDYSWITCH_PYTHON}" -c 'import json,sys; p=json.loads(sys.argv[1]); print(p.get("ownership", "unknown") if p.get("ok") is True else "unknown")' "${output}"
}

buddyswitch_browser_instance_pid_marker_is_active() {
  local marker_file="$(buddyswitch_instance_root "$1")/browser/chrome.pid"
  "${BUDDYSWITCH_PYTHON}" - "${marker_file}" <<'PY'
from pathlib import Path
import sys

from buddyswitch.foundation.process_runtime import process_identity

marker_file = Path(sys.argv[1])
record = process_identity.read_record(marker_file)
if record is not None and process_identity.is_running(record):
    raise SystemExit(0)
process_identity.remove_record(marker_file)
raise SystemExit(1)
PY
}

buddyswitch_browser_instance_endpoint_ownership_state() {
  buddyswitch_browser_instance_ownership_state "$1"
}
