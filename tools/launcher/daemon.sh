#!/usr/bin/env bash
set -euo pipefail

BUDDYSWITCH_DAEMON_HELPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUDDYSWITCH_DAEMON_HELPER="${BUDDYSWITCH_DAEMON_HELPER_DIR}/instance_daemon.py"
BUDDYSWITCH_CENTRAL_DAEMON_HELPER="${BUDDYSWITCH_DAEMON_HELPER_DIR}/central_daemon.py"

buddyswitch_central_daemon_ensure() {
  local output socket_path
  output="$(
    python3 "${BUDDYSWITCH_CENTRAL_DAEMON_HELPER}" start \
      --shared-root "${BUDDYSWITCH_SHARED_ROOT}"
  )" || {
    [[ -n "${output:-}" ]] && echo "${output}" >&2
    return 1
  }
  socket_path="$(
    python3 - "${output}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
value = payload.get("socket_path")
print(value if isinstance(value, str) else "")
PY
  )"
  if [[ -z "${socket_path}" ]]; then
    echo "Central daemon start did not return socket_path." >&2
    echo "${output}" >&2
    return 1
  fi
  export BUDDYSWITCH_CENTRAL_DAEMON_SOCKET="${socket_path}"
}

buddyswitch_central_daemon_stop_if_idle() {
  python3 "${BUDDYSWITCH_CENTRAL_DAEMON_HELPER}" stop-if-idle \
    --shared-root "${BUDDYSWITCH_SHARED_ROOT}" >/dev/null || true
  unset BUDDYSWITCH_CENTRAL_DAEMON_SOCKET
}

buddyswitch_daemon_start() {
  buddyswitch_central_daemon_ensure || return $?
  python3 "${BUDDYSWITCH_DAEMON_HELPER}" start \
    --instance-json "${BUDDYSWITCH_INSTANCE_JSON}"
}

buddyswitch_daemon_stop() {
  python3 "${BUDDYSWITCH_DAEMON_HELPER}" stop \
    --instance-json "${BUDDYSWITCH_INSTANCE_JSON}"
  buddyswitch_central_daemon_stop_if_idle
}

buddyswitch_daemon_status_json() {
  python3 "${BUDDYSWITCH_DAEMON_HELPER}" status \
    --instance-json "${BUDDYSWITCH_INSTANCE_JSON}" \
    --json
}
