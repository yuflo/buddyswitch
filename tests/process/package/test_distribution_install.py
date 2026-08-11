"""Process proof for the built and non-editable BuddySwitch distribution."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

from tests.support.package_runtime import add_correspondence_probe, install_clean_runtime
from tests.support.paths import REPO_ROOT


REQUIRED_CUTOVER_RESOURCES = {
    "buddyswitch/catalog/manifest.toml",
    "buddyswitch/catalog/env-profiles/dev.json",
    "buddyswitch/modules/artifact/assets/artifact-selection-v1.json",
    "buddyswitch/modules/artifact/assets/artifact-selection-v2.json",
    "buddyswitch/contracts/schemas/dev/dev-result.json",
    "buddyswitch/foundation/app_server/shell/app_server.sh",
    "buddyswitch/foundation/browser_runtime/assets/chrome-devtools-mcp-1.1.1-tools.json",
    "buddyswitch/launcher/assets/roles/dev/AGENTS.md",
    "buddyswitch/launcher/assets/web-management/index.html",
    "buddyswitch/launcher/assets/web-management/vendor/dompurify/LICENSE",
    "buddyswitch/launcher/assets/web-management/vendor/dompurify/LICENSE-MPL",
    "buddyswitch/launcher/assets/web-management/vendor/highlightjs/LICENSE",
    "buddyswitch/launcher/assets/web-management/vendor/markdown-it/LICENSE",
    "buddyswitch/modules/demand/skills/demand-triage/SKILL.md",
    "buddyswitch/modules/demand/skills/demand-orchestration/SKILL.md",
    "buddyswitch/modules/artifact/skills/artifact-tool/SKILL.md",
    "buddyswitch/modules/track/skills/track-tool/SKILL.md",
    "buddyswitch/modules/track/skills/triage-track/SKILL.md",
    "buddyswitch/skills/dev/implement-scoped-change/SKILL.md",
}
REQUIRED_FOUNDATION_MODULE_FILES = {
    "buddyswitch/foundation/actor_runtime/__init__.py",
    "buddyswitch/foundation/actor_runtime/capability.py",
    "buddyswitch/foundation/actor_runtime/codex_runtime.py",
    "buddyswitch/foundation/actor_runtime/session.py",
    "buddyswitch/foundation/actor_runtime/side_thread.py",
    "buddyswitch/foundation/actor_runtime/side_thread_lifecycle.py",
    "buddyswitch/foundation/actor_runtime/side_thread_registry.py",
    "buddyswitch/foundation/app_server/__init__.py",
    "buddyswitch/foundation/app_server/runtime.py",
    "buddyswitch/foundation/identity/__init__.py",
    "buddyswitch/foundation/identity/model.py",
    "buddyswitch/foundation/identity/profiles.py",
    "buddyswitch/foundation/state/__init__.py",
    "buddyswitch/foundation/state/runtime.py",
    "buddyswitch/foundation/state/actor_private.py",
    "buddyswitch/foundation/process_runtime/process_identity.py",
    "buddyswitch/foundation/process_runtime/json_framing.py",
    "buddyswitch/foundation/runtime_broker/__init__.py",
    "buddyswitch/foundation/runtime_broker/broker.py",
    "buddyswitch/foundation/runtime_broker/client.py",
    "buddyswitch/foundation/runtime_broker/coordinator.py",
    "buddyswitch/foundation/runtime_broker/dispatcher.py",
    "buddyswitch/foundation/runtime_broker/lifecycle.py",
    "buddyswitch/foundation/runtime_broker/protocol.py",
    "buddyswitch/foundation/runtime_broker/server.py",
}


def test_clean_source_builds_one_noneditable_runtime_distribution(tmp_path: Path) -> None:
    installed = install_clean_runtime(tmp_path)
    with zipfile.ZipFile(installed.wheel) as archive:
        names = sorted(archive.namelist())

    assert names
    assert all(
        name.startswith("buddyswitch/")
        or name.startswith("buddyswitch-0.1.0.dist-info/")
        for name in names
    )
    assert "buddyswitch/application/entrypoints/runtime_activation.py" in names
    assert REQUIRED_FOUNDATION_MODULE_FILES <= set(names)
    assert not any(name.startswith("buddyswitch/env/") for name in names)
    assert not any(name.startswith("buddyswitch/runtime_kernel/") for name in names)
    assert "buddyswitch/modules/demand/skills/demand-triage/SKILL.md" in names
    assert "buddyswitch/modules/demand/skills/demand-orchestration/SKILL.md" in names
    assert not [
        name
        for name in names
        if any(
            forbidden in f"/{name}"
            for forbidden in (
                "/tests/",
                "/buddyswitch-codex",
                "/buddyswitch-test",
                "/__pycache__/",
            )
        )
        or name.endswith(".pyc")
    ]

    script = """
