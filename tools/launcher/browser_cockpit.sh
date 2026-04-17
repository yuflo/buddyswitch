#!/usr/bin/env bash
set -euo pipefail

buddyswitch_browser_init_defaults() {
  export BUDDYSWITCH_BROWSER_PORT="${BUDDYSWITCH_BROWSER_PORT:-9222}"
  export BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME="${BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME:-chrome-devtools-cockpit}"
  export BUDDYSWITCH_BROWSER_PROFILE_DIR="${BUDDYSWITCH_BROWSER_PROFILE_DIR:-${BUDDYSWITCH_SHARED_ROOT}/chrome/shared-browser}"
  export BUDDYSWITCH_BROWSER_LOG_FILE="${BUDDYSWITCH_BROWSER_LOG_FILE:-${BUDDYSWITCH_SHARED_ROOT}/log/chrome-cockpit.log}"
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
  printf '%s/browser-cockpit.pid' "${BUDDYSWITCH_RUN_STATE_DIR}"
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

buddyswitch_browser_is_active() {
  local marker_file marker_pid

  marker_file="$(buddyswitch_browser_pid_marker)"
  if [[ -f "${marker_file}" ]]; then
    marker_pid="$(cat "${marker_file}" 2>/dev/null || true)"
    if [[ -n "${marker_pid}" ]] && kill -0 "${marker_pid}" 2>/dev/null; then
      return 0
    fi
    rm -f "${marker_file}"
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
  buddyswitch_ensure_shared_env
  buddyswitch_browser_ensure_general_mcp
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
