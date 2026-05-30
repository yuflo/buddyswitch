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
        description='Discover online actor contacts, send direct actor-address messages, and list inbox messages.',
        cli_resource='message',
        command="python3 scripts/env/client.py message <action> --payload '<json-object>'",
        scope='direct runtime actor inbox messaging',
        capability_boundary='Messages are direct runtime actor-address scope only.',
        object_model=(
            'Messages are direct actor-address inbox rows. They are informal direct communication and do not mutate tracks, artifacts, tasks, comments, or request lifecycle state.'
        ),
        use_when=(
            'You need direct inbox messaging between online runtime actors.',
        ),
        do_not_use_when=(
            'You need object-level discussion; use comment tool actions.',
        ),
        actions=(
            ActionDefinition(
                name='contacts',
                title='message.contacts',
                description='List online actor contacts that can receive direct messages.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'buddy': {
                            'type': 'string',
                            'description': 'Optional manifest buddy id filter for online actor contacts.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='message.contacts',
                authority='message.actor_contact_discovery',
                visibility='online actor contact summary',
                durability='none',
                result_content_level='actor address contact rows',
                success_effect='Returns online actor addresses discovered through central daemon contacts.',
                failure_state_guarantee='Rejected contact reads do not mutate runtime state.',
                reads=(
                    'central daemon online contacts',
                ),
                writes=(),
                does_not_write=(
                    'messages',
                    'tracks',
                    'tasks',
                    'artifacts',
                    'comments',
                    'requests',
                    'buddybox files',
                ),
                preconditions=(
                    'env.tool role-action policy allows this action for the active role',
                ),
                returns=(
                    'contacts',
                    'count',
                ),
                use_when=(
                    'You need contact discovery for a target actor address before message.send.',
                ),
                do_not_use_when=(
                    'You already have a current contact actor_address or need to read inbox messages.',
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
            ActionDefinition(
                name='send',
                title='message.send',
                description='Send one direct message to an online runtime actor address.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['target_actor_address', 'content'],
                    'properties': {
                        'target_actor_address': {
                            'type': 'object',
                            'additionalProperties': False,
                            'required': ['buddy_id', 'instance_id'],
                            'properties': {
                                'buddy_id': {
                                    'type': 'string',
                                    'description': 'Target runtime actor buddy id.',
                                },
                                'instance_id': {
                                    'type': 'string',
                                    'description': 'Target runtime actor instance id.',
                                },
                            },
                            'description': 'Exact RuntimeActorAddress returned by message.contacts.',
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
                visibility='sender and recipient direct message visibility',
                durability='durable',
                result_content_level='message id and delivery status',
                success_effect='Creates one durable inbox message and delivers a message.available signal to the target daemon.',
                failure_state_guarantee='Rejected non-writes do not mutate runtime objects; delivery failures clean up the message or report an indeterminate write.',
                reads=(
                    'manifest buddy ids',
                    'central daemon actor reachability',
                ),
                writes=(
                    'direct actor-address inbox message',
                ),
                does_not_write=(
                    'tracks',
                    'tasks',
                    'artifacts',
                    'comments',
                    'requests',
                    'buddybox files',
                    'browser session',
                ),
                preconditions=(
                    'target_actor_address is a declared manifest buddy actor address',
                    'target_actor_address is online and not the active buddy',
                ),
                returns=(
                    'message_id',
                    'delivery_status',
                ),
                use_when=(
                    'You need to deliver a direct inbox message to a specific online actor address.',
                ),
                do_not_use_when=(
                    'You only have a buddy id but no actor address (use message.contacts) or need target-scoped track/artifact discussion (use comment.add).',
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
                        'q': {
                            'type': 'string',
                            'description': 'Optional case-insensitive keyword filter over active-buddy inbox message content.',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Optional maximum number of inbox messages to return.',
                            'minimum': 1,
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
                visibility='active-buddy inbox',
                durability='none',
                result_content_level='message rows',
                success_effect='Lists active-buddy inbox messages with optional filters.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'active-buddy inbox messages',
                ),
                writes=(),
                does_not_write=(
                    'messages',
                    'tracks',
                    'tasks',
                    'artifacts',
                    'comments',
                    'requests',
                    'buddybox files',
                ),
                preconditions=(
                    'env.tool role-action policy allows this action for the active role',
                ),
                returns=(
                    'messages',
                ),
                use_when=(
                    'You need to read active-buddy inbox messages, optionally filtered by sender buddy, keyword, or bounded count.',
                ),
                do_not_use_when=(
                    'You need to create a new direct message (use message.send) or discuss a track/artifact target thread (use comment.add).',
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
            ActionDefinition(
                name='conversation',
                title='message.conversation',
                description='Read active actor visible bidirectional direct messages with one target actor or buddy.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'target_actor_address': {
                            'type': 'object',
                            'additionalProperties': False,
                            'required': ['buddy_id', 'instance_id'],
                            'properties': {
                                'buddy_id': {
                                    'type': 'string',
                                    'description': 'Target runtime actor buddy id.',
                                },
                                'instance_id': {
                                    'type': 'string',
                                    'description': 'Target runtime actor instance id.',
                                },
                            },
                            'description': 'Exact RuntimeActorAddress for the other conversation participant.',
                        },
                        'buddy': {
                            'type': 'string',
                            'description': 'Target manifest buddy id for all visible actor-address conversations with that buddy.',
                        },
                        'q': {
                            'type': 'string',
                            'description': 'Optional case-insensitive keyword filter over visible conversation content.',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Optional maximum number of latest conversation messages to return.',
                            'minimum': 1,
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='message.conversation',
                authority='message.active_actor_conversation',
                visibility='active actor visible direct conversation messages',
                durability='none',
                result_content_level='message rows',
                success_effect='Lists active actor visible bidirectional direct messages for the selected target actor or buddy.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and do not create messages.',
                reads=(
                    'active actor visible direct messages',
                ),
                writes=(),
                does_not_write=(
                    'messages',
                    'tracks',
                    'tasks',
                    'artifacts',
                    'comments',
                    'requests',
                    'buddybox files',
                ),
                preconditions=(
                    'exactly one of target_actor_address or buddy is provided',
                    'target selector is a declared manifest buddy outside the active buddy',
                ),
                returns=(
                    'messages',
                    'count',
                    'selector',
                ),
                use_when=(
                    'You need bidirectional context between the active actor and one target actor or buddy.',
                ),
                do_not_use_when=(
                    'You only need active actor inbox messages (use message.list) or need to send a new message (use message.send).',
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
