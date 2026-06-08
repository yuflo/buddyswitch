#!/usr/bin/env bash
set -euo pipefail

buddyswitch_workspace_repo_root() {
  local helper_dir repo_root

  helper_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_root="${BUDDYSWITCH_REPO_ROOT:-${REPO_ROOT:-$(cd "${helper_dir}/../.." && pwd)}}"
  printf '%s\n' "${repo_root}"
}

buddyswitch_workspace_repo_common_dir() {
  local repo_root common_dir

  repo_root="$(buddyswitch_workspace_repo_root)"
  common_dir="$(git -C "${repo_root}" rev-parse --git-common-dir)"
  if [[ "${common_dir}" != /* ]]; then
    common_dir="${repo_root}/${common_dir}"
  fi
  printf '%s\n' "${common_dir}"
}

buddyswitch_workspace_init_defaults() {
  local repo_root

  repo_root="$(buddyswitch_workspace_repo_root)"

  export BUDDYSWITCH_WORKSPACE_DIR="${BUDDYSWITCH_WORKSPACE_DIR:-${BUDDYSWITCH_SHARED_ROOT}/workspace}"
  export BUDDYSWITCH_PROJECT_WORKSPACE_DIR="${BUDDYSWITCH_PROJECT_WORKSPACE_DIR:-${BUDDYSWITCH_SHARED_ROOT}/project/workspace}"
}

buddyswitch_workspace_canonical_path() {
  python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve(strict=False))' "$1"
}

buddyswitch_workspace_force_remove_path() {
  local target="$1"
  if [[ -z "${target}" ]]; then
    return 0
  fi
  if [[ -L "${target}" || -f "${target}" ]]; then
    rm -f "${target}"
    return 0
  fi
  if [[ -d "${target}" ]]; then
    chmod -R u+w "${target}" 2>/dev/null || true
    find "${target}" -type d -exec chmod u+rwx {} + 2>/dev/null || true
    rm -rf "${target}"
  fi
}

buddyswitch_workspace_force_make_writable() {
  local target="$1"
  if [[ -z "${target}" || ! -d "${target}" ]]; then
    return 0
  fi
  chmod -R u+w "${target}" 2>/dev/null || true
  find "${target}" -type d -exec chmod u+rwx {} + 2>/dev/null || true
}

buddyswitch_workspace_validate_workspace_dir() {
  local workspace_dir shared_root normalized_workspace normalized_shared_root reserved_root

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR:-}"
  shared_root="${BUDDYSWITCH_SHARED_ROOT:-}"
  normalized_workspace="$(buddyswitch_workspace_canonical_path "${workspace_dir%/}")"
  normalized_shared_root="$(buddyswitch_workspace_canonical_path "${shared_root%/}")"

  if [[ "${normalized_workspace}" == "${normalized_shared_root}" ]]; then
    echo "workspace dir must be under BUDDYSWITCH_SHARED_ROOT" >&2
    echo "workspace: ${normalized_workspace}" >&2
    echo "shared root: ${normalized_shared_root}" >&2
    echo "reserved root: ${normalized_shared_root}" >&2
    return 1
  fi

  for reserved_root in \
    "${normalized_shared_root}/home" \
    "${normalized_shared_root}/codex-home" \
    "${normalized_shared_root}/run" \
    "${normalized_shared_root}/chrome"; do
    case "${normalized_workspace}" in
      "${reserved_root}" | "${reserved_root}/"*)
        echo "workspace dir must be under BUDDYSWITCH_SHARED_ROOT" >&2
        echo "workspace: ${normalized_workspace}" >&2
        echo "shared root: ${normalized_shared_root}" >&2
        echo "reserved root: ${reserved_root}" >&2
        return 1
        ;;
    esac
  done

  case "${normalized_workspace}" in
    "${normalized_shared_root}/"*)
      return 0
      ;;
  esac

  echo "workspace dir must be under BUDDYSWITCH_SHARED_ROOT" >&2
  echo "workspace: ${normalized_workspace}" >&2
  echo "shared root: ${normalized_shared_root}" >&2
  return 1
}

buddyswitch_workspace_validate_project_workspace_dir() {
  local project_workspace shared_root normalized_project normalized_shared_root reserved_root

  project_workspace="${BUDDYSWITCH_PROJECT_WORKSPACE_DIR:-}"
  shared_root="${BUDDYSWITCH_SHARED_ROOT:-}"
  normalized_project="$(buddyswitch_workspace_canonical_path "${project_workspace%/}")"
  normalized_shared_root="$(buddyswitch_workspace_canonical_path "${shared_root%/}")"

  if [[ "${normalized_project}" == "${normalized_shared_root}" ]]; then
    echo "project workspace dir must be under BUDDYSWITCH_SHARED_ROOT" >&2
    echo "project workspace: ${normalized_project}" >&2
    echo "shared root: ${normalized_shared_root}" >&2
    return 1
  fi

  for reserved_root in \
    "${normalized_shared_root}/home" \
    "${normalized_shared_root}/codex-home" \
    "${normalized_shared_root}/run" \
    "${normalized_shared_root}/chrome" \
    "${normalized_shared_root}/instances" \
    "${normalized_shared_root}/state"; do
    case "${normalized_project}" in
      "${reserved_root}" | "${reserved_root}/"*)
        echo "project workspace dir must not be inside reserved BuddySwitch runtime state" >&2
        echo "project workspace: ${normalized_project}" >&2
        echo "reserved root: ${reserved_root}" >&2
        return 1
        ;;
    esac
  done

  case "${normalized_project}" in
    "${normalized_shared_root}/"*)
      return 0
      ;;
  esac

  echo "project workspace dir must be under BUDDYSWITCH_SHARED_ROOT" >&2
  echo "project workspace: ${normalized_project}" >&2
  echo "shared root: ${normalized_shared_root}" >&2
  return 1
}

buddyswitch_workspace_is_valid_execution_worktree() {
  local workspace_dir repo_common workspace_common

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  repo_common="$(buddyswitch_workspace_repo_common_dir)"

  git -C "${workspace_dir}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  workspace_common="$(git -C "${workspace_dir}" rev-parse --git-common-dir 2>/dev/null || true)"
  [[ "${workspace_common}" == "${repo_common}" ]]
}

buddyswitch_workspace_is_valid_project_worktree() {
  local project_workspace repo_common project_common

  project_workspace="${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
  repo_common="$(buddyswitch_workspace_repo_common_dir)"

  git -C "${project_workspace}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  project_common="$(git -C "${project_workspace}" rev-parse --git-common-dir 2>/dev/null || true)"
  if [[ "${project_common}" != /* ]]; then
    project_common="${project_workspace}/${project_common}"
  fi
  project_common="$(buddyswitch_workspace_canonical_path "${project_common}")"
  repo_common="$(buddyswitch_workspace_canonical_path "${repo_common}")"
  [[ "${project_common}" == "${repo_common}" ]]
}

buddyswitch_workspace_project_sparse_paths() {
  cat <<'EOF'
projects/app/
EOF
}

buddyswitch_workspace_execution_sparse_paths() {
  cat <<'EOF'
scripts/env/
scripts/runtime_kernel/
scripts/turn_runtime.py
scripts/env_store.py
scripts/env_legacy_store.py
scripts/env_manifest.py
scripts/env_profiles.py
scripts/browser_evidence.py
buddyswitch/manifest.toml
buddyswitch/env-profiles/
framework/contracts/
EOF
}

buddyswitch_workspace_execution_forbidden_entries() {
  cat <<'EOF'
buddyswitch/skills
tools
tests
docs
README.md
buddyswitch-codex
runs
buddyswitch/content/runs
EOF
}

buddyswitch_workspace_runtime_managed_paths() {
  cat <<'EOF'
AGENTS.md
.agents/skills
.runtime
.codex
framework/contracts
projects/app
EOF
}

buddyswitch_workspace_execution_worktree_has_sparse_boundary() {
  local workspace_dir="$1"
  local require_runtime_files="${2:-1}"
  local sparse_paths expected forbidden_entry required_runtime_file

  git -C "${workspace_dir}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  sparse_paths="$(git -C "${workspace_dir}" sparse-checkout list 2>/dev/null || true)"
  expected="$(buddyswitch_workspace_execution_sparse_paths)"
  [[ "${sparse_paths}" == "${expected}" ]] || return 1

  while IFS= read -r forbidden_entry; do
    [[ -n "${forbidden_entry}" ]] || continue
    if [[ -e "${workspace_dir}/${forbidden_entry}" || -L "${workspace_dir}/${forbidden_entry}" ]]; then
      return 1
    fi
  done < <(buddyswitch_workspace_execution_forbidden_entries)

  if [[ "${require_runtime_files}" != "0" ]]; then
    for required_runtime_file in \
      scripts/env/client.py \
      scripts/runtime_kernel/broker.py \
      scripts/turn_runtime.py \
      scripts/env_legacy_store.py \
      buddyswitch/manifest.toml \
      framework/contracts/pm.md; do
      [[ -e "${workspace_dir}/${required_runtime_file}" ]] || return 1
    done
  fi
}

buddyswitch_workspace_execution_worktree_has_dirty_unmanaged_changes() {
  local workspace_dir="$1"
  local status_output managed_path
  local -a status_args

  status_args=(status --porcelain --untracked-files=all -- .)
  while IFS= read -r managed_path; do
    [[ -n "${managed_path}" ]] || continue
    status_args+=(":(exclude)${managed_path}")
    status_args+=(":(exclude)${managed_path}/**")
  done < <(buddyswitch_workspace_runtime_managed_paths)
  while IFS= read -r managed_path; do
    [[ -n "${managed_path}" ]] || continue
    managed_path="${managed_path%/}"
    status_args+=(":(exclude)${managed_path}")
    status_args+=(":(exclude)${managed_path}/**")
  done < <(buddyswitch_workspace_execution_sparse_paths)

  status_output="$(git -C "${workspace_dir}" "${status_args[@]}")"
  [[ -n "${status_output}" ]]
}

buddyswitch_workspace_report_dirty_unmanaged_execution_changes() {
  local workspace_dir="$1"
  local managed_path
  local -a status_args

  echo "execution workspace has local changes outside runtime-managed paths; refusing to narrow sparse checkout" >&2
  echo "execution workspace: ${workspace_dir}" >&2

  status_args=(status --short --untracked-files=all -- .)
  while IFS= read -r managed_path; do
    [[ -n "${managed_path}" ]] || continue
    status_args+=(":(exclude)${managed_path}")
    status_args+=(":(exclude)${managed_path}/**")
  done < <(buddyswitch_workspace_runtime_managed_paths)
  while IFS= read -r managed_path; do
    [[ -n "${managed_path}" ]] || continue
    managed_path="${managed_path%/}"
    status_args+=(":(exclude)${managed_path}")
    status_args+=(":(exclude)${managed_path}/**")
  done < <(buddyswitch_workspace_execution_sparse_paths)

  git -C "${workspace_dir}" "${status_args[@]}" >&2 || true
}

buddyswitch_workspace_configure_execution_sparse_checkout() {
  local workspace_dir="$1"
  local mode="${2:-existing}"
  local sparse_path
  local repo_root target_head current_head
  local require_runtime_files=1
  local -a sparse_paths

  if [[ "${mode}" != "fresh" && "${mode}" != "existing" ]]; then
    echo "unsupported execution sparse checkout mode: ${mode}" >&2
    return 2
  fi

  if [[ "${mode}" != "fresh" ]] && buddyswitch_workspace_execution_worktree_has_dirty_unmanaged_changes "${workspace_dir}"; then
    buddyswitch_workspace_report_dirty_unmanaged_execution_changes "${workspace_dir}"
    return 3
  fi

  sparse_paths=()
  while IFS= read -r sparse_path; do
    [[ -n "${sparse_path}" ]] || continue
    sparse_paths+=("${sparse_path}")
  done < <(buddyswitch_workspace_execution_sparse_paths)

  if [[ "${mode}" == "existing" ]]; then
    repo_root="$(buddyswitch_workspace_repo_root)"
    target_head="$(git -C "${repo_root}" rev-parse HEAD 2>/dev/null || true)"
    current_head="$(git -C "${workspace_dir}" rev-parse HEAD 2>/dev/null || true)"
    # Allow stale detached worktrees to adopt sparse rules first; sync step will
    # advance to repo HEAD and then satisfy required runtime file sentinels.
    if [[ -n "${target_head}" && -n "${current_head}" && "${current_head}" != "${target_head}" ]]; then
      require_runtime_files=0
    fi
  fi

  git -C "${workspace_dir}" sparse-checkout init --no-cone >/dev/null
  git -C "${workspace_dir}" sparse-checkout set --no-cone "${sparse_paths[@]}" >/dev/null
  git -C "${workspace_dir}" checkout HEAD >/dev/null

  if ! buddyswitch_workspace_execution_worktree_has_sparse_boundary "${workspace_dir}" "${require_runtime_files}"; then
    echo "execution workspace sparse checkout did not reach expected runtime boundary" >&2
    echo "execution workspace: ${workspace_dir}" >&2
    return 1
  fi
}

buddyswitch_workspace_project_worktree_has_sparse_boundary() {
  local project_workspace="$1"
  local sparse_paths forbidden_entry expected

  git -C "${project_workspace}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  sparse_paths="$(git -C "${project_workspace}" sparse-checkout list 2>/dev/null || true)"
  expected="$(buddyswitch_workspace_project_sparse_paths)"
  [[ "${sparse_paths}" == "${expected}" ]] || return 1

  for forbidden_entry in \
    buddyswitch \
    tools \
    scripts \
    tests \
    framework \
    docs \
    AGENTS.md \
    README.md \
    buddyswitch-codex; do
    if [[ -e "${project_workspace}/${forbidden_entry}" || -L "${project_workspace}/${forbidden_entry}" ]]; then
      return 1
    fi
  done

  [[ -d "${project_workspace}/projects/app" ]]
}

buddyswitch_workspace_project_worktree_has_dirty_non_project_changes() {
  local project_workspace="$1"
  local status_output

  status_output="$(
    git -C "${project_workspace}" status --porcelain --untracked-files=all -- . ':(exclude)projects/app/**'
  )"
  [[ -n "${status_output}" ]]
}

buddyswitch_workspace_report_dirty_non_project_changes() {
  local project_workspace="$1"

  echo "project workspace has local changes outside projects/app; refusing to narrow sparse checkout" >&2
  echo "project workspace: ${project_workspace}" >&2
  git -C "${project_workspace}" status --short --untracked-files=all -- . ':(exclude)projects/app/**' >&2 || true
}

buddyswitch_workspace_configure_project_sparse_checkout() {
  local project_workspace="$1"
  local mode="${2:-existing}"

  if [[ "${mode}" != "fresh" && "${mode}" != "existing" ]]; then
    echo "unsupported project sparse checkout mode: ${mode}" >&2
    return 2
  fi

  if [[ "${mode}" != "fresh" ]] && buddyswitch_workspace_project_worktree_has_dirty_non_project_changes "${project_workspace}"; then
    buddyswitch_workspace_report_dirty_non_project_changes "${project_workspace}"
    return 3
  fi

  git -C "${project_workspace}" sparse-checkout init --no-cone >/dev/null
  git -C "${project_workspace}" sparse-checkout set --no-cone projects/app/ >/dev/null
  git -C "${project_workspace}" checkout HEAD >/dev/null

  if ! buddyswitch_workspace_project_worktree_has_sparse_boundary "${project_workspace}"; then
    echo "project workspace sparse checkout did not reach expected projects/app boundary" >&2
    echo "project workspace: ${project_workspace}" >&2
    return 1
  fi
}

buddyswitch_workspace_force_rebuild_project_worktree() {
  local project_workspace repo_root

  project_workspace="${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
  repo_root="$(buddyswitch_workspace_repo_root)"
  buddyswitch_workspace_validate_project_workspace_dir

  mkdir -p "$(dirname "${project_workspace}")"
  if [[ -e "${project_workspace}" ]]; then
    git -C "${repo_root}" worktree remove --force "${project_workspace}" >/dev/null 2>&1 || true
  fi
  if [[ -e "${project_workspace}" ]]; then
    if [[ -d "${project_workspace}" ]] && [[ -z "$(find "${project_workspace}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
      rmdir "${project_workspace}"
    else
      echo "project workspace exists and is not a valid git worktree; refusing to delete possible product source" >&2
      echo "project workspace: ${project_workspace}" >&2
      return 3
    fi
  fi
  git -C "${repo_root}" worktree prune >/dev/null 2>&1 || true
  git -C "${repo_root}" worktree add --detach --no-checkout "${project_workspace}" HEAD >/dev/null
  buddyswitch_workspace_configure_project_sparse_checkout "${project_workspace}" fresh
}

buddyswitch_workspace_ensure_project_worktree() {
  buddyswitch_workspace_init_defaults
  buddyswitch_workspace_validate_project_workspace_dir
  if buddyswitch_workspace_is_valid_project_worktree; then
    if buddyswitch_workspace_project_worktree_has_dirty_non_project_changes "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"; then
      buddyswitch_workspace_report_dirty_non_project_changes "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
      return 3
    fi
    if buddyswitch_workspace_project_worktree_has_sparse_boundary "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"; then
      return 0
    fi
    buddyswitch_workspace_configure_project_sparse_checkout "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
    return $?
  fi

  buddyswitch_workspace_force_rebuild_project_worktree
}

buddyswitch_workspace_require_path_under_shared_root() {
  local label="$1"
  local raw_path="$2"
  local normalized_path normalized_shared_root

  normalized_path="$(buddyswitch_workspace_canonical_path "${raw_path%/}")"
  normalized_shared_root="$(buddyswitch_workspace_canonical_path "${BUDDYSWITCH_SHARED_ROOT%/}")"
  case "${normalized_path}" in
    "${normalized_shared_root}" | "${normalized_shared_root}/"*)
      printf '%s\n' "${normalized_path}"
      return 0
      ;;
  esac

  echo "${label} must resolve under BUDDYSWITCH_SHARED_ROOT" >&2
  echo "${label}: ${normalized_path}" >&2
  echo "shared root: ${normalized_shared_root}" >&2
  return 1
}

buddyswitch_workspace_repair_runtime_projects_app_projection() {
  local runtime_projects_app target_projects_app
  local runtime_resolved target_resolved

  runtime_projects_app="${BUDDYSWITCH_WORKSPACE_DIR}/projects/app"
  target_projects_app="${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app"

  runtime_resolved="$(
    buddyswitch_workspace_require_path_under_shared_root \
      "runtime projects/app path" \
      "${runtime_projects_app}"
  )" || return $?
  target_resolved="$(
    buddyswitch_workspace_require_path_under_shared_root \
      "shared projects/app target" \
      "${target_projects_app}"
  )" || return $?

  if [[ ! -d "${target_projects_app}" ]]; then
    echo "shared projects/app target is missing: ${target_projects_app}" >&2
    return 1
  fi

  if [[ -L "${runtime_projects_app}" ]]; then
    if [[ "${runtime_resolved}" == "${target_resolved}" ]]; then
      return 0
    fi
  fi

  mkdir -p "$(dirname "${runtime_projects_app}")"
  buddyswitch_workspace_force_remove_path "${runtime_projects_app}"
  ln -s "${target_projects_app}" "${runtime_projects_app}"
}

buddyswitch_workspace_runtime_output_paths() {
  true
}

buddyswitch_workspace_local_runtime_paths() {
  cat <<'EOF'
private
EOF
}

buddyswitch_workspace_is_instance_mode() {
  [[ -n "${BUDDYSWITCH_ACTOR_ID:-}" ]]
}

buddyswitch_workspace_neutralize_project_codex_config() {
  local workspace_dir project_config project_config_dir

  if ! buddyswitch_workspace_is_instance_mode; then
    return 0
  fi

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  project_config="${workspace_dir}/.codex/config.toml"
  project_config_dir="$(dirname "${project_config}")"

  buddyswitch_workspace_require_path_under_shared_root \
    "workspace dir" \
    "${workspace_dir}" >/dev/null || return $?

  # If .codex is a symlink, remove the workspace-local symlink itself.
  # Never remove files through the symlink target.
  if [[ -L "${project_config_dir}" ]]; then
    rm -f "${project_config_dir}"
    return 0
  fi

  if [[ -e "${project_config}" || -L "${project_config}" ]]; then
    rm -f "${project_config}"
  fi

  rmdir "${project_config_dir}" >/dev/null 2>&1 || true
}

buddyswitch_workspace_stage_runtime_outputs() {
  local staging_root="$1"
  local workspace_dir relative_path source_path staged_path

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  while IFS= read -r relative_path; do
    source_path="${workspace_dir}/${relative_path}"
    staged_path="${staging_root}/${relative_path}"
    if [[ ! -e "${source_path}" ]]; then
      continue
    fi
    mkdir -p "$(dirname "${staged_path}")"
    mv "${source_path}" "${staged_path}"
  done < <(buddyswitch_workspace_runtime_output_paths)
}

buddyswitch_workspace_restore_runtime_outputs() {
  local staging_root="$1"
  local workspace_dir relative_path staged_path target_path

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  while IFS= read -r relative_path; do
    staged_path="${staging_root}/${relative_path}"
    target_path="${workspace_dir}/${relative_path}"
    if [[ ! -e "${staged_path}" ]]; then
      continue
    fi
    buddyswitch_workspace_force_remove_path "${target_path}"
    mkdir -p "$(dirname "${target_path}")"
    mv "${staged_path}" "${target_path}"
  done < <(buddyswitch_workspace_runtime_output_paths)
}

buddyswitch_workspace_force_rebuild_execution_worktree() {
  local workspace_dir repo_root staging_root
  local cleanup_staging=0

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  repo_root="$(buddyswitch_workspace_repo_root)"
  buddyswitch_workspace_validate_workspace_dir

  mkdir -p "${BUDDYSWITCH_SHARED_ROOT}"
  if [[ -d "${workspace_dir}" ]]; then
    staging_root="$(mktemp -d "${BUDDYSWITCH_SHARED_ROOT}/workspace-outputs.XXXXXX")"
    cleanup_staging=1
    buddyswitch_workspace_stage_runtime_outputs "${staging_root}"
  fi

  mkdir -p "$(dirname "${workspace_dir}")"
  git -C "${repo_root}" worktree remove --force "${workspace_dir}" >/dev/null 2>&1 || true
  if ! buddyswitch_workspace_force_remove_path "${workspace_dir}"; then
    if [[ "${cleanup_staging}" -eq 1 ]]; then
      buddyswitch_workspace_restore_runtime_outputs "${staging_root}"
      buddyswitch_workspace_force_remove_path "${staging_root}"
    fi
    return 1
  fi
  git -C "${repo_root}" worktree prune >/dev/null 2>&1 || true
  if ! git -C "${repo_root}" worktree add --detach --no-checkout "${workspace_dir}" HEAD >/dev/null; then
    if [[ "${cleanup_staging}" -eq 1 ]]; then
      buddyswitch_workspace_restore_runtime_outputs "${staging_root}"
      buddyswitch_workspace_force_remove_path "${staging_root}"
    fi
    return 1
  fi
  if ! buddyswitch_workspace_configure_execution_sparse_checkout "${workspace_dir}" fresh; then
    if [[ "${cleanup_staging}" -eq 1 ]]; then
      buddyswitch_workspace_restore_runtime_outputs "${staging_root}"
      buddyswitch_workspace_force_remove_path "${staging_root}"
    fi
    return 1
  fi

  if [[ "${cleanup_staging}" -eq 1 ]]; then
    buddyswitch_workspace_restore_runtime_outputs "${staging_root}"
    buddyswitch_workspace_force_remove_path "${staging_root}"
  fi
}

buddyswitch_workspace_remove_registered_worktrees_under() {
  local root="$1"
  local repo_root normalized_root worktree_path normalized_worktree_path

  repo_root="$(buddyswitch_workspace_repo_root)"
  if [[ -z "${root}" || ! -d "${root}" ]]; then
    return 0
  fi
  if ! git -C "${repo_root}" rev-parse --git-dir >/dev/null 2>&1; then
    return 0
  fi
  normalized_root="$(buddyswitch_workspace_canonical_path "${root}")"

  while IFS= read -r line; do
    case "${line}" in
      worktree\ *)
        worktree_path="${line#worktree }"
        normalized_worktree_path="$(buddyswitch_workspace_canonical_path "${worktree_path}")"
        case "${normalized_worktree_path}" in
          "${normalized_root}" | "${normalized_root}/"*)
            buddyswitch_workspace_force_make_writable "${worktree_path}"
            git -C "${repo_root}" worktree remove --force "${worktree_path}" >/dev/null 2>&1 || true
            ;;
        esac
        ;;
    esac
  done < <(git -C "${repo_root}" worktree list --porcelain 2>/dev/null || true)

  git -C "${repo_root}" worktree prune >/dev/null 2>&1 || true
}

buddyswitch_workspace_remove_registered_worktrees_under_strict() {
  local root="$1"
  local repo_root normalized_root worktree_path normalized_worktree_path remove_failed=0

  repo_root="$(buddyswitch_workspace_repo_root)"
  if [[ -z "${root}" || ! -d "${root}" ]]; then
    return 0
  fi
  if ! git -C "${repo_root}" rev-parse --git-dir >/dev/null 2>&1; then
    return 0
  fi
  normalized_root="$(buddyswitch_workspace_canonical_path "${root}")"

  while IFS= read -r line; do
    case "${line}" in
      worktree\ *)
        worktree_path="${line#worktree }"
        normalized_worktree_path="$(buddyswitch_workspace_canonical_path "${worktree_path}")"
        case "${normalized_worktree_path}" in
          "${normalized_root}" | "${normalized_root}/"*)
            buddyswitch_workspace_force_make_writable "${worktree_path}"
            if ! git -C "${repo_root}" worktree remove --force "${worktree_path}"; then
              remove_failed=1
            fi
            ;;
        esac
        ;;
    esac
  done < <(git -C "${repo_root}" worktree list --porcelain)

  if [[ "${remove_failed}" -ne 0 ]]; then
    return 1
  fi
  git -C "${repo_root}" worktree prune
}

buddyswitch_workspace_ensure_execution_worktree() {
  local workspace_dir

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  if ! buddyswitch_workspace_is_valid_execution_worktree; then
    buddyswitch_workspace_force_rebuild_execution_worktree || return $?
    buddyswitch_workspace_sync_runtime_surface
    return $?
  fi

  if buddyswitch_workspace_execution_worktree_has_sparse_boundary "${workspace_dir}"; then
    buddyswitch_workspace_sync_runtime_surface
    return $?
  fi

  buddyswitch_workspace_configure_execution_sparse_checkout "${workspace_dir}" existing || return $?
  buddyswitch_workspace_sync_runtime_surface
}

buddyswitch_workspace_install_runtime_agents() {
  local workspace_dir template_path role_id

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  template_path="${BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE:-}"
  role_id="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"
  if [[ -z "${template_path}" ]]; then
    echo "BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE is required for runtime AGENTS installation." >&2
    return 1
  fi
  if [[ ! -f "${template_path}" ]]; then
    echo "Runtime AGENTS template not found: ${template_path}" >&2
    return 1
  fi
  if [[ -z "${role_id}" ]]; then
    echo "Active role id is required for runtime AGENTS installation." >&2
    return 1
  fi

  cp "${template_path}" "${workspace_dir}/AGENTS.md"
}

buddyswitch_workspace_install_runtime_skills() {
  local role_id repo_root

  role_id="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"
  if [[ -z "${role_id}" ]]; then
    return 0
  fi

  repo_root="$(buddyswitch_workspace_repo_root)"
  python3 "${repo_root}/scripts/runtime_skills.py" install \
    --role "${role_id}" \
    --workspace "${BUDDYSWITCH_WORKSPACE_DIR}"
}

buddyswitch_workspace_sync_runtime_surface() {
  local repo_root target_head current_head
  local workspace_dir
  local sparse_path
  local -a sparse_paths

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  repo_root="$(buddyswitch_workspace_repo_root)"
  target_head="$(git -C "${repo_root}" rev-parse HEAD)"
  current_head="$(git -C "${workspace_dir}" rev-parse HEAD)"
  if [[ "${current_head}" != "${target_head}" ]]; then
    git -C "${workspace_dir}" checkout --detach -f "${target_head}" >/dev/null
  fi

  sparse_paths=()
  while IFS= read -r sparse_path; do
    [[ -n "${sparse_path}" ]] || continue
    sparse_paths+=("${sparse_path}")
  done < <(buddyswitch_workspace_execution_sparse_paths)
  if buddyswitch_workspace_execution_worktree_has_sparse_boundary "${workspace_dir}"; then
    git -C "${workspace_dir}" checkout HEAD -- "${sparse_paths[@]}" >/dev/null
  else
    buddyswitch_workspace_configure_execution_sparse_checkout "${workspace_dir}" existing || return $?
  fi

  buddyswitch_workspace_overlay_runtime_source_surface

  buddyswitch_workspace_cleanup_stale_state_projections
  buddyswitch_workspace_sync_runtime_contracts
  buddyswitch_workspace_neutralize_project_codex_config
}

buddyswitch_workspace_overlay_runtime_source_surface() {
  local repo_root workspace_dir sparse_path relative_path source_path target_path

  repo_root="$(buddyswitch_workspace_repo_root)"
  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  while IFS= read -r sparse_path; do
    [[ -n "${sparse_path}" ]] || continue
    relative_path="${sparse_path%/}"
    source_path="${repo_root}/${relative_path}"
    target_path="${workspace_dir}/${relative_path}"
    if [[ ! -e "${source_path}" && ! -L "${source_path}" ]]; then
      buddyswitch_workspace_force_remove_path "${target_path}"
      continue
    fi
    buddyswitch_workspace_force_remove_path "${target_path}"
    mkdir -p "$(dirname "${target_path}")"
    cp -R "${source_path}" "${target_path}"
  done < <(buddyswitch_workspace_execution_sparse_paths)
}

buddyswitch_workspace_sync_runtime_contracts() {
  local repo_root workspace_dir source_contracts target_contracts

  repo_root="$(buddyswitch_workspace_repo_root)"
  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  source_contracts="${repo_root}/framework/contracts"
  target_contracts="${workspace_dir}/framework/contracts"
  if [[ ! -d "${source_contracts}" ]]; then
    return 0
  fi
  buddyswitch_workspace_force_remove_path "${target_contracts}"
  mkdir -p "${workspace_dir}/framework"
  cp -R "${source_contracts}" "${target_contracts}"
}

buddyswitch_workspace_ensure_state_skeleton() {
  local workspace_dir relative_dir

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  if buddyswitch_workspace_is_instance_mode; then
    while IFS= read -r relative_dir; do
      mkdir -p "${workspace_dir}/${relative_dir}"
    done < <(buddyswitch_workspace_local_runtime_paths)
    buddyswitch_workspace_cleanup_stale_state_projections
    return
  fi

  while IFS= read -r relative_dir; do
    mkdir -p "${workspace_dir}/${relative_dir}"
  done <<'EOF'
buddyswitch/objects/tracks
buddyswitch/objects/artifacts
buddyswitch/objects/messages
buddyswitch/objects/comments
EOF
}

buddyswitch_workspace_migrate_projection_files() {
  local source_root="$1"
  local target_root="$2"
  local file_glob="$3"
  local source_file relative_path target_file

  [[ -d "${source_root}" ]] || return 0
  mkdir -p "${target_root}"

  while IFS= read -r source_file; do
    [[ -n "${source_file}" ]] || continue
    relative_path="${source_file#${source_root}/}"
    target_file="${target_root}/${relative_path}"
    mkdir -p "$(dirname "${target_file}")"
    if [[ -e "${target_file}" ]]; then
      if cmp -s "${source_file}" "${target_file}"; then
        continue
      fi
      echo "state projection conflict for ${relative_path}" >&2
      echo "workspace source: ${source_file}" >&2
      echo "state target: ${target_file}" >&2
      return 1
    fi
    cp -p "${source_file}" "${target_file}"
  done < <(find "${source_root}" -type f -name "${file_glob}" -print | sort)
}

buddyswitch_workspace_cleanup_projection_dir() {
  local workspace_path="$1"
  local state_path="$2"
  local file_glob="$3"

  if [[ -L "${workspace_path}" ]]; then
    rm -f "${workspace_path}"
    return 0
  fi
  if [[ ! -e "${workspace_path}" ]]; then
    return 0
  fi
  if [[ ! -d "${workspace_path}" ]]; then
    echo "stale projection path must be a directory or symlink: ${workspace_path}" >&2
    return 1
  fi

  if ! buddyswitch_workspace_migrate_projection_files "${workspace_path}" "${state_path}" "${file_glob}"; then
    return 1
  fi
  buddyswitch_workspace_force_remove_path "${workspace_path}"
}

buddyswitch_workspace_cleanup_stale_state_projections() {
  local workspace_dir state_root workspace_objects_root state_objects_root
  local legacy_runtime_local_root workspace_private_root

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  state_root="${BUDDYSWITCH_SHARED_ROOT}/state"
  workspace_objects_root="${workspace_dir}/buddyswitch/objects"
  state_objects_root="${state_root}/buddyswitch/objects"
  legacy_runtime_local_root="${workspace_dir}/buddyswitch/local"

  buddyswitch_workspace_cleanup_projection_dir "${workspace_objects_root}" "${state_objects_root}" "*.json" || return $?

  for workspace_private_root in \
    "${legacy_runtime_local_root}/private"
  do
    if [[ -L "${workspace_private_root}" ]]; then
      rm -f "${workspace_private_root}"
      continue
    fi
    if [[ ! -d "${workspace_private_root}" ]]; then
      continue
    fi
    buddyswitch_workspace_force_remove_path "${workspace_private_root}" || return $?
  done
}

buddyswitch_workspace_active_role() {
  local role_id
  role_id="${BUDDYSWITCH_ROLE_ID:-${BUDDYSWITCH_START_ROLE:-}}"
  printf '%s\n' "${role_id}"
}

buddyswitch_workspace_install_guardrail_hooks() {
  local hooks_root workspace_dir git_dir config_worktree

  hooks_root="${BUDDYSWITCH_SHARED_ROOT}/hooks"
  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  git_dir="$(git -C "${workspace_dir}" rev-parse --git-dir)"
  config_worktree="${git_dir}/config.worktree"

  mkdir -p "${hooks_root}"

  cat > "${hooks_root}/pre-commit" <<'EOF'
#!/usr/bin/env bash
echo "Blocked: launcher-owned runtime workspace does not allow commits." >&2
exit 1
EOF

  cat > "${hooks_root}/pre-rebase" <<'EOF'
#!/usr/bin/env bash
echo "Blocked: launcher-owned runtime workspace does not allow rebases." >&2
exit 1
EOF

  cat > "${hooks_root}/pre-push" <<'EOF'
#!/usr/bin/env bash
echo "Blocked: launcher-owned runtime workspace does not allow pushes." >&2
exit 1
EOF

  chmod +x "${hooks_root}/pre-commit" "${hooks_root}/pre-rebase" "${hooks_root}/pre-push"

  git -C "${workspace_dir}" config --local extensions.worktreeConfig true
  git config --file "${config_worktree}" core.hooksPath "${hooks_root}"
}

buddyswitch_workspace_prepare_execution_worktree() {
  buddyswitch_workspace_init_defaults
  buddyswitch_workspace_ensure_execution_worktree
  buddyswitch_workspace_ensure_state_skeleton
  buddyswitch_workspace_install_runtime_agents
  buddyswitch_workspace_install_runtime_skills
  buddyswitch_workspace_install_guardrail_hooks
}
