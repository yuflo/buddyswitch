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
  local repo_root default_template

  repo_root="$(buddyswitch_workspace_repo_root)"
  default_template="${repo_root}/tools/launcher/assets/runtime-AGENTS.md"

  export BUDDYSWITCH_WORKSPACE_DIR="${BUDDYSWITCH_WORKSPACE_DIR:-${BUDDYSWITCH_SHARED_ROOT}/workspace}"
  export BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE="${BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE:-${default_template}}"
}

buddyswitch_workspace_canonical_path() {
  python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve(strict=False))' "$1"
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

buddyswitch_workspace_is_valid_execution_worktree() {
  local workspace_dir repo_common workspace_common

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  repo_common="$(buddyswitch_workspace_repo_common_dir)"

  git -C "${workspace_dir}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  workspace_common="$(git -C "${workspace_dir}" rev-parse --git-common-dir 2>/dev/null || true)"
  [[ "${workspace_common}" == "${repo_common}" ]]
}

buddyswitch_workspace_runtime_output_paths() {
  cat <<'EOF'
buddyswitch/objects/tracks
buddyswitch/objects/tasks
buddyswitch/objects/artifacts
buddyswitch/content/runs
runs/raw
projects/app/.runtime
EOF
}

buddyswitch_workspace_projected_state_paths() {
  cat <<'EOF'
buddyswitch/objects/tracks
buddyswitch/objects/tasks
buddyswitch/objects/artifacts
buddyswitch/content/runs
EOF
}

buddyswitch_workspace_local_runtime_paths() {
  cat <<'EOF'
runs/raw
projects/app/.runtime
EOF
}

buddyswitch_workspace_is_instance_mode() {
  [[ -n "${BUDDYSWITCH_INSTANCE_ID:-}" ]]
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
    rm -rf "${target_path}"
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
  if ! rm -rf "${workspace_dir}"; then
    if [[ "${cleanup_staging}" -eq 1 ]]; then
      buddyswitch_workspace_restore_runtime_outputs "${staging_root}"
      rm -rf "${staging_root}"
    fi
    return 1
  fi
  git -C "${repo_root}" worktree prune >/dev/null 2>&1 || true
  if ! git -C "${repo_root}" worktree add --detach "${workspace_dir}" HEAD >/dev/null; then
    if [[ "${cleanup_staging}" -eq 1 ]]; then
      buddyswitch_workspace_restore_runtime_outputs "${staging_root}"
      rm -rf "${staging_root}"
    fi
    return 1
  fi

  if [[ "${cleanup_staging}" -eq 1 ]]; then
    buddyswitch_workspace_restore_runtime_outputs "${staging_root}"
    rm -rf "${staging_root}"
  fi
}

buddyswitch_workspace_ensure_execution_worktree() {
  if buddyswitch_workspace_is_valid_execution_worktree; then
    return 0
  fi

  buddyswitch_workspace_force_rebuild_execution_worktree
}

buddyswitch_workspace_install_runtime_agents() {
  local workspace_dir template_path

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  template_path="${BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE}"
  if [[ ! -f "${template_path}" ]]; then
    echo "Runtime AGENTS template not found: ${template_path}" >&2
    return 1
  fi

  cp "${template_path}" "${workspace_dir}/AGENTS.md"
}

