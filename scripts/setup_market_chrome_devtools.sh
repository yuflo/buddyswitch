#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PORT="${PORT:-9222}"
PROFILE_DIR="${PROFILE_DIR:-$HOME/.buddyswitch/chrome-market}"
LOG_FILE="${LOG_FILE:-/tmp/chrome-market.log}"
MCP_NAME="${MCP_NAME:-chrome-devtools-market}"
CODEX_BIN="${CODEX_BIN:-codex}"
ONLY_STATUS=0
INSTALL_MCP=0

usage() {
  cat <<EOF
Usage:
  $(basename "$0") [--install-mcp] [--status] [--port <port>] [--profile-dir <dir>]

What it does:
  1. Launches a dedicated Chrome instance with remote debugging enabled.
  2. Reuses the same persistent profile directory across runs.
  3. Prints the exact MCP command to run manually.
  4. Optionally runs the MCP add command through zsh.

Options:
  --install-mcp         Run the MCP add command via zsh after Chrome is ready.
  --status              Only check whether the remote debugging endpoint is reachable.
  --port <port>         Remote debugging port. Default: ${PORT}
  --profile-dir <dir>   Chrome user data dir. Default: ${PROFILE_DIR}
  --help                Show this message.

Environment overrides:
  PORT, PROFILE_DIR, LOG_FILE, MCP_NAME, CODEX_BIN

Examples:
  bash scripts/setup_market_chrome_devtools.sh
  CODEX_BIN=codex-w1 bash scripts/setup_market_chrome_devtools.sh --install-mcp
  bash scripts/setup_market_chrome_devtools.sh --status
  PROFILE_DIR="\$HOME/.buddyswitch/chrome-market-alt" bash scripts/setup_market_chrome_devtools.sh
EOF
}

find_chrome_bin() {
  local candidates=(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"
    "/Applications/Chromium.app/Contents/MacOS/Chromium"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

build_mcp_add_cmd() {
  printf '%s mcp add %s -- npx chrome-devtools-mcp@latest --browser-url=http://127.0.0.1:%s' \
    "${CODEX_BIN}" "${MCP_NAME}" "${PORT}"
}

check_debug_endpoint() {
  curl --silent --show-error --fail \
    "http://127.0.0.1:${PORT}/json/version" >/dev/null
}

launch_chrome() {
  local chrome_bin
  chrome_bin="$(find_chrome_bin)" || {
    echo "Chrome binary not found. Install Google Chrome locally first." >&2
    exit 1
  }

  mkdir -p "${PROFILE_DIR}"

  if check_debug_endpoint 2>/dev/null; then
    echo "Chrome remote debugging is already reachable on port ${PORT}."
    return 0
  fi

  "${chrome_bin}" \
    --remote-debugging-port="${PORT}" \
    --user-data-dir="${PROFILE_DIR}" \
    >"${LOG_FILE}" 2>&1 &

  disown || true

  local attempt
  for attempt in {1..20}; do
    if check_debug_endpoint 2>/dev/null; then
      echo "Chrome launched with isolated profile: ${PROFILE_DIR}"
      echo "Remote debugging endpoint is ready on port ${PORT}."
      return 0
    fi
    sleep 1
  done

  echo "Chrome did not become reachable on port ${PORT}. See ${LOG_FILE}." >&2
  exit 1
}

install_mcp() {
  local cmd
  cmd="$(build_mcp_add_cmd)"
  zsh -lic "${cmd}"
}

print_next_steps() {
  cat <<EOF

Next steps:
  1. Log into any sites you want to reuse in the dedicated Chrome window.
  2. Run this once in the Codex shell you actually use:
     $(build_mcp_add_cmd)
  3. Open a fresh Codex session after adding '${MCP_NAME}'.

If you use a custom CODEX_HOME, run:
  CODEX_HOME="/path/to/your/codex-home" codex mcp add ${MCP_NAME} -- npx chrome-devtools-mcp@latest --browser-url=http://127.0.0.1:${PORT}
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-mcp)
      INSTALL_MCP=1
      shift
      ;;
    --status)
      ONLY_STATUS=1
      shift
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --profile-dir)
      PROFILE_DIR="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "${ONLY_STATUS}" -eq 1 ]]; then
  if check_debug_endpoint; then
    echo "Chrome remote debugging endpoint is reachable on port ${PORT}."
    exit 0
  fi
  echo "Chrome remote debugging endpoint is not reachable on port ${PORT}." >&2
  exit 1
fi

launch_chrome

if [[ "${INSTALL_MCP}" -eq 1 ]]; then
  install_mcp
fi

print_next_steps
