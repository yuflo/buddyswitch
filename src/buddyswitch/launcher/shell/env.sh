#!/usr/bin/env bash
set -euo pipefail

HOST_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_PACKAGE_ROOT="$(cd "${HOST_ENV_DIR}/../.." && pwd)"
source "${HOST_PACKAGE_ROOT}/foundation/host_control/shell/environment.sh"

buddyswitch_patch_codex_config() {
  local config_path
  local active_role
  local local_default_tmp_root
  local -a patch_args=()
  local -a temp_root_args=()
  config_path="${BUDDYSWITCH_CODEX_HOME}/config.toml"
  active_role="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"
  local_default_tmp_root="/tmp"

  patch_args=(
    --config "${config_path}"
    --source-root "${BUDDYSWITCH_SOURCE_ROOT}"
    --shared-root "${BUDDYSWITCH_SHARED_ROOT}"
    --source-codex-home "${BUDDYSWITCH_SOURCE_CODEX_HOME}"
  )

  if [[ -n "${active_role}" ]]; then
    temp_root_args=(--temp-root "${BUDDYSWITCH_INSTANCE_TMP}")
    patch_args+=(
      --manifest "${BUDDYSWITCH_PACKAGE_ROOT}/catalog/manifest.toml"
      --role "${active_role}"
      --instance-root "${BUDDYSWITCH_INSTANCE_ROOT}"
      --workspace-dir "${BUDDYSWITCH_WORKSPACE_DIR}"
      --project-workspace-dir "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
      --home "${BUDDYSWITCH_HOME}"
      --codex-home "${BUDDYSWITCH_CODEX_HOME}"
      --xdg-config-home "${BUDDYSWITCH_XDG_CONFIG_HOME}"
    )
    if [[ -n "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET:-}" ]]; then
      patch_args+=(--broker-socket "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}")
    fi
  else
    temp_root_args=(--temp-root "${local_default_tmp_root}")
    if [[ -n "${TMPDIR:-}" ]]; then
      temp_root_args+=(--temp-root "${TMPDIR}")
    fi
  fi

  "${BUDDYSWITCH_PYTHON}" -m buddyswitch.application.entrypoints.actor_build patch-config \
    "${patch_args[@]}" \
    "${temp_root_args[@]}"
}

buddyswitch_ensure_browser_ttl_config() {
  "${BUDDYSWITCH_PYTHON}" -m buddyswitch.application.entrypoints.browser_runtime ttl-config \
    ensure \
    --shared-root "${BUDDYSWITCH_SHARED_ROOT}" >/dev/null
}

buddyswitch_ensure_shared_env() {
  local shared_codex_home

  if [[ -n "${BUDDYSWITCH_ACTOR_ID:-}" ]]; then
    echo "Actor environments must be materialized by ActorEnvironmentBuilder." >&2
    return 2
  fi

  mkdir -p \
    "${BUDDYSWITCH_HOME}" \
    "${BUDDYSWITCH_XDG_CONFIG_HOME}" \
    "${BUDDYSWITCH_CODEX_HOME}" \
    "${BUDDYSWITCH_RUN_STATE_DIR}"

  buddyswitch_ensure_browser_ttl_config

  shared_codex_home="${BUDDYSWITCH_SHARED_ROOT}/codex-home"
  mkdir -p "${shared_codex_home}"

  if [[ ! -f "${BUDDYSWITCH_CODEX_HOME}/config.toml" ]]; then
    cat > "${BUDDYSWITCH_CODEX_HOME}/config.toml" <<'EOF'
[skills.bundled]
enabled = false

[features]
plugins = false
EOF
  fi

  buddyswitch_patch_codex_config

  if [[ ! -f "${shared_codex_home}/auth.json" && -f "${BUDDYSWITCH_SOURCE_CODEX_HOME}/auth.json" ]]; then
    cp "${BUDDYSWITCH_SOURCE_CODEX_HOME}/auth.json" "${shared_codex_home}/auth.json"
  fi

  if [[ "${BUDDYSWITCH_CODEX_HOME}" == "${shared_codex_home}" ]]; then
    return 0
  fi

  if [[ -f "${shared_codex_home}/auth.json" ]]; then
    rm -f "${BUDDYSWITCH_CODEX_HOME}/auth.json"
    ln -s "${shared_codex_home}/auth.json" "${BUDDYSWITCH_CODEX_HOME}/auth.json"
  fi

}

buddyswitch_codex_config_path() {
  printf '%s/config.toml\n' "${BUDDYSWITCH_CODEX_HOME}"
}

buddyswitch_env_mcp_has_server() {
  local server_name="$1"
  local config_path

  config_path="$(buddyswitch_codex_config_path)"
  if [[ ! -f "${config_path}" ]]; then
    return 1
  fi

  grep -Eq "^\\[mcp_servers\\.${server_name}\\]$" "${config_path}"
}

