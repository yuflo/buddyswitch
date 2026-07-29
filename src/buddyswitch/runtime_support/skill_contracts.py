"""Typed Skill artifacts exported by product modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillExport:
    id: str
    package_path: str
    enabled_by_default: bool = True
