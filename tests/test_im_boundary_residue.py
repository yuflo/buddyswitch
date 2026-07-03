#!/usr/bin/env python3
"""Scoped live-surface residue checks for the IM boundary replacement."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SURFACES = (
    ROOT / "scripts" / "env",
    ROOT / "tools" / "launcher",
    ROOT / "tests",
    ROOT / "buddyswitch",
)
FORBIDDEN_TERMS = (
    "contacts.list",
    "list_contacts",
    "central daemon contacts",
    "central daemon online contacts",
)


def test_im_boundary_has_no_stale_live_contact_surfaces() -> None:
    hits: list[str] = []
    self_path = Path(__file__).resolve()
    for surface in SURFACES:
        if not surface.exists():
            continue
        for path in surface.rglob("*"):
            if not path.is_file() or path.resolve() == self_path or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            relative = path.relative_to(ROOT)
            for line_number, line in enumerate(text.splitlines(), start=1):
                for term in FORBIDDEN_TERMS:
                    if term in line:
                        hits.append(f"{relative}:{line_number}: {term}")
    assert hits == []