buddyswitch_env_mcp_matches_instance() {
  local server_name="$1"
  local config_path
  local active_role

  config_path="$(buddyswitch_codex_config_path)"
  active_role="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"
  if [[ ! -f "${config_path}" ]]; then
    return 1
  fi
  if [[ -z "${BUDDYSWITCH_ACTOR_ID:-}" || -z "${active_role}" || -z "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET:-}" ]]; then
    return 1
  fi

  "${BUDDYSWITCH_PYTHON}" - "${config_path}" "${server_name}" "${BUDDYSWITCH_PYTHON}" "${BUDDYSWITCH_ACTOR_ID}" "${active_role}" "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}" <<'PY'
import sys
import tomllib
from pathlib import Path

config_path = Path(sys.argv[1])
server_name = sys.argv[2]
expected_python = sys.argv[3]
actor_id = sys.argv[4]
role = sys.argv[5]
broker_socket = sys.argv[6]

try:
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)

server = payload.get("mcp_servers", {}).get(server_name)
if not isinstance(server, dict):
    raise SystemExit(1)
args = server.get("args")
if server.get("command") != expected_python or not isinstance(args, list):
    raise SystemExit(1)

expected_args = [
    "-m",
    "buddyswitch.application.entrypoints.env_mcp",
    "--actor-id",
    actor_id,
    "--role",
    role,
    "--broker-socket",
    broker_socket,
]
if args != expected_args:
    raise SystemExit(1)
PY
}

buddyswitch_env_mcp_remove_server() {
  local server_name="$1"
  buddyswitch_run_codex mcp remove "${server_name}"
}

buddyswitch_env_mcp_add_server() {
  local server_name="$1"
  local active_role
  active_role="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"

  if [[ -z "${active_role}" ]]; then
    echo "BuddySwitch env MCP registration requires an active role." >&2
    return 2
  fi
  if [[ -z "${BUDDYSWITCH_ACTOR_ID:-}" ]]; then
    echo "BuddySwitch env MCP registration requires BUDDYSWITCH_ACTOR_ID." >&2
    return 2
  fi
  if [[ -z "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET:-}" ]]; then
    echo "BuddySwitch env MCP registration requires BUDDYSWITCH_RUNTIME_BROKER_SOCKET." >&2
    return 2
  fi

  buddyswitch_run_codex mcp add "${server_name}" -- \
    "${BUDDYSWITCH_PYTHON}" \
    -m buddyswitch.application.entrypoints.env_mcp \
    --actor-id "${BUDDYSWITCH_ACTOR_ID}" \
    --role "${active_role}" \
    --broker-socket "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}" || return $?
  buddyswitch_patch_codex_config
}

buddyswitch_env_mcp_ensure() {
  local server_name
  server_name="${BUDDYSWITCH_ENV_MCP_NAME}"

  if buddyswitch_env_mcp_has_server "${server_name}"; then
    if buddyswitch_env_mcp_matches_instance "${server_name}"; then
      return 0
    fi
    buddyswitch_env_mcp_remove_server "${server_name}" || return $?
  fi

  buddyswitch_env_mcp_add_server "${server_name}"
}

buddyswitch_validate_role_id() {
  local role_id="$1"

  if [[ -z "${role_id}" ]]; then
    echo "Role id must not be empty." >&2
    return 2
  fi
  [[ "${role_id}" =~ ^[a-z][a-z0-9-]*$ ]] || {
    echo "Invalid role id: ${role_id}" >&2
    return 2
  }
}

buddyswitch_require_env_profile() {
  local role_id="$1"
  buddyswitch_validate_role_id "${role_id}" || return $?
  "${BUDDYSWITCH_PYTHON}" - "${role_id}" <<'PY'
import sys

from buddyswitch.runtime_support import env_manifest
from buddyswitch.application.build import activate_application

try:
    activate_application()
    env_manifest.require_role(env_manifest.load_manifest(), sys.argv[1])
except env_manifest.ManifestError as exc:
    print(str(exc), file=sys.stderr)
    raise SystemExit(1) from None
PY
}

buddyswitch_role_agents_template_path() {
  local role_id="$1"
  printf '%s/launcher/assets/roles/%s/AGENTS.md\n' "${BUDDYSWITCH_PACKAGE_ROOT}" "${role_id}"
}

buddyswitch_require_role_agents_template() {
  local role_id="$1"
  local template_path

  template_path="$(buddyswitch_role_agents_template_path "${role_id}")"
  if [[ ! -f "${template_path}" ]]; then
    echo "Role AGENTS template not found: ${template_path}" >&2
    return 1
  fi
  export BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE="${template_path}"
}