import importlib.metadata
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import buddyswitch

current_modules = (
    "buddyswitch.foundation.actor_runtime",
    "buddyswitch.foundation.actor_runtime.capability",
    "buddyswitch.foundation.actor_runtime.codex_runtime",
    "buddyswitch.foundation.actor_runtime.session",
    "buddyswitch.foundation.actor_runtime.side_thread",
    "buddyswitch.foundation.actor_runtime.side_thread_lifecycle",
    "buddyswitch.foundation.actor_runtime.side_thread_registry",
    "buddyswitch.foundation.app_server.runtime",
    "buddyswitch.foundation.identity.model",
    "buddyswitch.foundation.identity.profiles",
    "buddyswitch.foundation.state.runtime",
    "buddyswitch.foundation.state.actor_private",
    "buddyswitch.foundation.process_runtime.process_identity",
    "buddyswitch.foundation.process_runtime.json_framing",
    "buddyswitch.foundation.runtime_broker.protocol",
    "buddyswitch.foundation.runtime_broker.client",
    "buddyswitch.foundation.runtime_broker.lifecycle",
)
module_files = {
    name: str(Path(importlib.import_module(name).__file__).resolve())
    for name in current_modules
}

distribution = importlib.metadata.distribution("buddyswitch")
direct_url = distribution.read_text("direct_url.json")
print(json.dumps({
    "package_file": str(Path(buddyswitch.__file__).resolve()),
    "version": distribution.version,
    "files": sorted(str(path) for path in distribution.files or ()),
    "direct_url": json.loads(direct_url) if direct_url else None,
    "sys_path": sys.path,
    "module_files": module_files,
    "retired_specs": {
        "buddyswitch.env": importlib.util.find_spec("buddyswitch.env") is not None,
        "buddyswitch.runtime_kernel": importlib.util.find_spec("buddyswitch.runtime_kernel") is not None,
        "buddyswitch.launcher.actor_capability": importlib.util.find_spec("buddyswitch.launcher.actor_capability") is not None,
        "buddyswitch.launcher.codex_runtime": importlib.util.find_spec("buddyswitch.launcher.codex_runtime") is not None,
        "buddyswitch.launcher.actor_session": importlib.util.find_spec("buddyswitch.launcher.actor_session") is not None,
        "buddyswitch.launcher.actor_side_thread": importlib.util.find_spec("buddyswitch.launcher.actor_side_thread") is not None,
        "buddyswitch.launcher.side_thread_lifecycle": importlib.util.find_spec("buddyswitch.launcher.side_thread_lifecycle") is not None,
        "buddyswitch.launcher.side_thread_registry": importlib.util.find_spec("buddyswitch.launcher.side_thread_registry") is not None,
    },
}, sort_keys=True))
"""
    environment_probe = installed.run_module(
        "buddyswitch.application.entrypoints.runtime_activation",
        ("status",),
    )
    assert environment_probe.returncode != 0

    import os
    import subprocess

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [str(installed.python), "-c", script],
        cwd=installed.work_root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    package_file = Path(payload["package_file"])
    assert payload["version"] == "0.1.0"
    assert package_file.is_relative_to(installed.runtime_dir / "venv")
    assert not package_file.is_relative_to(installed.source_root / "src")
    assert str(REPO_ROOT) not in payload["sys_path"]
    assert payload["retired_specs"] == {
        "buddyswitch.env": False,
        "buddyswitch.runtime_kernel": False,
        "buddyswitch.launcher.actor_capability": False,
        "buddyswitch.launcher.codex_runtime": False,
        "buddyswitch.launcher.actor_session": False,
        "buddyswitch.launcher.actor_side_thread": False,
        "buddyswitch.launcher.side_thread_lifecycle": False,
        "buddyswitch.launcher.side_thread_registry": False,
    }
    assert set(payload["module_files"]) == {
        "buddyswitch.foundation.actor_runtime",
        "buddyswitch.foundation.actor_runtime.capability",
        "buddyswitch.foundation.actor_runtime.codex_runtime",
        "buddyswitch.foundation.actor_runtime.session",
        "buddyswitch.foundation.actor_runtime.side_thread",
        "buddyswitch.foundation.actor_runtime.side_thread_lifecycle",
        "buddyswitch.foundation.actor_runtime.side_thread_registry",
        "buddyswitch.foundation.app_server.runtime",
        "buddyswitch.foundation.identity.model",
        "buddyswitch.foundation.identity.profiles",
        "buddyswitch.foundation.state.runtime",
        "buddyswitch.foundation.state.actor_private",
        "buddyswitch.foundation.process_runtime.process_identity",
        "buddyswitch.foundation.process_runtime.json_framing",
        "buddyswitch.foundation.runtime_broker.protocol",
        "buddyswitch.foundation.runtime_broker.client",
        "buddyswitch.foundation.runtime_broker.lifecycle",
    }
    assert all(
        Path(module_file).is_relative_to(installed.runtime_dir / "venv")
        for module_file in payload["module_files"].values()
    )
    direct_url = payload["direct_url"]
    assert not (
        isinstance(direct_url, dict)
        and (direct_url.get("dir_info") or {}).get("editable") is True
    )
    assert all(
        path.startswith("buddyswitch/")
        or path.startswith("buddyswitch-0.1.0.dist-info/")
        for path in payload["files"]
    )


def test_runtime_assets_ship_while_colocated_tests_and_caches_do_not(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(
        tmp_path,
        prepare_source=add_correspondence_probe,
    )
    with zipfile.ZipFile(installed.wheel) as archive:
        names = set(archive.namelist())

    assert "buddyswitch/launcher/assets/docs/help.md" in names
    assert "buddyswitch/modules/probe/__init__.py" in names
    assert not [
        name
        for name in names
        if "/tests/" in f"/{name}"
        or "/__pycache__/" in f"/{name}"
        or name.endswith(".pyc")
    ]


def test_atomic_cutover_distribution_contains_every_required_runtime_resource(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(tmp_path)
    with zipfile.ZipFile(installed.wheel) as archive:
        wheel_package_files = {
            name
            for name in archive.namelist()
            if name.startswith("buddyswitch/")
            and "/tests/" not in f"/{name}"
            and "/__pycache__/" not in f"/{name}"
            and not name.endswith(".pyc")
        }

    package_source = REPO_ROOT / "src" / "buddyswitch"
    source_package_files = {
        f"buddyswitch/{path.relative_to(package_source).as_posix()}"
        for path in package_source.rglob("*")
        if path.is_file()
        and "tests" not in path.relative_to(package_source).parts
        and "__pycache__" not in path.relative_to(package_source).parts
        and path.suffix != ".pyc"
    }

    assert REQUIRED_CUTOVER_RESOURCES <= wheel_package_files
    assert wheel_package_files == source_package_files
    assert "buddyswitch/launcher/assets/chrome-devtools-mcp-1.1.1-tools.json" not in wheel_package_files
