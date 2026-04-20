#!/usr/bin/env python3
"""Storage-aware BuddySwitch cleanup backend."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    from env_manifest import ManifestError, load_manifest as _load_manifest_full
except ModuleNotFoundError:  # pragma: no cover - exercised in shell integration fixture
    class ManifestError(ValueError):
        """Manifest validation error."""

    _load_manifest_full = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
CONFIRM_PHRASE = "DELETE_BUDDYSWITCH_DATA"
CATEGORY_ORDER = (
    "artifact_objects",
    "task_objects",
    "run_content",
    "run_raw",
    "track_objects",
    "project_runtime",
)


def _strip_toml_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    output: list[str] = []
    for char in line:
        if escaped:
            output.append(char)
            escaped = False
            continue
        if char == "\\" and in_double:
            output.append(char)
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            output.append(char)
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            output.append(char)
            continue
        if char == "#" and not in_single and not in_double:
            break
        output.append(char)
    return "".join(output)


def _strip_toml_quotes(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1].strip()
    return value


def _load_valid_buddies_minimal(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        raise ManifestError(f"Manifest not found: {manifest_path}")

    buddy_ids: set[str] = set()
    current_section: str | None = None
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = _strip_toml_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("[[") and line.endswith("]]"):
            current_section = line[2:-2].strip()
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = None
            continue
        if current_section != "buddies" or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip() != "id":
            continue
        buddy_id = _strip_toml_quotes(raw_value.strip())
        if buddy_id:
            buddy_ids.add(buddy_id)
    if not buddy_ids:
        raise ManifestError("manifest must define at least one [[buddies]] id")
    return buddy_ids


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def repo_path(root: Path, raw_path: str) -> Path | None:
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        return None
    return root / path


def iter_files(root: Path, relative_dir: str) -> list[Path]:
    directory = root / relative_dir
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.rglob("*") if (path.is_file() or path.is_symlink()) and path.name != ".gitkeep")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def load_valid_buddies(manifest_path: Path) -> set[str]:
    if _load_manifest_full is not None:
        try:
            data = _load_manifest_full(manifest_path)
            ids = {
                buddy["id"]
                for buddy in data.get("buddies", [])
                if isinstance(buddy, dict) and isinstance(buddy.get("id"), str) and buddy["id"].strip()
            }
            if ids:
                return ids
        except (ManifestError, OSError, ValueError, json.JSONDecodeError):
            pass
    return _load_valid_buddies_minimal(manifest_path)


def new_plan(scope: str, *, buddy: str | None = None) -> dict[str, Any]:
    counts = {key: 0 for key in CATEGORY_ORDER}
    return {
        "scope": scope,
        "buddy": buddy,
        "delete_paths": [],
        "artifact_object_ids": [],
        "task_object_ids": [],
        "run_ids": [],
        "warnings": [],
        "counts_by_category": counts,
        "artifact_records": [],
        "task_records": [],
        "run_records": [],
        "direct_delete_paths": [],
    }


def add_warning(plan: dict[str, Any], message: str) -> None:
    if message not in plan["warnings"]:
        plan["warnings"].append(message)


def add_path(plan: dict[str, Any], path: Path, category: str) -> None:
    relative = rel(Path(plan["repo_root"]), path)
    if relative not in plan["_path_categories"]:
        plan["_path_categories"][relative] = category
        plan["delete_paths"].append(relative)
        plan["counts_by_category"][category] += 1


def discover_artifact_objects(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in iter_files(root, "buddyswitch/objects/artifacts"):
        relative = rel(root, path)
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "reason": f"invalid artifact object JSON: {exc}"})
            continue

        artifact_id = payload.get("id")
        producer_buddy = payload.get("buddy")
        if not isinstance(artifact_id, str) or not artifact_id:
            invalid.append({"path": relative, "reason": "artifact object is missing id"})
            continue
        if not isinstance(producer_buddy, str) or not producer_buddy:
            invalid.append({"path": relative, "reason": f"artifact '{artifact_id}' is missing buddy"})
            continue

        record = {
            "id": artifact_id,
            "producer_buddy": producer_buddy,
            "task_id": payload.get("task_id"),
            "object_path": relative,
        }
        valid.append(record)
    return valid, invalid


def discover_task_objects(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in iter_files(root, "buddyswitch/objects/tasks"):
        relative = rel(root, path)
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "reason": f"invalid task object JSON: {exc}"})
            continue

        task_id = payload.get("id")
        task_buddy = payload.get("buddy")
        if not isinstance(task_id, str) or not task_id:
            invalid.append({"path": relative, "reason": "task object is missing id"})
            continue
        if not isinstance(task_buddy, str) or not task_buddy:
            invalid.append({"path": relative, "reason": f"task '{task_id}' is missing buddy"})
            continue

        valid.append(
            {
                "id": task_id,
                "buddy": task_buddy,
                "track_id": payload.get("track_id"),
                "object_path": relative,
            }
        )
    return valid, invalid


def discover_run_content(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in iter_files(root, "buddyswitch/content/runs"):
        relative = rel(root, path)
        run_id = path.stem
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "run_id": run_id, "reason": f"invalid run content JSON: {exc}"})
            continue

        switch = payload.get("switch")
        if not isinstance(switch, dict):
            invalid.append({"path": relative, "run_id": run_id, "reason": "run content is missing switch object"})
            continue
        buddy = switch.get("buddy")
        if not isinstance(buddy, str) or not buddy:
            invalid.append({"path": relative, "run_id": run_id, "reason": "run content is missing switch.buddy"})
            continue
        valid.append({"path": relative, "run_id": run_id, "buddy": buddy})
    return valid, invalid


def add_dir_files(plan: dict[str, Any], relative_dir: str, category: str) -> None:
    root = Path(plan["repo_root"])
    for path in iter_files(root, relative_dir):
        add_path(plan, path, category)
        plan["direct_delete_paths"].append(rel(root, path))


def add_indexed_artifact(plan: dict[str, Any], record: dict[str, Any]) -> None:
    root = Path(plan["repo_root"])
    if record["id"] not in plan["artifact_object_ids"]:
        plan["artifact_object_ids"].append(record["id"])
        plan["artifact_records"].append(record)

    object_path = root / record["object_path"]
    add_path(plan, object_path, "artifact_objects")


def add_indexed_task(plan: dict[str, Any], record: dict[str, Any]) -> None:
    root = Path(plan["repo_root"])
    if record["id"] not in plan["task_object_ids"]:
        plan["task_object_ids"].append(record["id"])
        plan["task_records"].append(record)

    object_path = root / record["object_path"]
    add_path(plan, object_path, "task_objects")


def add_run_content(plan: dict[str, Any], record: dict[str, Any]) -> None:
    root = Path(plan["repo_root"])
    if record["run_id"] not in plan["run_ids"]:
        plan["run_ids"].append(record["run_id"])
        plan["run_records"].append(record)
    resolved = repo_path(root, record["path"])
    if resolved is not None:
        add_path(plan, resolved, "run_content")
        plan["direct_delete_paths"].append(record["path"])


def delete_relative_path(root: Path, relative_path: str) -> None:
    resolved = repo_path(root, relative_path)
    if resolved is None or not resolved.exists():
        return
    if resolved.is_dir() and not resolved.is_symlink():
        shutil.rmtree(resolved)
        return
    resolved.unlink()


def detach_task_from_track(root: Path, track_id: str | None, task_id: str) -> None:
    if not isinstance(track_id, str) or not track_id:
        return
    track_path = root / "buddyswitch" / "objects" / "tracks" / f"{track_id}.json"
    if not track_path.exists():
        return
    try:
        payload = read_json(track_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return
    task_ids = payload.get("task_ids")
    if not isinstance(task_ids, list):
        return
    filtered = [item for item in task_ids if item != task_id]
    if filtered == task_ids:
        return
    payload["task_ids"] = filtered
    write_json(track_path, payload)


def detach_artifact_from_task(root: Path, task_id: str | None, artifact_id: str) -> None:
    if not isinstance(task_id, str) or not task_id:
        return
    task_path = root / "buddyswitch" / "objects" / "tasks" / f"{task_id}.json"
    if not task_path.exists():
        return
    try:
        payload = read_json(task_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return
    artifact_ids = payload.get("artifact_ids")
    if not isinstance(artifact_ids, list):
        return
    filtered = [item for item in artifact_ids if item != artifact_id]
    if filtered == artifact_ids:
        return
    payload["artifact_ids"] = filtered

    artifact_slots = payload.get("artifact_slots")
    artifact_path = root / "buddyswitch" / "objects" / "artifacts" / f"{artifact_id}.json"
    slot: str | None = None
    if isinstance(artifact_slots, dict) and artifact_path.exists():
        try:
            artifact_payload = read_json(artifact_path)
        except (OSError, ValueError, json.JSONDecodeError):
            artifact_payload = None
        if isinstance(artifact_payload, dict):
            artifact_slot = artifact_payload.get("slot")
            if isinstance(artifact_slot, str) and artifact_slot:
                slot = artifact_slot

    if isinstance(artifact_slots, dict) and isinstance(slot, str) and slot:
        slot_state = artifact_slots.get(slot)
        deleting_current = isinstance(slot_state, dict) and slot_state.get("current_artifact_id") == artifact_id
        if deleting_current:
            candidates: list[dict[str, Any]] = []
            for candidate_id in filtered:
                candidate_path = root / "buddyswitch" / "objects" / "artifacts" / f"{candidate_id}.json"
                if not candidate_path.exists():
                    continue
                try:
                    candidate = read_json(candidate_path)
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(candidate, dict):
                    continue
                candidate_slot = candidate.get("slot")
                if not isinstance(candidate_slot, str) or candidate_slot != slot:
                    continue
                candidates.append(candidate)
            if candidates:
                candidates.sort(
                    key=lambda row: (
                        row.get("revision", 0) if isinstance(row.get("revision"), int) else 0,
                        row.get("updated_at", "") if isinstance(row.get("updated_at"), str) else "",
                        row.get("id", "") if isinstance(row.get("id"), str) else "",
                    ),
                    reverse=True,
                )
                promoted = candidates[0]
                revision_count = slot_state.get("revision_count", promoted.get("revision")) if isinstance(slot_state, dict) else promoted.get("revision")
                if not isinstance(revision_count, int) or revision_count < promoted.get("revision", 0):
                    revision_count = promoted.get("revision", 0)
                for candidate in candidates:
                    candidate["is_current"] = candidate.get("id") == promoted.get("id")
                    write_json(root / "buddyswitch" / "objects" / "artifacts" / f"{candidate['id']}.json", candidate)
                artifact_slots[slot] = {
                    "current_artifact_id": promoted["id"],
                    "revision_count": revision_count,
                }
            else:
                artifact_slots.pop(slot, None)
    write_json(task_path, payload)


def ensure_required_skeleton(root: Path) -> None:
    for relative_dir in (
        "runs/raw",
        "projects/app/.runtime",
        "buddyswitch/objects/tracks",
        "buddyswitch/objects/tasks",
        "buddyswitch/objects/artifacts",
        "buddyswitch/content/runs",
    ):
        directory = root / relative_dir
        directory.mkdir(parents=True, exist_ok=True)


def build_cleanup_plan(
    *,
    scope: str,
    buddy: str | None,
    repo_root: Path = ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    valid_buddies = load_valid_buddies(manifest_path)
    if scope == "agent" and (buddy is None or buddy not in valid_buddies):
        raise ValueError(f"Invalid buddy '{buddy}'. Check buddyswitch/manifest.toml")
    if scope == "project" and buddy is not None:
        raise ValueError("project cleanup does not accept buddy")

    plan = new_plan(scope, buddy=buddy)
    plan["repo_root"] = str(repo_root)
    plan["_path_categories"] = {}

    artifact_objects, invalid_artifact_objects = discover_artifact_objects(repo_root)
    task_objects, invalid_task_objects = discover_task_objects(repo_root)
    run_content, invalid_run_content = discover_run_content(repo_root)

    if scope == "agent":
        add_dir_files(plan, f"runs/raw/{buddy}", "run_raw")
        for record in artifact_objects:
            if record["producer_buddy"] == buddy:
                add_indexed_artifact(plan, record)
        for record in task_objects:
            if record["buddy"] == buddy:
                add_indexed_task(plan, record)
        for record in run_content:
            if record["buddy"] == buddy:
                add_run_content(plan, record)
        for item in invalid_run_content:
            add_warning(
                plan,
                f"{item['path']} cannot be safely attributed to buddy '{buddy}' and will be skipped in scoped cleanup ({item['reason']}).",
            )
        for item in invalid_artifact_objects:
            add_warning(
                plan,
                f"{item['path']} cannot be safely attributed to buddy '{buddy}' and will be skipped in scoped cleanup ({item['reason']}).",
            )
        for item in invalid_task_objects:
            add_warning(
                plan,
                f"{item['path']} cannot be safely attributed to buddy '{buddy}' and will be skipped in scoped cleanup ({item['reason']}).",
            )

    elif scope == "all-agents":
        add_dir_files(plan, "runs/raw", "run_raw")
        add_dir_files(plan, "buddyswitch/objects/tracks", "track_objects")
        for record in artifact_objects:
            add_indexed_artifact(plan, record)
        for record in task_objects:
            add_indexed_task(plan, record)
        for record in run_content:
            add_run_content(plan, record)
        for item in invalid_artifact_objects:
            add_warning(plan, f"Deleting malformed artifact object during all-agents cleanup: {item['path']} ({item['reason']}).")
            add_path(plan, repo_root / item["path"], "artifact_objects")
            plan["direct_delete_paths"].append(item["path"])
        for item in invalid_run_content:
            add_warning(plan, f"Deleting malformed run content during all-agents cleanup: {item['path']} ({item['reason']}).")
            add_run_content(plan, {"path": item["path"], "run_id": item["run_id"], "buddy": None})
        for item in invalid_task_objects:
            add_warning(plan, f"Deleting malformed task object during all-agents cleanup: {item['path']} ({item['reason']}).")
            add_path(plan, repo_root / item["path"], "task_objects")
            plan["direct_delete_paths"].append(item["path"])

    elif scope == "project":
        add_dir_files(plan, "projects/app/.runtime", "project_runtime")

    elif scope == "all-storage":
        add_dir_files(plan, "runs/raw", "run_raw")
        add_dir_files(plan, "projects/app/.runtime", "project_runtime")
        add_dir_files(plan, "buddyswitch/objects/tracks", "track_objects")
        add_dir_files(plan, "buddyswitch/objects/tasks", "task_objects")
        add_dir_files(plan, "buddyswitch/objects/artifacts", "artifact_objects")
        add_dir_files(plan, "buddyswitch/content/runs", "run_content")
        for record in artifact_objects:
            if record["id"] not in plan["artifact_object_ids"]:
                plan["artifact_object_ids"].append(record["id"])
                plan["artifact_records"].append(record)
        for record in task_objects:
            if record["id"] not in plan["task_object_ids"]:
                plan["task_object_ids"].append(record["id"])
                plan["task_records"].append(record)
        for record in run_content:
            if record["run_id"] not in plan["run_ids"]:
                plan["run_ids"].append(record["run_id"])
                plan["run_records"].append(record)
        for item in invalid_run_content:
            if item["run_id"] not in plan["run_ids"]:
                plan["run_ids"].append(item["run_id"])
        for item in invalid_artifact_objects:
            add_warning(plan, f"All-storage cleanup will delete malformed artifact object: {item['path']} ({item['reason']}).")
        for item in invalid_task_objects:
            add_warning(plan, f"All-storage cleanup will delete malformed task object: {item['path']} ({item['reason']}).")
        for item in invalid_run_content:
            add_warning(plan, f"All-storage cleanup will delete malformed run content: {item['path']} ({item['reason']}).")
    else:
        raise ValueError(f"Unsupported cleanup scope: {scope}")

    plan["delete_paths"].sort()
    plan["artifact_object_ids"].sort()
    plan["task_object_ids"].sort()
    plan["run_ids"].sort()
    plan["direct_delete_paths"] = sorted(set(plan["direct_delete_paths"]))
    plan["warnings"].sort()
    plan.pop("_path_categories", None)
    return plan


def execute_cleanup_plan(plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(plan["repo_root"])
    deleted_paths: list[str] = []

    if plan["scope"] == "agent":
        for record in plan["artifact_records"]:
            detach_artifact_from_task(root, record.get("task_id"), record["id"])
        for record in plan["task_records"]:
            detach_task_from_track(root, record.get("track_id"), record["id"])

    indexed_artifact_paths = set()
    for record in plan["artifact_records"]:
        indexed_artifact_paths.add(record["object_path"])

    indexed_task_paths = set()
    for record in plan["task_records"]:
        indexed_task_paths.add(record["object_path"])

    for relative_path in sorted(indexed_artifact_paths):
        delete_relative_path(root, relative_path)
        deleted_paths.append(relative_path)

    for relative_path in sorted(indexed_task_paths):
        delete_relative_path(root, relative_path)
        deleted_paths.append(relative_path)

    for relative_path in plan["direct_delete_paths"]:
        if relative_path in indexed_artifact_paths or relative_path in indexed_task_paths:
            continue
        delete_relative_path(root, relative_path)
        deleted_paths.append(relative_path)

    ensure_required_skeleton(root)
    return {
        "ok": True,
        "scope": plan["scope"],
        "buddy": plan["buddy"],
        "deleted_paths": deleted_paths,
        "deleted_count": len(deleted_paths),
        "artifact_object_ids": plan["artifact_object_ids"],
        "task_object_ids": plan["task_object_ids"],
        "run_ids": plan["run_ids"],
        "warnings": plan["warnings"],
    }


def print_text_plan(plan: dict[str, Any]) -> None:
    if plan["scope"] == "agent":
        target = f"--agent {plan['buddy']}"
    elif plan["scope"] == "all-agents":
        target = "--all-agents"
    elif plan["scope"] == "project":
        target = "--project app"
    else:
        target = "--all-storage"

    print("BuddySwitch cleanup plan")
    print(f"Repo root: {plan['repo_root']}")
    print(f"Target: {target}")
    print()
    print("Counts by category:")
    for key in CATEGORY_ORDER:
        count = plan["counts_by_category"][key]
        if count:
            print(f"  - {key}: {count}")
    if not any(plan["counts_by_category"].values()):
        print("  - no files matched")
    print()
    print(f"Delete candidates: {len(plan['delete_paths'])}")
    for path in plan["delete_paths"]:
        print(f"  - {path}")
    if plan["warnings"]:
        print()
        print("Warnings:")
        for warning in plan["warnings"]:
            print(f"  - {warning}")


def confirm_execute(force: bool) -> None:
    if force:
        return
    if not sys.stdin.isatty():
        raise ValueError("--execute requires interactive confirmation, or use --force")
    print(f"Type '{CONFIRM_PHRASE}' to confirm deletion:")
    answer = input().strip()
    if answer != CONFIRM_PHRASE:
        raise ValueError("Confirmation phrase mismatch. Aborted.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BuddySwitch cleanup utility (manual use only)")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--agent")
    target.add_argument("--all-agents", action="store_true")
    target.add_argument("--project")
    target.add_argument("--all-storage", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print cleanup plan/result as JSON.")
    return parser


def resolve_scope(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.agent:
        return "agent", args.agent
    if args.all_agents:
        return "all-agents", None
    if args.project:
        if args.project != "app":
            raise ValueError(f"Invalid project '{args.project}'. Only 'app' is supported for --project")
        return "project", None
    if args.all_storage:
        return "all-storage", None
    raise ValueError("No cleanup target provided")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.force and not args.execute:
        print("ERROR: --force can only be used with --execute", file=sys.stderr)
        return 1

    try:
        scope, buddy = resolve_scope(args)
        plan = build_cleanup_plan(scope=scope, buddy=buddy, repo_root=ROOT, manifest_path=args.manifest)
        if not args.json:
            print_text_plan(plan)

        if not args.execute:
            if args.json:
                print(json.dumps(plan, ensure_ascii=True, indent=2))
            else:
                print()
                print("Dry-run mode: no files were deleted.")
            return 0

        confirm_execute(args.force)
        result = execute_cleanup_plan(plan)
        if args.json:
            print(json.dumps({"plan": plan, "result": result}, ensure_ascii=True, indent=2))
        else:
            print()
            print(f"Cleanup completed. Deleted {result['deleted_count']} file(s).")
        return 0
    except (OSError, ValueError, ManifestError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
