"""Process proof for the installed runtime activation identity."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path

from tests.support.package_runtime import (
    COLOCATED_TEST,
    RUNTIME_ASSET,
    InstalledRuntime,
    add_correspondence_probe,
    install_clean_runtime,
)


ENTRYPOINT = "buddyswitch.application.entrypoints.runtime_activation"


def _payload(
    installed: InstalledRuntime,
    command: str,
    *args: str,
) -> tuple[object, dict[str, object]]:
    completed = installed.run_module(ENTRYPOINT, (command, *args))
    return completed, installed.json_payload(completed)


def _assert_runtime_mismatch(
    installed: InstalledRuntime,
    command: str = "activate",
) -> dict[str, object]:
    args = (
        ("--source-root", str(installed.source_root))
        if command == "activate"
        else ()
    )
    completed, payload = _payload(installed, command, *args)
    assert completed.returncode == 6
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RUNTIME_MISMATCH"
    return payload


def test_activation_binds_source_distribution_interpreter_and_package_root(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(tmp_path)

    missing, missing_payload = _payload(installed, "verify")
    assert missing.returncode == 5
    assert missing_payload["ok"] is False
    assert (missing_payload["error"])["code"] == "RUNTIME_UNAVAILABLE"

    activated, activated_payload = _payload(
        installed,
        "activate",
        "--source-root",
        str(installed.source_root),
    )
    assert activated.returncode == 0, activated.stderr
    assert activated_payload["ok"] is True
    assert activated_payload["kind"] == "runtime.activate"

    activation_path = installed.runtime_dir / "activation.json"
    assert activation_path.is_file()
    assert activation_path.stat().st_mode & 0o777 == 0o600
    record = json.loads(activation_path.read_text(encoding="utf-8"))
    assert set(record) == {
        "schema_version",
        "source_root",
        "source_digest",
        "package_version",
        "distribution_digest",
        "python_executable",
        "package_root",
        "activated_at",
    }
    assert record["schema_version"] == 1
    assert record["source_root"] == str(installed.source_root)
    assert record["package_version"] == "0.1.0"
    assert record["python_executable"] == str(installed.python)
    assert Path(record["package_root"]).is_relative_to(installed.runtime_dir / "venv")
    for digest_field in ("source_digest", "distribution_digest"):
        assert len(record[digest_field]) == 64
        int(record[digest_field], 16)

    verified, verified_payload = _payload(installed, "verify")
    assert verified.returncode == 0, verified.stderr
    assert verified_payload["ok"] is True
    assert verified_payload["kind"] == "runtime.verify"
    assert verified_payload["data"]["runtime_identity"] == record

    status, status_payload = _payload(installed, "status")
    assert status.returncode == 0, status.stderr
    assert status_payload["ok"] is True
    assert status_payload["kind"] == "runtime.status"
    assert status_payload["data"]["runtime_identity"] == record


def test_activation_rejects_source_distribution_and_interpreter_drift(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(tmp_path)
    activated, _ = _payload(
        installed,
        "activate",
        "--source-root",
        str(installed.source_root),
    )
    assert activated.returncode == 0, activated.stderr
    activation_path = installed.runtime_dir / "activation.json"
    record_bytes = activation_path.read_bytes()

    source_init = installed.source_root / "src" / "buddyswitch" / "__init__.py"
    source_bytes = source_init.read_bytes()
    source_init.write_bytes(source_bytes + b"\nSOURCE_DRIFT = True\n")
    source_drift, source_payload = _payload(installed, "verify")
    assert source_drift.returncode == 6
    assert source_payload["ok"] is False
    assert source_payload["error"]["code"] == "RUNTIME_MISMATCH"
    source_init.write_bytes(source_bytes)

    record = json.loads(record_bytes)
    record["python_executable"] = "/wrong/runtime/python"
    activation_path.write_text(
        json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    interpreter_drift, interpreter_payload = _payload(installed, "verify")
    assert interpreter_drift.returncode == 6
    assert interpreter_payload["error"]["code"] == "RUNTIME_MISMATCH"
    activation_path.write_bytes(record_bytes)
    os.chmod(activation_path, 0o600)

    package_init = Path(json.loads(record_bytes)["package_root"]) / "__init__.py"
    package_bytes = package_init.read_bytes()
    package_init.write_bytes(package_bytes + b"\nINSTALLED_DRIFT = True\n")
    distribution_drift, distribution_payload = _payload(installed, "verify")
    assert distribution_drift.returncode == 6
    assert distribution_payload["error"]["code"] == "RUNTIME_MISMATCH"


def test_activation_rejects_source_drift_before_first_record(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(
        tmp_path,
        prepare_source=add_correspondence_probe,
    )
    asset = installed.source_root / "src" / "buddyswitch" / RUNTIME_ASSET
    asset.write_bytes(asset.read_bytes() + b"SOURCE DRIFT\n")

    payload = _assert_runtime_mismatch(installed)
    assert payload["error"]["details"] == {
        "source_only": [],
        "installed_only": [],
        "changed": [RUNTIME_ASSET.as_posix()],
    }
    assert not (installed.runtime_dir / "activation.json").exists()


def test_activation_rejects_correspondence_drift_without_rewriting_record(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(
        tmp_path,
        prepare_source=add_correspondence_probe,
    )
    activated, activated_payload = _payload(
        installed,
        "activate",
        "--source-root",
        str(installed.source_root),
    )
    assert activated.returncode == 0, activated.stderr
    assert activated_payload["ok"] is True
    activation_path = installed.runtime_dir / "activation.json"
    record_bytes = activation_path.read_bytes()
    record = json.loads(record_bytes)
    source_package = installed.source_root / "src" / "buddyswitch"
    installed_package = Path(record["package_root"])

    def assert_mutation(
        mutate: Callable[[], object],
        restore: Callable[[], object],
        expected_details: dict[str, object],
    ) -> None:
        mutate()
        try:
            payload = _assert_runtime_mismatch(installed)
            assert payload["error"]["details"] == expected_details
            assert activation_path.read_bytes() == record_bytes
        finally:
            restore()

    source_only = source_package / "source-only.txt"
    assert_mutation(
        lambda: source_only.write_bytes(b"source only\n"),
        source_only.unlink,
        {
            "source_only": ["source-only.txt"],
            "installed_only": [],
            "changed": [],
        },
    )

    source_file = source_package / "modules" / "probe" / "__init__.py"
    source_file_bytes = source_file.read_bytes()
    assert_mutation(
        source_file.unlink,
        lambda: source_file.write_bytes(source_file_bytes),
        {
            "source_only": [],
            "installed_only": ["modules/probe/__init__.py"],
            "changed": [],
        },
    )

    source_asset = source_package / RUNTIME_ASSET
    source_asset_bytes = source_asset.read_bytes()
    assert_mutation(
        lambda: source_asset.write_bytes(source_asset_bytes + b"source drift\n"),
        lambda: source_asset.write_bytes(source_asset_bytes),
        {
            "source_only": [],
            "installed_only": [],
            "changed": [RUNTIME_ASSET.as_posix()],
        },
    )

    installed_only = installed_package / "installed-only.txt"
    assert_mutation(
        lambda: installed_only.write_bytes(b"installed only\n"),
        installed_only.unlink,
        {"paths": [str(installed_only)]},
    )

    installed_file = installed_package / "modules" / "probe" / "__init__.py"
    installed_file_bytes = installed_file.read_bytes()
    assert_mutation(
        installed_file.unlink,
        lambda: installed_file.write_bytes(installed_file_bytes),
        {"path": "buddyswitch/modules/probe/__init__.py"},
    )

    installed_asset = installed_package / RUNTIME_ASSET
    installed_asset_bytes = installed_asset.read_bytes()
    assert_mutation(
        lambda: installed_asset.write_bytes(installed_asset_bytes + b"installed drift\n"),
        lambda: installed_asset.write_bytes(installed_asset_bytes),
        {
            "source_only": [],
            "installed_only": [],
            "changed": [RUNTIME_ASSET.as_posix()],
        },
    )

    verified, verified_payload = _payload(installed, "verify")
    assert verified.returncode == 0, verified.stderr
    assert verified_payload["ok"] is True
    assert activation_path.read_bytes() == record_bytes


def test_activation_rejects_source_symlinks_before_exclusions(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(
        tmp_path,
        prepare_source=add_correspondence_probe,
    )
    package_root = installed.source_root / "src" / "buddyswitch"
    source_file = package_root / "modules" / "probe" / "__init__.py"
    candidates = (
        (package_root / "modules" / "probe" / "linked.py", source_file, False),
        (
            package_root / "modules" / "probe" / "linked_package",
            package_root / "launcher",
            True,
        ),
        (
            package_root / "modules" / "probe" / "tests" / "linked_test.py",
            source_file,
            False,
        ),
    )
    activation_path = installed.runtime_dir / "activation.json"
    observed: list[tuple[Path, int, dict[str, object], bool]] = []
    for candidate, target, target_is_directory in candidates:
        candidate.symlink_to(target, target_is_directory=target_is_directory)
        try:
            completed, payload = _payload(
                installed,
                "activate",
                "--source-root",
                str(installed.source_root),
            )
            observed.append(
                (candidate, completed.returncode, payload, activation_path.exists())
            )
            activation_path.unlink(missing_ok=True)
        finally:
            candidate.unlink()

    assert [(candidate.name, returncode) for candidate, returncode, _, _ in observed] == [
        ("linked.py", 6),
        ("linked_package", 6),
        ("linked_test.py", 6),
    ]
    assert not [
        candidate.name
        for candidate, _, _, record_exists in observed
        if record_exists
    ]
    for candidate, _, payload, _ in observed:
        assert payload["ok"] is False
        assert payload["error"]["code"] == "RUNTIME_MISMATCH"
        assert "symlink" in payload["error"]["message"].lower()
        assert payload["error"]["details"] == {"path": str(candidate)}


def test_activation_ignores_colocated_tests_and_cache_but_tracks_runtime_assets(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(
        tmp_path,
        prepare_source=add_correspondence_probe,
    )
    activated, activated_payload = _payload(
        installed,
        "activate",
        "--source-root",
        str(installed.source_root),
    )
    assert activated.returncode == 0, activated.stderr
    assert activated_payload["ok"] is True

    package_root = installed.source_root / "src" / "buddyswitch"
    colocated_test = package_root / COLOCATED_TEST
    colocated_test.write_bytes(colocated_test.read_bytes() + b"# ignored drift\n")
    cache = package_root / "modules" / "probe" / "__pycache__" / "probe.pyc"
    cache.write_bytes(b"ignored cache drift")

    verified, verified_payload = _payload(installed, "verify")
    assert verified.returncode == 0, verified.stderr
    assert verified_payload["ok"] is True

    asset = package_root / RUNTIME_ASSET
    asset.write_bytes(asset.read_bytes() + b"runtime drift\n")
    _assert_runtime_mismatch(installed, "verify")
