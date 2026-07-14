"""Permanent collection topology for the four BuddySwitch test tiers."""

from __future__ import annotations

from tests.support.paths import REPO_ROOT


def test_all_test_files_live_in_one_of_the_four_tiers() -> None:
    tests_root = REPO_ROOT / "tests"
    tiers = {"unit", "integration", "process", "system"}

    assert all((tests_root / tier).is_dir() for tier in tiers)
    misplaced: list[str] = []
    for path in sorted(tests_root.rglob("*")):
        if path.is_symlink():
            misplaced.append(f"symlink: {path.relative_to(REPO_ROOT)}")
            continue
        if not path.is_file():
            continue
        is_python_test = path.name.startswith("test_") and path.suffix == ".py"
        is_javascript_test = path.name.endswith(".test.js")
        if not (is_python_test or is_javascript_test):
            continue
        relative = path.relative_to(tests_root)
        if not relative.parts or relative.parts[0] not in tiers:
            misplaced.append(relative.as_posix())
        if is_javascript_test and relative.parts[0] != "unit":
            misplaced.append(f"non-unit JavaScript: {relative.as_posix()}")

    assert misplaced == []
