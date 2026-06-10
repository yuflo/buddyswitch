#!/usr/bin/env python3
"""Phase 8 boundary tests for env layer workspace and state access."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - python<3.11 fallback
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

CODEX_CONFIG = ROOT / "tools" / "launcher" / "codex_config.py"
MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
PERMISSION_PROFILE = "buddyswitch-runtime"


class EnvLayerBoundaryTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _DOMAIN_CROSS_OBJECT_ALLOWLIST = {
        "publication",
        "artifact_visibility",
        "tasks",
        "source_refs",
        "actor_private_workspace",
    }
    _SHIPPED_TOOLS = {"task", "track", "artifact", "context", "evidence", "message", "search"}

    def _legacy_store_import_violations(self, roots: list[Path]) -> list[str]:
        violations: list[str] = []
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*.py")):
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
                rel = path.relative_to(ROOT).as_posix()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name == "env_legacy_store":
                                violations.append(f"{rel}:{node.lineno}: import env_legacy_store")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module == "env_legacy_store":
                            violations.append(f"{rel}:{node.lineno}: from env_legacy_store import ...")
        return violations

    def test_tool_package_cross_imports_are_forbidden(self) -> None:
        tool_root = ROOT / "scripts" / "env" / "tools"
        violations: list[str] = []
        for tool in sorted(self._SHIPPED_TOOLS):
            package_dir = tool_root / tool
            if not package_dir.is_dir():
                violations.append(f"missing package: {package_dir.relative_to(ROOT)}")
                continue
            for path in sorted(package_dir.rglob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                rel = path.relative_to(ROOT).as_posix()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("env.tools."):
                                parts = alias.name.split(".")
                                if len(parts) >= 3:
                                    target = parts[2]
                                    if target in self._SHIPPED_TOOLS and target != tool:
                                        violations.append(f"{rel}:{node.lineno}: import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if module == "env.tools":
                            for alias in node.names:
                                if alias.name in self._SHIPPED_TOOLS and alias.name != tool:
                                    violations.append(f"{rel}:{node.lineno}: from env.tools import {alias.name}")
                        elif module.startswith("env.tools."):
                            parts = module.split(".")
                            if len(parts) >= 3:
                                target = parts[2]
                                if target in self._SHIPPED_TOOLS and target != tool:
                                    violations.append(f"{rel}:{node.lineno}: from {module} import ...")

        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_legacy_env_services_tool_entrypoints_are_removed(self) -> None:
        runtime_roots = [ROOT / "scripts"]
        import_violations: list[str] = []
        for root in runtime_roots:
            for path in sorted(root.rglob("*.py")):
                rel = path.relative_to(ROOT).as_posix()
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("env.services"):
                                import_violations.append(f"{rel}:{node.lineno}: import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if module.startswith("env.services"):
                            import_violations.append(f"{rel}:{node.lineno}: from {module} import ...")
        self.assertEqual(import_violations, [], msg="\n".join(import_violations))

        service_dir = ROOT / "scripts" / "env" / "services"
        self.assertFalse(service_dir.exists(), msg=str(service_dir))

    def _patch_config(
        self,
        *,
        temp_root: Path,
        role: str,
        shared_root: Path,
    ) -> str:
        instance_root = shared_root / "instances" / f"act-{role}-boundary"
        workspace_dir = instance_root / "workspace"
        project_workspace_dir = shared_root / "project" / "workspace"
        config_path = temp_root / f"{role}-config.toml"
        completed = subprocess.run(
            [
                "python3",
                str(CODEX_CONFIG),
                "--config",
                str(config_path),
                "--repo-root",
                str(ROOT),
                "--shared-root",
                str(shared_root),
                "--source-codex-home",
                str(shared_root / "source-codex-home"),
                "--role",
                role,
                "--instance-root",
                str(instance_root),
                "--workspace-dir",
                str(workspace_dir),
                "--project-workspace-dir",
                str(project_workspace_dir),
                "--home",
                str(instance_root / "home"),
                "--codex-home",
                str(instance_root / "codex-home"),
                "--xdg-config-home",
                str(instance_root / "xdg-config"),
                "--temp-root",
                str(instance_root / "tmp"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        return config_path.read_text(encoding="utf-8")

    def _filesystem_entries(self, config_text: str) -> dict[str, object]:
        parsed = tomllib.loads(config_text)
        return parsed["permissions"][PERMISSION_PROFILE]["filesystem"]

    def _writable_paths(self, config_text: str) -> set[str]:
        filesystem = self._filesystem_entries(config_text)
        return {key for key, value in filesystem.items() if value == "write"}

    def _instance_json(self) -> Path:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-boundary")
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": "dev",
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch_dev_task_capture(self, args: dict[str, object]) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-boundary")
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-env-layer-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "actor_id": actor_id,
                    "active_role": "dev",
                    "tool": "task",
                    "action": "capture",
                    "args": args,
                },
                "deadline_ms": 35000,
            },
            instance_json_path=self._instance_json(),
            manifest_path=MANIFEST,
        )
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            payload = envelope.get("result")
            self.assertIsInstance(payload, dict, msg=envelope)
            assert isinstance(payload, dict)
            return payload
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        payload = {
            "ok": False,
            "error": {
                "code": error.get("code"),
                "message": error.get("message"),
                "retriable": error.get("retriable"),
            },
        }
        for key, value in envelope.items():
            if key in {"protocol", "request_id", "ok", "error"}:
                continue
            payload[key] = value
        return payload

    def test_dev_source_root_is_writable_and_non_dev_source_root_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            dev_instance_root = shared_root / "instances" / "act-dev-boundary"
            pm_instance_root = shared_root / "instances" / "act-pm-boundary"
            project_workspace_dir = shared_root / "project" / "workspace"
            project_source_root = project_workspace_dir / "projects" / "app"

            dev_writable = self._writable_paths(
                self._patch_config(temp_root=temp_root, role="dev", shared_root=shared_root)
            )
            pm_writable = self._writable_paths(
                self._patch_config(temp_root=temp_root, role="pm", shared_root=shared_root)
            )

            self.assertIn(str(project_source_root.resolve(strict=False)), dev_writable)
            self.assertNotIn(str(project_source_root.resolve(strict=False)), pm_writable)
            self.assertIn(str((dev_instance_root / "workspace" / "private").resolve(strict=False)), dev_writable)
            self.assertIn(str((dev_instance_root / "tmp").resolve(strict=False)), dev_writable)
            self.assertIn(str((pm_instance_root / "workspace" / "private").resolve(strict=False)), pm_writable)
            self.assertIn(str((pm_instance_root / "tmp").resolve(strict=False)), pm_writable)
            self.assertNotIn(str(project_workspace_dir.resolve(strict=False)), dev_writable)
            self.assertNotIn(str(project_workspace_dir.resolve(strict=False)), pm_writable)
            self.assertNotIn(str((shared_root / "state").resolve(strict=False)), dev_writable)
            self.assertNotIn(str(shared_root.resolve(strict=False)), dev_writable)

    def test_permission_profile_does_not_grant_pm_project_or_design_sandbox_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            instance_root = shared_root / "instances" / "act-pm-boundary"
            workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"

            config_text = self._patch_config(temp_root=temp_root, role="pm", shared_root=shared_root)
            writable_paths = self._writable_paths(config_text)
            project_source_root = project_workspace_dir / "projects" / "app"
            self.assertIn(str((workspace_dir / "private").resolve(strict=False)), writable_paths)
            self.assertIn(str((instance_root / "tmp").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
            self.assertNotIn(str(project_source_root.resolve(strict=False)), writable_paths)
            self.assertNotIn(str(workspace_dir.resolve(strict=False)), writable_paths)
            self.assertNotIn(str((workspace_dir / ".sandbox").resolve(strict=False)), writable_paths)
            self.assertNotIn(str((workspace_dir / ".sandbox" / "design").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(shared_root.resolve(strict=False)), writable_paths)
            self.assertNotIn(str((shared_root / "state").resolve(strict=False)), writable_paths)
            self.assertNotIn("/tmp", writable_paths)
            self.assertNotIn(str(Path(tempfile.gettempdir()).resolve(strict=False)), writable_paths)

    def test_permission_profile_keeps_dev_source_root_write_and_runtime_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shared_root = temp_root / "shared"
            project_workspace_dir = shared_root / "project" / "workspace"
            project_source_root = project_workspace_dir / "projects" / "app"
            runtime_workspace_dir = shared_root / "instances" / "act-dev-boundary" / "workspace"
            config_text = self._patch_config(temp_root=temp_root, role="dev", shared_root=shared_root)
            writable_paths = self._writable_paths(config_text)
            filesystem = self._filesystem_entries(config_text)
            self.assertIn(str(project_source_root.resolve(strict=False)), writable_paths)
            self.assertIn(str((runtime_workspace_dir / "private").resolve(strict=False)), writable_paths)
            self.assertIn(str((shared_root / "instances" / "act-dev-boundary" / "tmp").resolve(strict=False)), writable_paths)
            self.assertNotIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
            self.assertNotIn(":project_roots", filesystem)
            for key, value in filesystem.items():
                self.assertIsInstance(key, str)
                self.assertIsInstance(value, str, msg=key)
                self.assertNotIn("*", key)
                if key != "/":
                    self.assertTrue(Path(key).is_absolute(), msg=key)
            self.assertEqual(filesystem[str(runtime_workspace_dir.resolve(strict=False))], "read")
            self.assertEqual(filesystem[str((shared_root / "state").resolve(strict=False))], "none")
            self.assertNotIn(
                str((runtime_workspace_dir / "buddyswitch" / "objects").resolve(strict=False)),
                filesystem,
            )
            self.assertNotIn("/tmp", writable_paths)
            self.assertNotIn(str(Path(tempfile.gettempdir()).resolve(strict=False)), writable_paths)

    def test_env_tool_rejects_payload_paths_instead_of_bypassing_project_or_raw_state_boundaries(self) -> None:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-boundary")
        project_probe = self._runtime_path("projects/app/env-tool-bypass.txt")
        raw_state_path = f"instances/{actor_id}/taskbox/dev/tasks/env-tool-bypass.json"
        raw_probe = self._runtime_path(raw_state_path)

        response = self._dispatch_dev_task_capture(
            {
                "reason": "Boundary test.",
                "evidence": "Payload includes forbidden path fields.",
                "task": {
                    "title": "Boundary bypass attempt",
                    "body": "should reject before write",
                    "project_path": "projects/app/env-tool-bypass.txt",
                    "raw_state_path": raw_state_path,
                },
            }
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "request-payload")
        self.assertFalse(project_probe.exists())
        self.assertFalse(raw_probe.exists())

    def test_env_tool_services_do_not_write_files_directly(self) -> None:
        completed = subprocess.run(
            [
                "rg",
                "-n",
                r"\.mkdir\(|\.write_text\(|\.write_bytes\(|\.unlink\(|os\.replace\(|NamedTemporaryFile\(",
                "scripts/env/tools",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_object_repo_sibling_imports_are_restricted_to_runtime_files(self) -> None:
        repo_files = sorted(path for path in ROOT.glob("scripts/**/repos/*.py") if path.name != "__init__.py")
        if not repo_files:
            self.skipTest("No scripts/**/repos/*.py modules exist in this migration stage; repo boundary scan deferred.")
        violations: list[str] = []
        for path in repo_files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.level <= 0:
                    continue
                if node.module is None:
                    imported_roots = {alias.name.split(".", 1)[0] for alias in node.names}
                    if imported_roots != {"runtime_files"}:
                        violations.append(
                            f"{path.relative_to(ROOT)}:{node.lineno}: sibling import must target runtime_files only"
                        )
                    continue
                target = node.module.split(".", 1)[0]
                if target != "runtime_files":
                    violations.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: sibling import '{node.module}' is not runtime_files"
                    )
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_track_comment_repo_owns_only_track_comment_storage(self) -> None:
        path = ROOT / "scripts/env/repos/track_comments.py"
        source = path.read_text(encoding="utf-8")
        self.assertNotIn("env_legacy_store", source)
        self.assertNotIn("artifact_revision_chain", source)
        tree = ast.parse(source, filename=str(path))
        imported_modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
        forbidden = [name for name in imported_modules if "artifacts" in name or name.endswith(".tracks") or "tasks" in name]
        self.assertEqual(forbidden, [], msg=", ".join(forbidden))

    def test_active_object_repos_do_not_import_env_legacy_store(self) -> None:
        repo_files = sorted(path for path in (ROOT / "scripts/env/repos").glob("*.py") if path.name != "__init__.py")
        violations: list[str] = []
        for path in repo_files:
            if path.name == "runtime_files.py":
                continue
            source = path.read_text(encoding="utf-8")
            if "env_legacy_store" in source:
                violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_active_runtime_modules_do_not_import_env_legacy_store(self) -> None:
        roots = [
            ROOT / "scripts/env/domain",
            ROOT / "scripts/env/repos",
            ROOT / "scripts/env/tools",
        ]
        violations = self._legacy_store_import_violations(roots)
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_track_artifact_publication_writes_only_live_in_publication_domain(self) -> None:
        publication_terms = (
            "published_to_track",
            '"status": "published"',
            "'status': 'published'",
            "shared_materials",
            "close_proof",
        )
        allowed_paths = {
            "scripts/env/domain/publication.py",
            "scripts/env/repos/artifacts.py",
            "scripts/env/repos/tracks.py",
            "scripts/env/domain/artifact_visibility.py",
            "scripts/env/domain/task_management.py",
            "scripts/env/domain/tasks.py",
        }
        scanned_roots = [ROOT / "scripts/env/domain"]
        violations: list[str] = []
        for root in scanned_roots:
            for path in sorted(root.glob("*.py")):
                rel = path.relative_to(ROOT).as_posix()
                source = path.read_text(encoding="utf-8")
                if rel in allowed_paths:
                    continue
                if any(term in source for term in publication_terms):
                    violations.append(rel)
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_domain_cross_object_imports_are_allowlisted(self) -> None:
        domain_files = sorted(path for path in ROOT.glob("scripts/**/domain/*.py") if path.name != "__init__.py")
        if not domain_files:
            self.skipTest("No scripts/**/domain/*.py modules exist in this migration stage; domain boundary scan deferred.")
        violations: list[str] = []
        for path in domain_files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                module = node.module or ""
                if "domain." not in module:
                    continue
                target = module.split("domain.", 1)[1].split(".", 1)[0]
                if target and target not in self._DOMAIN_CROSS_OBJECT_ALLOWLIST:
                    violations.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: domain cross-object import '{target}' is not allowlisted"
                    )
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_skills_and_boundary_guides_do_not_copy_payload_or_schema_tables(self) -> None:
        completed = subprocess.run(
            [
                "rg",
                "-uuu",
                "-n",
                "--glob",
                "*.md",
                (
                    "payload_fields"
                    + "|action_semantics"
                    + "|operation_semantics"
                    + "|\\|\\s*tool\\s*\\|\\s*action\\s*\\|\\s*payload"
                    + "|\\|\\s*action\\s*\\|\\s*payload"
                    + "|##\\s*`[^`]+`\\s+payload"
                ),
                "buddyswitch/skills",
                "framework/contracts",
                "tools/launcher/assets/roles",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))


if __name__ == "__main__":
    unittest.main()
