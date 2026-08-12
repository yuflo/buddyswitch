#!/usr/bin/env bash
set -euo pipefail

buddyswitch_central_daemon_ensure() {
  local output socket_path
  output="$(
    "${BUDDYSWITCH_PYTHON}" -m "${BUDDYSWITCH_HOST_CONTROL_CENTRAL_DAEMON_MODULE}" start \
      --shared-root "${BUDDYSWITCH_SHARED_ROOT}"
  )" || {
    [[ -n "${output:-}" ]] && echo "${output}" >&2
    return 1
  }
  socket_path="$(
    "${BUDDYSWITCH_PYTHON}" - "${output}" <<'PY'
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
  "${BUDDYSWITCH_PYTHON}" -m "${BUDDYSWITCH_HOST_CONTROL_CENTRAL_DAEMON_MODULE}" stop-if-idle \
    --shared-root "${BUDDYSWITCH_SHARED_ROOT}" >/dev/null || true
  unset BUDDYSWITCH_CENTRAL_DAEMON_SOCKET
}

buddyswitch_daemon_start() {
  buddyswitch_central_daemon_ensure || return $?
  "${BUDDYSWITCH_PYTHON}" -m "${BUDDYSWITCH_HOST_CONTROL_INSTANCE_DAEMON_MODULE}" start \
    --instance-json "${BUDDYSWITCH_INSTANCE_JSON}"
}

buddyswitch_daemon_stop() {
  "${BUDDYSWITCH_PYTHON}" -m "${BUDDYSWITCH_HOST_CONTROL_INSTANCE_DAEMON_MODULE}" stop \
    --instance-json "${BUDDYSWITCH_INSTANCE_JSON}"
  buddyswitch_central_daemon_stop_if_idle
}

buddyswitch_daemon_status_json() {
  "${BUDDYSWITCH_PYTHON}" -m "${BUDDYSWITCH_HOST_CONTROL_INSTANCE_DAEMON_MODULE}" status \
    --instance-json "${BUDDYSWITCH_INSTANCE_JSON}" \
    --json
}
