#!/usr/bin/env python3
"""Runtime kernel entrypoints for switch resolve/persist."""

from .persist import persist_skill_result_request
from .resolve import resolve_switch_request

__all__ = [
    "resolve_switch_request",
    "persist_skill_result_request",
]
