#!/usr/bin/env python3
"""Repo-local env.tool package discovery."""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Any

import env.tools

_SKIP_NAMES = {
    "__pycache__",
    "model",
    "discovery",
    "catalog",
    "cli_helpers",
    "contracts",
    "semantics",
    "dispatch",
    "responses",
    "router",
}


def discover_tool_ids() -> list[str]:
    discovered: list[str] = []
    for info in pkgutil.iter_modules(env.tools.__path__):
        if not info.ispkg:
            continue
        if info.name in _SKIP_NAMES:
            continue
        if info.name.startswith("_"):
            continue
        discovered.append(info.name)
    return sorted(set(discovered))


def tool_package_exists(tool: str) -> bool:
    return tool in discover_tool_ids()


def import_tool_module(tool: str, module_name: str) -> ModuleType:
    return importlib.import_module(f"env.tools.{tool}.{module_name}")


def read_module_attr(tool: str, module_name: str, attr_name: str) -> Any:
    module = import_tool_module(tool, module_name)
    return getattr(module, attr_name)
