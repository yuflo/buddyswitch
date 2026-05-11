#!/usr/bin/env bash
set -euo pipefail

buddyswitch_runtime_broker_socket() {
  local marker_path default_path
  marker_path="$(buddyswitch_runtime_broker_socket_marker_file)"
  if [[ -f "${marker_path}" ]]; then
    cat "${marker_path}"
    return 0
  fi
  default_path="${BUDDYSWITCH_INSTANCE_ROOT}/runtime/runtime-broker.sock"
  printf '%s\n' "${default_path}"
}

buddyswitch_runtime_broker_pid_file() {
  printf '%s/runtime/runtime-broker.pid\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

buddyswitch_runtime_broker_log_file() {
  printf '%s/runtime/runtime-broker.log\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

buddyswitch_runtime_broker_socket_marker_file() {
  printf '%s/runtime/runtime-broker.socket\n' "${BUDDYSWITCH_INSTANCE_ROOT}"
}

buddyswitch_runtime_broker_is_active() {
  local pid_file="$1"
  local pid
  if [[ ! -f "${pid_file}" ]]; then
    return 1
  fi
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]]; then
    return 1
  fi
  if kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi
  rm -f "${pid_file}"
  return 1
}

buddyswitch_runtime_broker_ensure() {
  local socket_path pid_file log_file manifest_path broker_script attempt marker_path default_socket fallback_socket

  marker_path="$(buddyswitch_runtime_broker_socket_marker_file)"
  default_socket="${BUDDYSWITCH_INSTANCE_ROOT}/runtime/runtime-broker.sock"
  socket_path="${default_socket}"
  pid_file="$(buddyswitch_runtime_broker_pid_file)"
  log_file="$(buddyswitch_runtime_broker_log_file)"
  manifest_path="${BUDDYSWITCH_REPO_ROOT}/buddyswitch/manifest.toml"
  broker_script="${BUDDYSWITCH_WORKSPACE_DIR}/scripts/runtime_kernel/broker.py"
  if [[ ! -f "${broker_script}" ]]; then
    echo "Runtime broker script missing in workspace: ${broker_script}" >&2
    return 1
  fi

  if [[ ${#socket_path} -ge 100 ]]; then
    fallback_socket="$(python3 - "${BUDDYSWITCH_INSTANCE_ID}" <<'PY'
import hashlib
import sys
instance_id = sys.argv[1]
digest = hashlib.sha1(instance_id.encode("utf-8")).hexdigest()[:12]
print(f"/tmp/buddyswitch-runtime-{digest}.sock")
PY
)"
    socket_path="${fallback_socket}"
  fi

  mkdir -p "$(dirname "${socket_path}")" "$(dirname "${log_file}")"
  if buddyswitch_runtime_broker_is_active "${pid_file}" && [[ -S "${socket_path}" ]]; then
    printf '%s\n' "${socket_path}" > "${marker_path}"
    export BUDDYSWITCH_RUNTIME_BROKER_SOCKET="${socket_path}"
    return 0
  fi

  rm -f "${socket_path}" "${pid_file}" "${marker_path}"
  (
    cd "${BUDDYSWITCH_WORKSPACE_DIR}"
    python3 "${broker_script}" serve \
      --socket "${socket_path}" \
      --pid-file "${pid_file}" \
      --instance-json "${BUDDYSWITCH_INSTANCE_JSON}" \
      --manifest "${manifest_path}" \
      >>"${log_file}" 2>&1
  ) &

  for attempt in {1..30}; do
    if [[ -S "${socket_path}" ]] && buddyswitch_runtime_broker_is_active "${pid_file}"; then
      printf '%s\n' "${socket_path}" > "${marker_path}"
      export BUDDYSWITCH_RUNTIME_BROKER_SOCKET="${socket_path}"
      return 0
    fi
    sleep 0.1
  done

  echo "Runtime broker failed to start for ${BUDDYSWITCH_INSTANCE_ID}." >&2
  echo "See log: ${log_file}" >&2
  return 1
}

buddyswitch_runtime_broker_stop() {
  local socket_path pid_file pid marker_path
  socket_path="$(buddyswitch_runtime_broker_socket)"
  pid_file="$(buddyswitch_runtime_broker_pid_file)"
  marker_path="$(buddyswitch_runtime_broker_socket_marker_file)"

  if [[ -f "${pid_file}" ]]; then
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]]; then
      kill "${pid}" 2>/dev/null || true
      for _ in {1..20}; do
        if ! kill -0 "${pid}" 2>/dev/null; then
          break
        fi
        sleep 0.05
      done
      if kill -0 "${pid}" 2>/dev/null; then
        kill -9 "${pid}" 2>/dev/null || true
      fi
    fi
    rm -f "${pid_file}"
  fi
  rm -f "${socket_path}"
  rm -f "${marker_path}"
}
