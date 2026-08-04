"""Phase 8 boundary tests for env layer workspace and state access."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
import tomllib
import unittest
import uuid
from pathlib import Path

from buddyswitch.application.build import build_application
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT

import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.support.python import PYTHON  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

CODEX_CONFIG = ROOT / "src" / "buddyswitch" / "launcher" / "codex_config.py"
MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
PERMISSION_PROFILE = "buddyswitch-runtime"


def _tool_roots() -> dict[str, Path]:
    application = build_application()
    explicit_tool_roots = {
        registration.definition.id: (
            ROOT
            / "src"
            / Path(*registration.invoke.__module__.split(".")).parent
        )
        for registration in application.tools
    }
    dynamic_tool_roots = {
        path.name: path
        for path in (ROOT / "src/buddyswitch/env/tools").iterdir()
        if path.is_dir()
        and not path.name.startswith("_")
        and (path / "__init__.py").is_file()
    }
    assert not (explicit_tool_roots.keys() & dynamic_tool_roots.keys())
    tool_roots = {**dynamic_tool_roots, **explicit_tool_roots}
    return tool_roots


class EnvLayerBoundaryTests(RuntimeWorkspaceTestCase):
    _DOMAIN_CROSS_OBJECT_ALLOWLIST = {
        "publication",
        "artifact_visibility",
        "source_refs",
        "actor_private_workspace",
        "identity",
    }
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
        tool_roots = _tool_roots()
        tool_ids = set(tool_roots)
        violations: list[str] = []
        for tool, package_dir in sorted(tool_roots.items()):
            if not package_dir.is_dir():
                violations.append(f"missing package: {package_dir.relative_to(ROOT)}")
                continue
            for path in sorted(package_dir.rglob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                rel = path.relative_to(ROOT).as_posix()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("buddyswitch.env.tools."):
                                parts = alias.name.split(".")
                                if len(parts) >= 3:
                                    target = parts[2]
                                    if target in tool_ids and target != tool:
                                        violations.append(f"{rel}:{node.lineno}: import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if module == "buddyswitch.env.tools":
                            for alias in node.names:
                                if alias.name in tool_ids and alias.name != tool:
                                    violations.append(
                                        f"{rel}:{node.lineno}: from buddyswitch.env.tools import {alias.name}"
                                    )
                        elif module.startswith("buddyswitch.env.tools."):
                            parts = module.split(".")
                            if len(parts) >= 3:
                                target = parts[2]
                                if target in tool_ids and target != tool:
                                    violations.append(f"{rel}:{node.lineno}: from {module} import ...")

        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_legacy_env_services_tool_entrypoints_are_removed(self) -> None:
        runtime_roots = [ROOT / "src" / "buddyswitch"]
        import_violations: list[str] = []
        for root in runtime_roots:
            for path in sorted(root.rglob("*.py")):
                rel = path.relative_to(ROOT).as_posix()
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("buddyswitch.env.services"):
                                import_violations.append(f"{rel}:{node.lineno}: import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if module == "buddyswitch.env.services":
                            import_violations.append(f"{rel}:{node.lineno}: from {module} import ...")
                        elif module.startswith("buddyswitch.env.services"):
                            import_violations.append(f"{rel}:{node.lineno}: from {module} import ...")
        self.assertEqual(import_violations, [], msg="\n".join(import_violations))

        service_dir = ROOT / "src" / "buddyswitch" / "env" / "services"
        allowed_service_files = {
            "src/buddyswitch/env/services/__init__.py",
        }
        if service_dir.exists():
            service_files = {
                path.relative_to(ROOT).as_posix()
                for path in service_dir.rglob("*.py")
                if "__pycache__" not in path.parts
            }
            self.assertEqual(service_files, allowed_service_files)

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
        completed = run_process(
            [
                PYTHON,
                "-m",
            "buddyswitch.application.entrypoints.actor_build",
            "patch-config",
                "--config",
                str(config_path),
                "--source-root",
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

    def _dispatch_dev_retired_task_tool(self, args: dict[str, object]) -> dict[str, object]:
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
        raw_state_path = f"instances/{actor_id}/retired-task/env-tool-bypass.json"
        raw_probe = self._runtime_path(raw_state_path)

        response = self._dispatch_dev_retired_task_tool(
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
        self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL")
        self.assertEqual(response.get("permission_boundary"), "env.tool")
        self.assertFalse(project_probe.exists())
        self.assertFalse(raw_probe.exists())

    def test_env_tool_services_do_not_write_files_directly(self) -> None:
        completed = run_process(
            [
                "rg",
                "-n",
                r"\.mkdir\(|\.write_text\(|\.write_bytes\(|\.unlink\(|os\.replace\(|NamedTemporaryFile\(",
                "src/buddyswitch/env/tools",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_object_state_sibling_imports_are_restricted_to_runtime_files(self) -> None:
        application = build_application()
        repo_files = sorted(
            {
                *(
                    path
                    for path in ROOT.glob("src/buddyswitch/**/repos/*.py")
                    if path.name != "__init__.py"
                ),
                *(
                    path
                    for module in application.modules
                    for path in (
                        ROOT
                        / "src"
                        / "buddyswitch"
                        / "modules"
                        / module.name
                        / "private"
                        / "state"
                    ).glob("*.py")
                    if path.name != "__init__.py"
                ),
            }
        )
        if not repo_files:
            self.skipTest("No packaged repository modules exist.")
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
        path = (
            ROOT
            / "src/buddyswitch/modules/track/private/state/track_comments.py"
        )
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
        application = build_application()
        repo_files = sorted(
            {
                *(
                    path
                    for path in (ROOT / "src/buddyswitch/env/repos").glob("*.py")
                    if path.name != "__init__.py"
                ),
                *(
                    path
                    for module in application.modules
                    for path in (
                        ROOT
                        / "src"
                        / "buddyswitch"
                        / "modules"
                        / module.name
                        / "private"
                        / "state"
                    ).glob("*.py")
                    if path.name != "__init__.py"
                ),
            }
        )
        violations: list[str] = []
        for path in repo_files:
            if path.name == "runtime_files.py":
                continue
            source = path.read_text(encoding="utf-8")
            if "env_legacy_store" in source:
                violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_active_runtime_modules_do_not_import_env_legacy_store(self) -> None:
        application = build_application()
        roots = [
            ROOT / "src/buddyswitch/env/domain",
            ROOT / "src/buddyswitch/env/repos",
            ROOT / "src/buddyswitch/env/tools",
            *(
                ROOT / "src" / "buddyswitch" / "modules" / module.name
                for module in application.modules
            ),
        ]
        violations = self._legacy_store_import_violations(roots)
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_retired_publication_fields_only_live_in_explicit_guards(self) -> None:
        publication_terms = (
            "published_to_track",
            '"status": "published"',
            "'status': 'published'",
            "shared_materials",
            "close_proof",
        )
        allowed_paths = {
            "src/buddyswitch/modules/artifact/private/adapters/tool/_impl.py",
            "src/buddyswitch/modules/artifact/private/adapters/tool/tool.py",
            "src/buddyswitch/modules/artifact/private/state/artifacts.py",
            "src/buddyswitch/modules/track/private/state/tracks.py",
        }
        scanned_roots = [
            ROOT
            / "src"
            / "buddyswitch"
            / "modules"
            / module.name
            / "private"
            for module in build_application().modules
        ]
        violations: list[str] = []
        for root in scanned_roots:
            for path in sorted(root.rglob("*.py")):
                rel = path.relative_to(ROOT).as_posix()
                source = path.read_text(encoding="utf-8")
                if rel in allowed_paths:
                    continue
                if any(term in source for term in publication_terms):
                    violations.append(rel)
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_retired_task_domain_and_repository_imports_are_absent(self) -> None:
        self.assertFalse((ROOT / "src/buddyswitch/env/domain/tasks.py").exists())
        violations: list[str] = []
        for scan_root in (ROOT / "src" / "buddyswitch",):
            for path in sorted(scan_root.rglob("*")):
                if not path.is_file() or path.suffix not in {".py", ".md"}:
                    continue
                source = path.read_text(encoding="utf-8")
                if "buddyswitch.env.domain.tasks" in source or "buddyswitch.env.repos.tasks" in source:
                    violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(violations, [])

    def test_domain_cross_object_imports_are_allowlisted(self) -> None:
        domain_files = sorted(
            path
            for path in ROOT.glob("src/buddyswitch/**/domain/*.py")
            if path.name != "__init__.py"
        )
        if not domain_files:
            self.skipTest("No packaged domain modules exist.")
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
        completed = run_process(
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
                "src/buddyswitch/skills",
                "src/buddyswitch/modules",
                "src/buddyswitch/contracts",
                "src/buddyswitch/launcher/assets/roles",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))
