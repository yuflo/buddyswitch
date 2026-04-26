#!/usr/bin/env bash
set -euo pipefail

buddyswitch_browser_instance_root() {
  local instance_id="${BUDDYSWITCH_INSTANCE_ID:-}"
  if [[ -z "${instance_id}" ]]; then
    return 1
  fi
  printf '%s\n' "${BUDDYSWITCH_INSTANCE_ROOT:-${BUDDYSWITCH_SHARED_ROOT}/instances/${instance_id}}"
}

buddyswitch_browser_default_profile_dir() {
  local instance_root
  if instance_root="$(buddyswitch_browser_instance_root)"; then
    printf '%s/browser/profile\n' "${instance_root}"
    return 0
  fi
  printf '%s/chrome/shared-browser\n' "${BUDDYSWITCH_SHARED_ROOT}"
}

buddyswitch_browser_default_log_file() {
  local instance_root
  if instance_root="$(buddyswitch_browser_instance_root)"; then
    printf '%s/browser/chrome.log\n' "${instance_root}"
    return 0
  fi
  printf '%s/log/chrome-cockpit.log\n' "${BUDDYSWITCH_SHARED_ROOT}"
}

buddyswitch_browser_is_instance_mode() {
  [[ -n "${BUDDYSWITCH_INSTANCE_ID:-}" ]]
}

buddyswitch_browser_init_defaults() {
  local default_profile_dir default_log_file

  if [[ -z "${BUDDYSWITCH_BROWSER_DEFAULTS_INITIALIZED:-}" ]]; then
    if [[ -n "${BUDDYSWITCH_BROWSER_PORT:-}" ]]; then
      export BUDDYSWITCH_BROWSER_PORT_EXPLICIT=1
    fi
    if [[ -n "${BUDDYSWITCH_BROWSER_PROFILE_DIR:-}" ]]; then
      export BUDDYSWITCH_BROWSER_PROFILE_DIR_EXPLICIT=1
    fi
    if [[ -n "${BUDDYSWITCH_BROWSER_LOG_FILE:-}" ]]; then
      export BUDDYSWITCH_BROWSER_LOG_FILE_EXPLICIT=1
    fi
    export BUDDYSWITCH_BROWSER_DEFAULTS_INITIALIZED=1
  fi

  default_profile_dir="$(buddyswitch_browser_default_profile_dir)"
  default_log_file="$(buddyswitch_browser_default_log_file)"

  export BUDDYSWITCH_BROWSER_PORT="${BUDDYSWITCH_BROWSER_PORT:-9222}"
  export BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME="${BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME:-chrome-devtools-cockpit}"

  if [[ "${BUDDYSWITCH_BROWSER_PROFILE_DIR_EXPLICIT:-0}" == "1" ]]; then
    export BUDDYSWITCH_BROWSER_PROFILE_DIR
  else
    export BUDDYSWITCH_BROWSER_PROFILE_DIR="${default_profile_dir}"
  fi

  if [[ "${BUDDYSWITCH_BROWSER_LOG_FILE_EXPLICIT:-0}" == "1" ]]; then
    export BUDDYSWITCH_BROWSER_LOG_FILE
  else
    export BUDDYSWITCH_BROWSER_LOG_FILE="${default_log_file}"
  fi
}

buddyswitch_browser_usage() {
  cat <<EOF
Usage:
  buddyswitch-codex browser status [--port <port>] [--profile-dir <dir>]
  buddyswitch-codex browser ensure [--port <port>] [--profile-dir <dir>]
  buddyswitch-codex browser help

Commands:
  status  Check whether the shared browser cockpit endpoint is reachable.
  ensure  Ensure the shared browser cockpit and BuddySwitch browser MCPs are ready.
  help    Show this help message.

Environment:
  BUDDYSWITCH_BROWSER_PORT              Remote debugging port (default: ${BUDDYSWITCH_BROWSER_PORT})
  BUDDYSWITCH_BROWSER_PROFILE_DIR       Shared Chrome profile dir (default: ${BUDDYSWITCH_BROWSER_PROFILE_DIR})
  BUDDYSWITCH_BROWSER_LOG_FILE          Chrome log file (default: ${BUDDYSWITCH_BROWSER_LOG_FILE})
  BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME  MCP server name (default: ${BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME})
  BUDDYSWITCH_BROWSER_CHROME_BIN        Override Chrome binary path.
EOF
}

