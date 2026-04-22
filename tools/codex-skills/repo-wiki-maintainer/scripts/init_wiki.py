from __future__ import annotations

import argparse
from pathlib import Path

from common import load_repo_config

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"

TEMPLATE_TARGETS: tuple[tuple[str, str], ...] = (
    ("wiki-readme.md", "docs/llm-wiki/README.md"),
    ("recent-important-changes.md", "docs/llm-wiki/recent-important-changes.md"),
    ("verification-map.md", "docs/llm-wiki/verification-map.md"),
    ("llm-wiki.toml", ".llm-wiki.toml"),
)


def _load_template(template_name: str) -> str:
    return (TEMPLATE_ROOT / template_name).read_text(encoding="utf-8")


def _file_matches_template(file_path: Path, template_name: str) -> bool:
    return file_path.read_text(encoding="utf-8") == _load_template(template_name)


def _is_valid_repo_config(file_path: Path) -> bool:
    try:
        load_repo_config(file_path)
    except Exception:
        return False
    return True


def _preflight_target_paths(repo_root: Path) -> None:
    for template_name, relative_target_path in TEMPLATE_TARGETS:
        relative_target = Path(relative_target_path)
        relative_parts = relative_target.parts

        for index in range(len(relative_parts)):
            relative_candidate = Path(*relative_parts[: index + 1])
            candidate_path = repo_root / relative_candidate
            is_terminal = index == len(relative_parts) - 1
            candidate_label = relative_candidate.as_posix()

            if candidate_path.is_symlink():
                raise FileExistsError(
                    f"wiki-init target path conflict at symlink: {candidate_label}"
                )

            if not candidate_path.exists():
                continue

            if is_terminal:
                if relative_target_path == ".llm-wiki.toml" and candidate_path.is_file():
                    if _is_valid_repo_config(candidate_path):
                        continue
                    raise FileExistsError(
                        f"wiki-init target path already exists: {candidate_label}"
                    )

                if candidate_path.is_file() and _file_matches_template(
                    candidate_path, template_name
                ):
                    continue
                raise FileExistsError(f"wiki-init target path already exists: {candidate_label}")

            if not candidate_path.is_dir():
                raise FileExistsError(
                    f"wiki-init target path conflict at non-directory ancestor: {candidate_label}"
                )


def scaffold_repo_wiki(repo_root: Path) -> None:
    _preflight_target_paths(repo_root)

    for template_name, relative_target_path in TEMPLATE_TARGETS:
        target_path = repo_root / relative_target_path
        if relative_target_path == ".llm-wiki.toml" and target_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(_load_template(template_name), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap repo wiki scaffold files.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root directory where docs/llm-wiki and .llm-wiki.toml should be scaffolded.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    scaffold_repo_wiki(Path(args.repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
