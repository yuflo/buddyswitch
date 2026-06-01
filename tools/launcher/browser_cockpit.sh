#!/usr/bin/env bash
set -euo pipefail

buddyswitch_browser_instance_root() {
  local actor_id="${BUDDYSWITCH_ACTOR_ID:-}"
  if [[ -z "${actor_id}" ]]; then
    return 1
  fi
  printf '%s\n' "${BUDDYSWITCH_INSTANCE_ROOT:-${BUDDYSWITCH_SHARED_ROOT}/instances/${actor_id}}"
}

buddyswitch_browser_default_profile_dir() {
  local instance_root
  if instance_root="$(buddyswitch_browser_instance_root)"; then
    printf '%s/browser/profile\n' "${instance_root}"
    return 0
  fi
  echo "Browser profile default requires an instance-scoped root." >&2
  return 2
}

buddyswitch_browser_default_log_file() {
  local instance_root
  if instance_root="$(buddyswitch_browser_instance_root)"; then
    printf '%s/browser/chrome.log\n' "${instance_root}"
    return 0
  fi
  echo "Browser log default requires an instance-scoped root." >&2
  return 2
}

buddyswitch_browser_is_instance_mode() {
  [[ -n "${BUDDYSWITCH_ACTOR_ID:-}" ]]
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

  export BUDDYSWITCH_BROWSER_PORT="${BUDDYSWITCH_BROWSER_PORT:-9222}"
  export BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME="${BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME:-chrome-devtools-cockpit}"
  export BUDDYSWITCH_BROWSER_COCKPIT_PROXY="${BUDDYSWITCH_BROWSER_COCKPIT_PROXY:-${BUDDYSWITCH_REPO_ROOT}/tools/launcher/chrome_devtools_cockpit_proxy.py}"
  export BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_PACKAGE="${BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_PACKAGE:-chrome-devtools-mcp@1.1.1}"
  export BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL="${BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL:-${BUDDYSWITCH_REPO_ROOT}/scripts/env/cdp_background_page.py}"

  if [[ "${BUDDYSWITCH_BROWSER_PROFILE_DIR_EXPLICIT:-0}" == "1" ]]; then
    export BUDDYSWITCH_BROWSER_PROFILE_DIR
  else
    default_profile_dir="$(buddyswitch_browser_default_profile_dir)"
    export BUDDYSWITCH_BROWSER_PROFILE_DIR="${default_profile_dir}"
  fi

  if [[ "${BUDDYSWITCH_BROWSER_LOG_FILE_EXPLICIT:-0}" == "1" ]]; then
    export BUDDYSWITCH_BROWSER_LOG_FILE
  else
    default_log_file="$(buddyswitch_browser_default_log_file)"
    export BUDDYSWITCH_BROWSER_LOG_FILE="${default_log_file}"
  fi
}

buddyswitch_browser_usage() {
  cat <<EOF
Usage:
  buddyswitch-codex env browser status [--instance <actor-id>] [--port <port>] [--profile-dir <dir>]
  buddyswitch-codex env browser ensure --instance <actor-id> [--port <port>] [--profile-dir <dir>]
  buddyswitch-codex env browser help

Commands:
  status  Check whether the browser cockpit has a usable ready page for MCP operations.
  ensure  Ensure the instance browser cockpit has a usable ready page and BuddySwitch browser MCPs are ready.
  help    Show this help message.

Environment:
  BUDDYSWITCH_BROWSER_PORT              Remote debugging port (default: ${BUDDYSWITCH_BROWSER_PORT:-9222})
  BUDDYSWITCH_BROWSER_PROFILE_DIR       Chrome profile dir (default: ${BUDDYSWITCH_BROWSER_PROFILE_DIR:-<instance>/browser/profile})
  BUDDYSWITCH_BROWSER_LOG_FILE          Chrome log file (default: ${BUDDYSWITCH_BROWSER_LOG_FILE:-<instance>/browser/chrome.log})
  BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME  MCP server name (default: ${BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME:-chrome-devtools-cockpit})
  BUDDYSWITCH_BROWSER_COCKPIT_PROXY     BuddySwitch MCP proxy path.
  BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL
                                         Helper used to create non-activating ready pages.
  BUDDYSWITCH_BROWSER_CHROME_BIN        Override Chrome binary path.
EOF
}

