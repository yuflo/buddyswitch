#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.message."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='message',
        title='Buddy Messages',
        description='Send and list direct buddy-to-buddy inbox messages.',
        cli_resource='message',
        command="python3 scripts/env/client.py message <action> --payload '<json-object>'",
        scope='direct buddy-to-buddy inbox messaging',
        capability_boundary='Messages are direct buddy-to-buddy scope only.',
        use_when=(
            'You need direct inbox messaging between manifest-declared buddies.',
        ),
        do_not_use_when=(
            'You need object-level discussion; use comment tool actions.',
        ),
        actions=(
            ActionDefinition(
                name='send',
                title='message.send',
                description='Send one direct message to another manifest buddy.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['to_buddy', 'content'],
                    'properties': {
                        'to_buddy': {
                            'type': 'string',
                            'description': 'manifest buddy id recipient; must differ from active_buddy.',
                        },
                        'content': {
                            'type': 'string',
                            'description': 'Message body text.',
                        },
                        'reply_to': {
                            'type': 'string',
                            'description': 'Optional parent message id for threading.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='message.send',
                authority='message.direct_buddy_channel',
                preconditions=(
                    'to_buddy is a declared manifest buddy',
                    'to_buddy != active_buddy',
                ),
                returns=(
                    'message_id',
                    'message',
                ),
                risk_hints={
                    'read_only': False,
                    'destructive': False,
                    'idempotent': False,
                    'open_world': False,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='list',
                title='message.list',
                description='List active-buddy inbox messages.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'buddy': {
                            'type': 'string',
                            'description': 'Optional inbox buddy filter.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='message.list',
                authority='message.active_buddy_inbox',
                preconditions=(
                    'active buddy owns message.list permission',
                ),
                returns=(
                    'messages',
                ),
                risk_hints={
                    'read_only': True,
                    'destructive': False,
                    'idempotent': True,
                    'open_world': False,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