buddyswitch_browser_url() {
  printf 'http://127.0.0.1:%s' "${BUDDYSWITCH_BROWSER_PORT}"
}

buddyswitch_browser_pid_marker() {
  local instance_root
  if instance_root="$(buddyswitch_browser_instance_root)"; then
    printf '%s/browser/chrome.pid' "${instance_root}"
    return 0
  fi
  printf '%s/browser-cockpit.pid' "${BUDDYSWITCH_RUN_STATE_DIR}"
}

buddyswitch_browser_port_is_available() {
  local port="$1"
  python3 - "${port}" <<'PY'
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind(("127.0.0.1", port))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
}

buddyswitch_browser_allocate_instance_port() {
  local port

  buddyswitch_browser_init_defaults
  if [[ "${BUDDYSWITCH_BROWSER_PORT_EXPLICIT:-0}" == "1" ]]; then
    return 0
  fi

  for port in {9222..9321}; do
    if buddyswitch_browser_port_is_available "${port}"; then
      export BUDDYSWITCH_BROWSER_PORT="${port}"
      return 0
    fi
  done

  echo "No free browser cockpit port found in range 9222..9321." >&2
  return 1
}

buddyswitch_browser_check_endpoint() {
  curl --silent --show-error --fail "$(buddyswitch_browser_url)/json/version" >/dev/null
}

buddyswitch_browser_find_chrome_bin() {
  local candidate

  if [[ -n "${BUDDYSWITCH_BROWSER_CHROME_BIN:-}" ]]; then
    if [[ -x "${BUDDYSWITCH_BROWSER_CHROME_BIN}" ]]; then
      printf '%s\n' "${BUDDYSWITCH_BROWSER_CHROME_BIN}"
      return 0
    fi
    return 1
  fi

  for candidate in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

buddyswitch_browser_has_mcp_server() {
  local server_name="$1"
  local config_path

  config_path="$(buddyswitch_codex_config_path)"
  if [[ ! -f "${config_path}" ]]; then
    return 1
  fi

  grep -Eq "^\\[mcp_servers\\.${server_name}\\]$" "${config_path}"
}

buddyswitch_browser_add_mcp_server() {
  local server_name="$1"
  shift
  buddyswitch_run_codex mcp add "${server_name}" -- "$@"
}

buddyswitch_browser_ensure_general_mcp() {
  if buddyswitch_browser_has_mcp_server "chrome-devtools"; then
    return 0
  fi

  buddyswitch_browser_add_mcp_server chrome-devtools npx chrome-devtools-mcp@latest
}

buddyswitch_browser_ensure_cockpit_mcp() {
  if buddyswitch_browser_has_mcp_server "${BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME}"; then
    return 0
  fi

  buddyswitch_browser_add_mcp_server \
    "${BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME}" \
    npx \
    chrome-devtools-mcp@latest \
    --browser-url="$(buddyswitch_browser_url)"
}

buddyswitch_browser_pid_marker_is_active() {
  local marker_file="$1"
  local marker_pid

  if [[ ! -f "${marker_file}" ]]; then
    return 1
  fi

  marker_pid="$(cat "${marker_file}" 2>/dev/null || true)"
  if [[ -n "${marker_pid}" ]] && kill -0 "${marker_pid}" 2>/dev/null; then
    return 0
  fi

  rm -f "${marker_file}"
  return 1
}

buddyswitch_browser_any_instance_pid_marker_is_active() {
  local marker_file

  for marker_file in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/browser/chrome.pid; do
    if [[ ! -e "${marker_file}" ]]; then
      continue
    fi
    if buddyswitch_browser_pid_marker_is_active "${marker_file}"; then
      return 0
    fi
  done

  return 1
}

buddyswitch_browser_any_recorded_instance_endpoint_is_active() {
  local instance_json browser_port

  for instance_json in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/instance.json; do
    if [[ ! -f "${instance_json}" ]]; then
      continue
    fi
    browser_port="$(
      python3 - "${instance_json}" <<'PY'
import json
import sys
from pathlib import Path

try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

port = payload.get("browser_port")
if isinstance(port, int):
    print(port)
PY
    )"
    if [[ -n "${browser_port}" ]] && curl --silent --show-error --fail "http://127.0.0.1:${browser_port}/json/version" >/dev/null 2>&1; then
      return 0
    fi
  done

  return 1
}

