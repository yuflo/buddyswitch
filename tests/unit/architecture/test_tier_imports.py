"""Import boundaries keep the unit tier independent of heavier harnesses."""

from __future__ import annotations

import ast

from tests.support.paths import REPO_ROOT


def test_unit_tests_do_not_import_higher_tier_harnesses() -> None:
    forbidden_prefixes = ("tests.integration", "tests.process", "tests.system")
    violations: list[str] = []

    for path in sorted((REPO_ROOT / "tests" / "unit").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            for module in imported:
                if module.startswith(forbidden_prefixes):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {module}"
                    )

    assert violations == []