_buddyswitch_list_actor_ids_for_role() {
  local target_role="${1:-}"
  local instance_json actor_id

  for instance_json in "${BUDDYSWITCH_SHARED_ROOT}"/instances/*/instance.json; do
    [[ -f "${instance_json}" ]] || continue
    actor_id="$(
      "${BUDDYSWITCH_PYTHON}" - "${instance_json}" "${target_role}" <<'PY'
import json
import sys
from pathlib import Path

instance_json = Path(sys.argv[1])
target_role = sys.argv[2]

try:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

role = payload.get("role")
if target_role and role != target_role:
    raise SystemExit(0)

actor_id = payload.get("actor_id", instance_json.parent.name)
if isinstance(actor_id, str) and actor_id:
    print(actor_id)
PY
    )"
    [[ -n "${actor_id}" ]] || continue
    printf '%s\n' "${actor_id}"
  done
}

buddyswitch_count_active_app_servers() {
  local count=0 actor_id
  while IFS= read -r actor_id; do
    [[ -n "${actor_id}" ]] || continue
    if buddyswitch_instance_app_server_is_active "${actor_id}"; then
      count=$((count + 1))
    fi
  done < <(_buddyswitch_list_actor_ids_for_role)
  echo "${count}"
}

buddyswitch_count_active_app_servers_for_role() {
  local role="$1"
  local count=0 actor_id
  while IFS= read -r actor_id; do
    [[ -n "${actor_id}" ]] || continue
    if buddyswitch_instance_app_server_is_active "${actor_id}"; then
      count=$((count + 1))
    fi
  done < <(_buddyswitch_list_actor_ids_for_role "${role}")
  echo "${count}"
}

buddyswitch_arg_sets_native_web_search() {
  local value="$1"
  case "${value}" in
    web_search=*|*.web_search=*|*web_search=*)
      return 0
      ;;
  esac
  return 1
}

buddyswitch_print_native_search_rejection() {
  echo "Native Codex web_search is disabled in BuddySwitch product sessions." >&2
  echo "Use chrome-devtools-cockpit for browser-native discovery." >&2
  echo "Use chrome-devtools-cockpit.search_page for browser-native search page opening." >&2
  echo "Use search__request only for non-opening URL planning." >&2
  echo "Use search__status for search capability status." >&2
  echo 'Diagnostic: "$BUDDYSWITCH_PYTHON" -m buddyswitch.application.entrypoints.diagnostics status' >&2
}

buddyswitch_reject_native_search_args() {
  local arg next
  while [[ $# -gt 0 ]]; do
    arg="$1"
    next="${2:-}"
    case "${arg}" in
      --search|--search=*)
        buddyswitch_print_native_search_rejection
        return 2
        ;;
      -c|--config)
        if [[ -n "${next}" ]] && buddyswitch_arg_sets_native_web_search "${next}"; then
          buddyswitch_print_native_search_rejection
          return 2
        fi
        if [[ $# -ge 2 ]]; then
          shift 2
        else
          shift
        fi
        continue
        ;;
      -c*|--config=*)
        if buddyswitch_arg_sets_native_web_search "${arg}"; then
          buddyswitch_print_native_search_rejection
          return 2
        fi
        ;;
    esac
    shift || true
  done
  return 0
}

buddyswitch_run_codex() {
  if [[ -n "${BUDDYSWITCH_ROLE_ID:-}" || -n "${BUDDYSWITCH_ACTOR_ID:-}" ]]; then
    buddyswitch_reject_native_search_args "$@" || return $?
  fi
  if [[ "${BUDDYSWITCH_CODEX_BIN:-}" != /* || ! -x "${BUDDYSWITCH_CODEX_BIN}" ]]; then
    echo "A valid absolute BUDDYSWITCH_CODEX_BIN is required." >&2
    return 2
  fi
  if [[ -n "${BUDDYSWITCH_INSTANCE_TMP:-}" ]]; then
    mkdir -p "${BUDDYSWITCH_INSTANCE_TMP}"
    TMPDIR="${BUDDYSWITCH_INSTANCE_TMP}" \
    TMP="${BUDDYSWITCH_INSTANCE_TMP}" \
    TEMP="${BUDDYSWITCH_INSTANCE_TMP}" \
    TMPPREFIX="${BUDDYSWITCH_INSTANCE_TMP}/zsh" \
    BUDDYSWITCH_ACTOR_PRIVATE_DIR="${BUDDYSWITCH_ACTOR_PRIVATE_DIR:-}" \
    HOME="${BUDDYSWITCH_HOME}" \
    CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
    XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
    "${BUDDYSWITCH_CODEX_BIN}" "$@"
    return $?
  fi
  HOME="${BUDDYSWITCH_HOME}" \
  CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
  XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
  "${BUDDYSWITCH_CODEX_BIN}" "$@"
}

buddyswitch_validate_reset_root() {
  local shared_root normalized_root root_name

  shared_root="${BUDDYSWITCH_SHARED_ROOT:-}"
  normalized_root="${shared_root%/}"

  if [[ -z "${normalized_root}" || "${normalized_root}" == "/" ]]; then
    echo "Reset blocked: unsafe shared root '${shared_root}'." >&2
    return 1
  fi

  if [[ -L "${normalized_root}" ]]; then
    echo "Reset blocked: shared root is a symlink (${normalized_root})." >&2
    return 1
  fi

  if [[ -e "${normalized_root}" && ! -d "${normalized_root}" ]]; then
    echo "Reset blocked: shared root is not a directory (${normalized_root})." >&2
    return 1
  fi

  root_name="$(basename "${normalized_root}")"
  if [[ "${root_name}" != ".codex-buddyswitch" ]]; then
    echo "Reset blocked: BUDDYSWITCH_SHARED_ROOT must target a '.codex-buddyswitch' directory." >&2
    echo "Current: ${normalized_root}" >&2
    return 1
  fi

  return 0
}