buddyswitch_browser_is_active() {
  local marker_file

  marker_file="$(buddyswitch_browser_pid_marker)"
  if buddyswitch_browser_pid_marker_is_active "${marker_file}"; then
    return 0
  fi

  if ! buddyswitch_browser_is_instance_mode; then
    if buddyswitch_browser_any_instance_pid_marker_is_active; then
      return 0
    fi
    if buddyswitch_browser_any_recorded_instance_endpoint_is_active; then
      return 0
    fi
  fi

  if buddyswitch_browser_check_endpoint 2>/dev/null; then
    return 0
  fi

  return 1
}

buddyswitch_browser_status() {
  if buddyswitch_browser_check_endpoint; then
    echo "Browser cockpit reachable: $(buddyswitch_browser_url)"
    echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}"
    return 0
  fi

  echo "Browser cockpit not reachable: $(buddyswitch_browser_url)" >&2
  echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}" >&2
  return 1
}

buddyswitch_browser_ensure_cockpit_endpoint() {
  local chrome_bin chrome_pid attempt marker_file

  mkdir -p "${BUDDYSWITCH_BROWSER_PROFILE_DIR}" "$(dirname "${BUDDYSWITCH_BROWSER_LOG_FILE}")"

  if buddyswitch_browser_check_endpoint 2>/dev/null; then
    echo "Browser cockpit already reachable: $(buddyswitch_browser_url)"
    echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}"
    return 0
  fi

  chrome_bin="$(buddyswitch_browser_find_chrome_bin)" || {
    echo "Chrome binary not found. Set BUDDYSWITCH_BROWSER_CHROME_BIN or install Chrome." >&2
    return 1
  }

  "${chrome_bin}" \
    --remote-debugging-port="${BUDDYSWITCH_BROWSER_PORT}" \
    --user-data-dir="${BUDDYSWITCH_BROWSER_PROFILE_DIR}" \
    >"${BUDDYSWITCH_BROWSER_LOG_FILE}" 2>&1 &
  chrome_pid=$!
  marker_file="$(buddyswitch_browser_pid_marker)"
  printf '%s\n' "${chrome_pid}" > "${marker_file}"
  disown || true

  for attempt in {1..20}; do
    if buddyswitch_browser_check_endpoint 2>/dev/null; then
      echo "Browser cockpit ready: $(buddyswitch_browser_url)"
      echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}"
      return 0
    fi
    sleep 1
  done

  rm -f "${marker_file}"
  echo "Browser cockpit did not become reachable: $(buddyswitch_browser_url)" >&2
  echo "See log: ${BUDDYSWITCH_BROWSER_LOG_FILE}" >&2
  return 1
}

buddyswitch_browser_bootstrap() {
  buddyswitch_browser_init_defaults
  buddyswitch_ensure_shared_env
  if ! buddyswitch_browser_is_instance_mode; then
    buddyswitch_browser_ensure_general_mcp
  fi
  buddyswitch_browser_ensure_cockpit_endpoint
  buddyswitch_browser_ensure_cockpit_mcp
}

buddyswitch_browser_main() {
  local command arg

  buddyswitch_browser_init_defaults
  command="${1:-status}"
  if [[ $# -gt 0 ]]; then
    shift
  fi

  while [[ $# -gt 0 ]]; do
    arg="$1"
    case "${arg}" in
      --port)
        if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
          echo "Missing value for --port" >&2
          buddyswitch_browser_usage >&2
          return 2
        fi
        BUDDYSWITCH_BROWSER_PORT="$2"
        shift 2
        ;;
      --profile-dir)
        if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
          echo "Missing value for --profile-dir" >&2
          buddyswitch_browser_usage >&2
          return 2
        fi
        BUDDYSWITCH_BROWSER_PROFILE_DIR="$2"
        shift 2
        ;;
      --help|-h)
        buddyswitch_browser_usage
        return 0
        ;;
      *)
        echo "Unknown browser option: ${arg}" >&2
        buddyswitch_browser_usage >&2
        return 2
        ;;
    esac
  done

  case "${command}" in
    status)
      buddyswitch_browser_status
      ;;
    ensure)
      buddyswitch_browser_bootstrap
      ;;
    help)
      buddyswitch_browser_usage
      ;;
    *)
      echo "Unknown browser command: ${command}" >&2
      buddyswitch_browser_usage >&2
      return 2
      ;;
  esac
}
