#!/usr/bin/env bash
set -euo pipefail

BUDDYSWITCH_DAEMON_HELPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUDDYSWITCH_DAEMON_HELPER="${BUDDYSWITCH_DAEMON_HELPER_DIR}/instance_daemon.py"

buddyswitch_daemon_start() {
  python3 "${BUDDYSWITCH_DAEMON_HELPER}" start \
    --instance-json "${BUDDYSWITCH_INSTANCE_JSON}"
}

buddyswitch_daemon_stop() {
  python3 "${BUDDYSWITCH_DAEMON_HELPER}" stop \
    --instance-json "${BUDDYSWITCH_INSTANCE_JSON}"
}

buddyswitch_daemon_status_json() {
  python3 "${BUDDYSWITCH_DAEMON_HELPER}" status \
    --instance-json "${BUDDYSWITCH_INSTANCE_JSON}" \
    --json
}
