#!/usr/bin/env python3
"""Shared env.tool metadata shapes."""

from __future__ import annotations

from typing import TypedDict

MUTATES_NONE = "none"
MUTATES_RUNTIME_OBJECTS = "runtime_objects"
MUTATES_RUNTIME_FILES = "runtime_files"
MUTATES_BROKER_TOKEN = "broker_token"
MUTATES_BROWSER_SESSION = "browser_session"


class ActionSpec(TypedDict, total=False):
    name: str
    payload_fields: list[str]
    kind: str
    mutates: str
    required_permission: str
    authority: str
    preconditions: list[str]
    returns: list[str]


class ToolSpec(TypedDict, total=False):
    tool: str
    cli_resource: str
    command: str
    scope: str
    actions: list[ActionSpec]


class ToolLoadProblem(TypedDict):
    tool: str
    module: str
    error: str