buddyswitch_workspace_install_local_excludes() {
  local workspace_dir exclude_path
  local marker

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  exclude_path="$(git -C "${workspace_dir}" rev-parse --git-path info/exclude)"
  marker="# BuddySwitch runtime-only excludes"

  mkdir -p "$(dirname "${exclude_path}")"
  touch "${exclude_path}"

  if ! grep -Fxq "${marker}" "${exclude_path}"; then
    printf '\n%s\n' "${marker}" >> "${exclude_path}"
  fi

  while IFS= read -r pattern; do
    if ! grep -Fxq "${pattern}" "${exclude_path}"; then
      printf '%s\n' "${pattern}" >> "${exclude_path}"
    fi
  done <<'EOF'
buddyswitch/content/runs/**
buddyswitch/objects/tracks/**
buddyswitch/objects/tasks/**
buddyswitch/objects/artifacts/**
runs/raw/**
projects/app/.runtime/**
EOF
}

buddyswitch_workspace_ensure_state_skeleton() {
  local workspace_dir relative_dir

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  if buddyswitch_workspace_is_instance_mode; then
    while IFS= read -r relative_dir; do
      mkdir -p "${workspace_dir}/${relative_dir}"
    done < <(buddyswitch_workspace_local_runtime_paths)
    buddyswitch_workspace_install_state_projections
    return
  fi

  while IFS= read -r relative_dir; do
    mkdir -p "${workspace_dir}/${relative_dir}"
  done <<'EOF'
runs/raw
projects/app/.runtime
buddyswitch/objects/tracks
buddyswitch/objects/tasks
buddyswitch/objects/artifacts
buddyswitch/content/runs
EOF
}

buddyswitch_workspace_install_state_projections() {
  local workspace_dir state_root relative_dir state_dir projected_dir

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  state_root="${BUDDYSWITCH_SHARED_ROOT}/state"
  while IFS= read -r relative_dir; do
    state_dir="${state_root}/${relative_dir}"
    projected_dir="${workspace_dir}/${relative_dir}"
    mkdir -p "${state_dir}" "$(dirname "${projected_dir}")"
    rm -rf "${projected_dir}"
    ln -s "${state_dir}" "${projected_dir}"
  done < <(buddyswitch_workspace_projected_state_paths)
}

buddyswitch_workspace_migrate_legacy_state_if_needed() {
  python3 - "${BUDDYSWITCH_SHARED_ROOT}" <<'PY'
import json
import shutil
import sys
from pathlib import Path

shared_root = Path(sys.argv[1])
legacy_root = shared_root / "workspace"
state_root = shared_root / "state"
durable_dirs = (
    Path("buddyswitch/objects/tracks"),
    Path("buddyswitch/objects/tasks"),
    Path("buddyswitch/objects/artifacts"),
    Path("buddyswitch/content/runs"),
)
ignored_names = {".DS_Store", ".gitkeep"}


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink(missing_ok=True)


def prune_reservations(root: Path) -> None:
    shutil.rmtree(root / "buddyswitch" / "content" / "runs" / "reserved", ignore_errors=True)


def durable_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    for relative_dir in durable_dirs:
        directory = root / relative_dir
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_dir() or path.name in ignored_names:
                continue
            rows.append(path)
    return rows


def validate_json(files: list[Path], label: str) -> None:
    for path in files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Migration blocked: invalid JSON in {label} durable state: {path}: {exc}", file=sys.stderr)
            raise SystemExit(3)


prune_reservations(legacy_root)
prune_reservations(state_root)
legacy_files = durable_files(legacy_root)
state_files = durable_files(state_root)
validate_json(legacy_files, "legacy workspace")
validate_json(state_files, "shared")

if legacy_files and state_files:
    print(
        "Migration blocked: legacy workspace durable state and shared state both contain data. "
        "Run buddyswitch-codex reset --yes or clean up one state root before starting product mode.",
        file=sys.stderr,
    )
    raise SystemExit(3)

if legacy_files:
    for relative_dir in durable_dirs:
        source = legacy_root / relative_dir
        target = state_root / relative_dir
        if not source.exists() and not source.is_symlink():
            continue
        if target.exists() or target.is_symlink():
            remove_path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))

for relative_dir in durable_dirs:
    (state_root / relative_dir).mkdir(parents=True, exist_ok=True)
PY
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
  buddyswitch_workspace_install_local_excludes
  buddyswitch_workspace_install_guardrail_hooks
}

buddyswitch_workspace_sync_execution_worktree() {
  buddyswitch_workspace_init_defaults
  buddyswitch_workspace_force_rebuild_execution_worktree
  buddyswitch_workspace_ensure_state_skeleton
  buddyswitch_workspace_install_runtime_agents
  buddyswitch_workspace_install_local_excludes
  buddyswitch_workspace_install_guardrail_hooks
}