buddyswitch_browser_validate_port_option() {
  local port="$1"

  if [[ ! "${port}" =~ ^[0-9]+$ ]]; then
    echo "Invalid value for --port: ${port} (expected 1..65535)" >&2
    return 2
  fi
  if (( 10#${port} < 1 || 10#${port} > 65535 )); then
    echo "Invalid value for --port: ${port} (expected 1..65535)" >&2
    return 2
  fi
}

buddyswitch_browser_validate_env_or_default_port() {
  local port="${BUDDYSWITCH_BROWSER_PORT:-9222}"

  if buddyswitch_browser_validate_port_option "${port}" >/dev/null 2>&1; then
    return 0
  fi

  echo "Invalid value for BUDDYSWITCH_BROWSER_PORT: ${port} (expected 1..65535)" >&2
  return 2
}

buddyswitch_browser_url() {
  printf 'http://127.0.0.1:%s' "${BUDDYSWITCH_BROWSER_PORT}"
}

buddyswitch_browser_cdp_curl() {
  curl \
    --silent \
    --show-error \
    --fail \
    --connect-timeout "${BUDDYSWITCH_BROWSER_CDP_CONNECT_TIMEOUT:-0.5}" \
    --max-time "${BUDDYSWITCH_BROWSER_CDP_MAX_TIME:-1.5}" \
    "$@"
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
  buddyswitch_browser_cdp_curl "$(buddyswitch_browser_url)/json/version" >/dev/null
}

buddyswitch_browser_has_usable_page() {
  local page_targets

  page_targets="$(buddyswitch_browser_cdp_curl "$(buddyswitch_browser_url)/json/list")" || return 1
  python3 - "${page_targets}" <<'PY'
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except (IndexError, json.JSONDecodeError):
    raise SystemExit(1)

if not isinstance(payload, list):
    raise SystemExit(1)

for target in payload:
    if not isinstance(target, dict):
        continue
    if target.get("type") != "page":
        continue
    url = target.get("url")
    if not isinstance(url, str):
        continue
    normalized = url.strip().lower()
    if not normalized:
        continue
    if normalized == "about:blank":
        raise SystemExit(0)
    if normalized.startswith("chrome://"):
        continue
    if normalized.startswith("chrome-untrusted://"):
        continue
    if normalized.startswith("devtools://"):
        continue
    raise SystemExit(0)

raise SystemExit(1)
PY
}

buddyswitch_browser_create_blank_page() {
  python3 "${BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL}" \
    --browser-url "$(buddyswitch_browser_url)" \
    --url about:blank >/dev/null
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
  local status
  shift
  buddyswitch_run_codex mcp add "${server_name}" -- "$@" || {
    status=$?
    return "${status}"
  }
  buddyswitch_patch_codex_config
}

buddyswitch_browser_remove_mcp_server() {
  local server_name="$1"
  buddyswitch_run_codex mcp remove "${server_name}"
}

buddyswitch_browser_disable_cockpit_mcp() {
  local server_name
  server_name="${BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME}"

  if buddyswitch_browser_has_mcp_server "${server_name}"; then
    buddyswitch_browser_remove_mcp_server "${server_name}" || return $?
  fi
  return 0
}

buddyswitch_browser_mcp_browser_url() {
  local server_name="$1"
  local config_path section

  config_path="$(buddyswitch_codex_config_path)"
  if [[ ! -f "${config_path}" ]]; then
    return 1
  fi

  section="[mcp_servers.${server_name}]"
  awk -v section="${section}" '
    $0 == section { in_section = 1; next }
    /^\[/ && in_section { exit }
    in_section {
      if (match($0, /--browser-url=[^" ,\]]+/)) {
        value = substr($0, RSTART, RLENGTH)
        sub(/^--browser-url=/, "", value)
        print value
        exit
      }
    }
  ' "${config_path}"
}

buddyswitch_browser_mcp_uses_cockpit_proxy() {
  local server_name="$1"
  local config_path section

  config_path="$(buddyswitch_codex_config_path)"
  if [[ ! -f "${config_path}" ]]; then
    return 1
  fi

  section="[mcp_servers.${server_name}]"
  awk -v section="${section}" '
    $0 == section { in_section = 1; next }
    /^\[/ && in_section { exit }
    in_section && /chrome_devtools_cockpit_proxy\.py/ { found = 1 }
    END { exit found ? 0 : 1 }
  ' "${config_path}"
}

buddyswitch_browser_ensure_cockpit_mcp() {
  local server_name expected_browser_url recorded_browser_url upstream_command

  server_name="${BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME}"
  expected_browser_url="$(buddyswitch_browser_url)"
  upstream_command="npx ${BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_PACKAGE}"

  if buddyswitch_browser_has_mcp_server "${server_name}"; then
    recorded_browser_url="$(buddyswitch_browser_mcp_browser_url "${server_name}" || true)"
    if [[ "${recorded_browser_url}" == "${expected_browser_url}" ]] && buddyswitch_browser_mcp_uses_cockpit_proxy "${server_name}"; then
      return 0
    fi
    buddyswitch_browser_remove_mcp_server "${server_name}"
  fi

  buddyswitch_browser_add_mcp_server \
    "${server_name}" \
    python3 \
    "${BUDDYSWITCH_BROWSER_COCKPIT_PROXY}" \
    --upstream-command "${upstream_command}" \
    --browser-url="${expected_browser_url}"
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

buddyswitch_browser_instance_pid_marker_is_active() {
  local actor_id="$1"
  local marker_file="${BUDDYSWITCH_SHARED_ROOT}/instances/${actor_id}/browser/chrome.pid"
  buddyswitch_browser_pid_marker_is_active "${marker_file}"
}

buddyswitch_browser_instance_endpoint_is_active() {
  local actor_id="$1"
  local instance_json="${BUDDYSWITCH_SHARED_ROOT}/instances/${actor_id}/instance.json"
  local browser_port

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
  [[ -n "${browser_port}" ]] || return 1
  buddyswitch_browser_cdp_curl "http://127.0.0.1:${browser_port}/json/version" >/dev/null 2>&1
}

_buddyswitch_browser_instance_recorded_port() {
  local actor_id="$1"
  local instance_json="${BUDDYSWITCH_SHARED_ROOT}/instances/${actor_id}/instance.json"

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
}

_buddyswitch_browser_port_listener_pids() {
  local browser_port="$1"

  if ! command -v lsof >/dev/null 2>&1; then
    return 1
  fi
  lsof -nP -iTCP:"${browser_port}" -sTCP:LISTEN -t 2>/dev/null | awk 'NF { print $1 }'
}

_buddyswitch_browser_process_command_line() {
  local pid="$1"
  ps -ww -p "${pid}" -o command= 2>/dev/null || true
}

buddyswitch_browser_instance_endpoint_ownership_state() {
  local actor_id="$1"
  local browser_port target_profile pid command_line found_listener=0 found_foreign=0

  browser_port="$(_buddyswitch_browser_instance_recorded_port "${actor_id}")"
  if [[ -z "${browser_port}" ]]; then
    echo "inactive"
    return 0
  fi
  if ! buddyswitch_browser_cdp_curl "http://127.0.0.1:${browser_port}/json/version" >/dev/null 2>&1; then
    echo "inactive"
    return 0
  fi
  if buddyswitch_browser_instance_pid_marker_is_active "${actor_id}"; then
    echo "owned"
    return 0
  fi

  target_profile="${BUDDYSWITCH_SHARED_ROOT}/instances/${actor_id}/browser/profile"
  while IFS= read -r pid; do
    [[ -n "${pid}" ]] || continue
    found_listener=1
    command_line="$(_buddyswitch_browser_process_command_line "${pid}")"
    if [[ "${command_line}" == *"--user-data-dir=${target_profile}"* ]]; then
      echo "owned"
      return 0
    fi
    if [[ "${command_line}" == *"--user-data-dir="*"/browser/profile"* ]]; then
      found_foreign=1
    fi
  done < <(_buddyswitch_browser_port_listener_pids "${browser_port}" || true)

  if [[ "${found_foreign}" -eq 1 ]]; then
    echo "foreign"
    return 0
  fi
  echo "unknown"
}

buddyswitch_browser_instance_endpoint_is_owned_active() {
  local actor_id="$1"
  [[ "$(buddyswitch_browser_instance_endpoint_ownership_state "${actor_id}")" == "owned" ]]
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
    if [[ -n "${browser_port}" ]] && buddyswitch_browser_cdp_curl "http://127.0.0.1:${browser_port}/json/version" >/dev/null 2>&1; then
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
  if buddyswitch_browser_check_endpoint 2>/dev/null; then
    if buddyswitch_browser_has_usable_page 2>/dev/null; then
      echo "Browser cockpit ready: $(buddyswitch_browser_url)"
      echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}"
      return 0
    fi
    echo "Browser cockpit not ready: $(buddyswitch_browser_url) (endpoint reachable but no usable page target)" >&2
    echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}"
    return 1
  fi

  echo "Browser cockpit not ready: $(buddyswitch_browser_url) (endpoint unreachable)" >&2
  echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}" >&2
  return 1
}

buddyswitch_browser_ensure_cockpit_endpoint() {
  local chrome_bin chrome_pid attempt marker_file

  mkdir -p "${BUDDYSWITCH_BROWSER_PROFILE_DIR}" "$(dirname "${BUDDYSWITCH_BROWSER_LOG_FILE}")"

  if buddyswitch_browser_check_endpoint 2>/dev/null; then
    if buddyswitch_browser_has_usable_page 2>/dev/null; then
      echo "Browser cockpit already ready: $(buddyswitch_browser_url)"
      echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}"
      return 0
    fi
    buddyswitch_browser_create_blank_page >/dev/null 2>&1 || true
    if buddyswitch_browser_has_usable_page 2>/dev/null; then
      echo "Browser cockpit ready: $(buddyswitch_browser_url)"
      echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}"
      return 0
    fi
  fi

  chrome_bin="$(buddyswitch_browser_find_chrome_bin)" || {
    echo "Chrome binary not found. Set BUDDYSWITCH_BROWSER_CHROME_BIN or install Chrome." >&2
    return 1
  }

  "${chrome_bin}" \
    --remote-debugging-port="${BUDDYSWITCH_BROWSER_PORT}" \
    --user-data-dir="${BUDDYSWITCH_BROWSER_PROFILE_DIR}" \
    --no-first-run \
    --no-default-browser-check \
    about:blank \
    >"${BUDDYSWITCH_BROWSER_LOG_FILE}" 2>&1 &
  chrome_pid=$!
  marker_file="$(buddyswitch_browser_pid_marker)"
  printf '%s\n' "${chrome_pid}" > "${marker_file}"
  disown || true

  for attempt in {1..20}; do
    if buddyswitch_browser_check_endpoint 2>/dev/null; then
      if buddyswitch_browser_has_usable_page 2>/dev/null; then
        echo "Browser cockpit ready: $(buddyswitch_browser_url)"
        echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}"
        return 0
      fi
      buddyswitch_browser_create_blank_page >/dev/null 2>&1 || true
      if buddyswitch_browser_has_usable_page 2>/dev/null; then
        echo "Browser cockpit ready: $(buddyswitch_browser_url)"
        echo "Profile: ${BUDDYSWITCH_BROWSER_PROFILE_DIR}"
        return 0
      fi
      break
    fi
    sleep 1
  done

  rm -f "${marker_file}"
  if buddyswitch_browser_check_endpoint 2>/dev/null; then
    echo "Browser cockpit not ready: $(buddyswitch_browser_url) (endpoint reachable but no usable page target)" >&2
  else
    echo "Browser cockpit not ready: $(buddyswitch_browser_url) (endpoint unreachable)" >&2
  fi
  echo "See log: ${BUDDYSWITCH_BROWSER_LOG_FILE}" >&2
  return 1
}

buddyswitch_browser_active_role() {
  local role
  role="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"
  if [[ -n "${role}" ]]; then
    printf '%s\n' "${role}"
    return 0
  fi
  if [[ -n "${BUDDYSWITCH_INSTANCE_JSON:-}" && -f "${BUDDYSWITCH_INSTANCE_JSON}" ]]; then
    python3 - "${BUDDYSWITCH_INSTANCE_JSON}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
role = payload.get("role")
if isinstance(role, str) and role.strip():
    print(role.strip())
PY
    return 0
  fi
  return 1
}

buddyswitch_browser_profile_capability() {
  local role_id="${1:-}"
  if [[ -z "${role_id}" ]]; then
    return 1
  fi
  python3 - "${BUDDYSWITCH_REPO_ROOT}" "${role_id}" <<'PY'
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
role_id = sys.argv[2]
sys.path.insert(0, str(repo_root / "scripts"))
import env_profiles  # noqa: E402

profile = env_profiles.require_env_profile(
    role_id,
    manifest_path=repo_root / "buddyswitch" / "manifest.toml",
    repo_root=repo_root,
)
capability = profile["tool_capability"]["browser_cockpit"]
print(capability)
PY
}

buddyswitch_browser_bootstrap() {
  local strict_mode active_role capability require_browser
  buddyswitch_browser_init_defaults
  buddyswitch_ensure_shared_env
  strict_mode="${BUDDYSWITCH_BROWSER_ENSURE_STRICT:-0}"
  require_browser=1
  if [[ "${strict_mode}" != "1" ]] && buddyswitch_browser_is_instance_mode; then
    active_role="$(buddyswitch_browser_active_role || true)"
    if [[ -n "${active_role}" ]]; then
      capability="$(buddyswitch_browser_profile_capability "${active_role}" || true)"
      if [[ "${capability}" == "available" ]]; then
        require_browser=0
      fi
    fi
  fi

  if buddyswitch_browser_ensure_cockpit_endpoint; then
    if buddyswitch_browser_ensure_cockpit_mcp; then
      return 0
    fi
    if [[ "${require_browser}" -eq 1 ]]; then
      return 1
    fi
    if ! buddyswitch_browser_disable_cockpit_mcp; then
      echo "Warning: browser cockpit MCP setup failed and stale cockpit MCP could not be removed; stopping optional-browser launch." >&2
      return 1
    fi
    echo "Warning: browser cockpit MCP setup failed for non-required role; continuing without browser cockpit MCP." >&2
    return 0
  fi

  if [[ "${require_browser}" -eq 1 ]]; then
    return 1
  fi
  if ! buddyswitch_browser_disable_cockpit_mcp; then
    echo "Warning: browser cockpit unavailable and stale cockpit MCP could not be removed; stopping optional-browser launch." >&2
    return 1
  fi
  echo "Warning: browser cockpit unavailable for non-required role; continuing without cockpit endpoint." >&2
  return 0
}

buddyswitch_browser_instance_stop() {
  local actor_id="$1"
  local marker_file marker_pid

  if [[ -z "${actor_id}" ]]; then
    echo "actor id is required" >&2
    return 2
  fi

  marker_file="${BUDDYSWITCH_SHARED_ROOT}/instances/${actor_id}/browser/chrome.pid"
  if [[ ! -f "${marker_file}" ]]; then
    return 0
  fi

  marker_pid="$(cat "${marker_file}" 2>/dev/null || true)"
  if [[ -n "${marker_pid}" && "${marker_pid}" =~ ^[0-9]+$ ]] && kill -0 "${marker_pid}" 2>/dev/null; then
    kill "${marker_pid}" 2>/dev/null || true
    sleep 0.2
    if kill -0 "${marker_pid}" 2>/dev/null; then
      kill -9 "${marker_pid}" 2>/dev/null || true
    fi
  fi
  rm -f "${marker_file}"
}

buddyswitch_browser_main() {
  local command arg

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
        buddyswitch_browser_validate_port_option "$2" || return $?
        export BUDDYSWITCH_BROWSER_PORT="$2"
        export BUDDYSWITCH_BROWSER_PORT_EXPLICIT=1
        shift 2
        ;;
      --profile-dir)
        if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
          echo "Missing value for --profile-dir" >&2
          buddyswitch_browser_usage >&2
          return 2
        fi
        export BUDDYSWITCH_BROWSER_PROFILE_DIR="$2"
        export BUDDYSWITCH_BROWSER_PROFILE_DIR_EXPLICIT=1
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
  buddyswitch_browser_init_defaults

  case "${command}" in
    status)
      buddyswitch_browser_status
      ;;
    ensure)
      BUDDYSWITCH_BROWSER_ENSURE_STRICT=1 buddyswitch_browser_bootstrap
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
