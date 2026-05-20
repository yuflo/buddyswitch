#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.search."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='search',
        title='Search Boundary',
        description='Expose search backend metadata, URL planning, and browser open actions.',
        cli_resource='search',
        command="python3 scripts/env/client.py search <action> --payload '<json-object>'",
        scope='runtime-visible search capability boundary',
        capability_boundary='Search actions remain inside configured profile backend and launcher browser boundaries.',
        use_when=(
            'You need runtime search boundary metadata or explicit browser search actions.',
        ),
        do_not_use_when=(
            'You need durable product object mutation.',
        ),
        actions=(
            ActionDefinition(
                name='status',
                title='search.status',
                description='Read search capability and backend/browser readiness metadata.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {},
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='none',
                authority='profile.search_boundary',
                preconditions=(
                    'active instance is available',
                ),
                returns=(
                    'backend_status',
                ),
                risk_hints={
                    'read_only': True,
                    'destructive': False,
                    'idempotent': True,
                    'open_world': True,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='request',
                title='search.request',
                description='Resolve one explicit search target URL intent.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'query': {
                            'type': 'string',
                        },
                        'backend': {
                            'type': 'string',
                        },
                        'engine': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='request',
                mutates='none',
                required_permission='none',
                authority='profile.search_boundary',
                preconditions=(
                    'query is non-empty',
                ),
                returns=(
                    'target_url',
                    'backend',
                    'engine',
                ),
                risk_hints={
                    'read_only': True,
                    'destructive': False,
                    'idempotent': True,
                    'open_world': True,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='open_browser',
                title='search.open_browser',
                description='Open one search URL through launcher-managed browser endpoint.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'query': {
                            'type': 'string',
                        },
                        'engine': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='open',
                mutates='browser_session',
                required_permission='none',
                authority='profile.search_boundary',
                preconditions=(
                    'query is non-empty',
                ),
                returns=(
                    'target_url',
                    'backend',
                    'engine',
                ),
                risk_hints={
                    'read_only': False,
                    'destructive': False,
                    'idempotent': False,
                    'open_world': True,
                    'requires_human_approval': False,
                    'external_effect': True,
                },
            ),
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
