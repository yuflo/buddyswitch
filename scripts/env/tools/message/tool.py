#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.message."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, TASK_REQUIREMENT_FREE, ToolDefinition, validate_definition


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='message',
        title='Direct Actor Messages',
        description='Message tools cover online actor contact discovery, direct actor-address sends, exact processable inbound reads, and non-reply disposition marking.',
        scope='direct runtime actor inbox messaging',
        capability_boundary='Messages are direct runtime actor-address scope only.',
        object_model=(
            'Messages are direct actor-address inbox rows. They are informal direct communication and do not mutate tracks, artifacts, tasks, comments, browser state, or actor private files.'
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
                description='List online actor contacts for direct sends; only the active full ActorAddress row is not sendable as self.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'role': {
                            'type': 'string',
                            'description': 'Optional manifest role id filter for online actor contacts.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                task_requirement=TASK_REQUIREMENT_FREE,
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
                    'actor_private files',
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
                description='Send one direct outbound message to an online runtime actor address, or reply to one processable inbound message with reply_to.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['target_actor_address', 'content'],
                    'properties': {
                        'target_actor_address': {
                            'type': 'object',
                            'additionalProperties': False,
                            'required': ['role_id', 'actor_id'],
                            'properties': {
                                'role_id': {
                                    'type': 'string',
                                    'description': 'Target runtime actor role id.',
                                },
                                'actor_id': {
                                    'type': 'string',
                                    'description': 'Target runtime actor id.',
                                },
                            },
                            'description': 'Exact ActorAddress returned by message.contacts.',
                        },
                        'content': {
                            'type': 'string',
                            'description': 'Message body text.',
                        },
                        'reply_to': {
                            'type': 'string',
                            'description': 'Optional processable inbound message id addressed to the active actor. When reply_to is provided, success marks that original message as replied after delivery.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission='message.send',
                authority='message.direct_actor_address_channel',
                visibility='sender and recipient direct message visibility',
                durability='durable',
                result_content_level='message id and delivery status',
                success_effect='Creates and delivers one durable inbox message; when reply_to is provided, also transitions the original processable inbound message to replied.',
                failure_state_guarantee='Reachability and payload rejections do not mutate state; delivery failures clean up the created message or report delivery cleanup uncertainty; reply disposition save failure can leave the delivered reply durable while the original remains in its previous disposition.',
                reads=(
                    'manifest role ids',
                    'central daemon actor reachability',
                ),
                writes=(
                    'direct actor-address inbox message',
                    'original message replied disposition when reply_to succeeds',
                ),
                does_not_write=(
                    'tracks',
                    'tasks',
                    'artifacts',
                    'comments',
                    'actor_private files',
                    'browser session',
                ),
                preconditions=(
                    'target_actor_address.role_id is a declared manifest role',
                    'target actor is online and is not the active full ActorAddress',
                    'reply_to, when provided, references a processable inbound message addressed to the active actor',
                ),
                returns=(
                    'message_id',
                    'delivery_status',
                    'original_message_id and original_final_disposition when reply_to is provided',
                ),
                use_when=(
                    'You need to deliver a direct inbox message to a specific online actor address.',
                    'You need to reply to one processable inbound message and mark the original replied after delivery.',
                ),
                do_not_use_when=(
                    'You only have a role id but no actor address (use message.contacts) or need Track discussion (use track.add_comment).',
                    'Use message.mark(absorbed) when no reply is needed.',
                    'Use message.mark(needs_parent) when side triage needs parent handling.',
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
                name='get',
                title='message.get',
                description='Read one exact processable inbound message by id without changing disposition; processable means unseen or needs_parent.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['message_id'],
                    'properties': {
                        'message_id': {
                            'type': 'string',
                            'description': 'Exact inbound message id to process.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission='message.get',
                authority='message.active_actor_exact_message',
                visibility='active actor exact processable inbound message',
                durability='none',
                result_content_level='full message row with disposition metadata',
                success_effect='Returns one exact processable inbound message without changing disposition.',
                failure_state_guarantee='Rejected reads do not mutate message state.',
                reads=(
                    'one active actor processable inbound message',
                ),
                writes=(),
                does_not_write=(
                    'messages',
                    'tracks',
                    'tasks',
                    'artifacts',
                    'comments',
                    'actor_private files',
                ),
                preconditions=(
                    'message_id references a message addressed to the active actor',
                    'message disposition is unseen or needs_parent',
                ),
                returns=(
                    'message',
                    'message_id',
                    'disposition',
                ),
                use_when=(
                    'A prompt gives an exact message_id and you need to read that exact inbound message and its disposition metadata.',
                ),
                do_not_use_when=(
                    'You need general inbox scanning (use message.list) or conversation context (use message.conversation).',
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
                name='mark',
                title='message.mark',
                description='Set only non-reply processing dispositions for one exact inbound message: absorbed or needs_parent.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['message_id', 'disposition'],
                    'properties': {
                        'message_id': {
                            'type': 'string',
                            'description': 'Exact inbound message id to mark.',
                        },
                        'disposition': {
                            'type': 'string',
                            'description': 'Allowed values are absorbed and needs_parent. Use message.send(reply_to=...) for replied.',
                            'enum': ['absorbed', 'needs_parent'],
                        },
                        'reason': {
                            'type': 'string',
                            'description': 'Required and non-empty for needs_parent; ignored or omitted for absorbed.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission='message.mark',
                authority='message.active_actor_message_disposition',
                visibility='active actor exact processable inbound message disposition',
                durability='durable',
                result_content_level='updated message disposition metadata',
                success_effect='absorbed saves the message as processed without a reply; needs_parent submits the parent prompt first, then saves the message as needs_parent.',
                failure_state_guarantee='Validation failures do not mutate state; needs_parent prompt-submit failure leaves the message in its previous disposition; needs_parent save failure after prompt submit leaves the message in its previous disposition but the parent prompt was already submitted.',
                reads=(
                    'one active actor processable inbound message',
                ),
                writes=(
                    'message disposition metadata',
                ),
                does_not_write=(
                    'tracks',
                    'tasks',
                    'artifacts',
                    'comments',
                    'actor_private files',
                ),
                preconditions=(
                    'message_id references a message addressed to the active actor',
                    'message disposition transition is valid',
                    'needs_parent includes a non-empty reason',
                ),
                returns=(
                    'message_id',
                    'disposition',
                    'message',
                ),
                use_when=(
                    'You processed an exact inbound message and need to mark disposition absorbed, or side triage needs_parent with a reason.',
                ),
                do_not_use_when=(
                    'You need to reply; use message.send with reply_to so the message is marked replied after delivery.',
                    'Do not use message.mark as a generic disposition editor.',
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
                description='List active actor inbox messages.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'role': {
                            'type': 'string',
                            'description': 'Optional inbox role filter.',
                        },
                        'q': {
                            'type': 'string',
                            'description': 'Optional case-insensitive keyword filter over active actor inbox message content.',
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
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission='message.list',
                authority='message.active_actor_inbox',
                visibility='active actor inbox',
                durability='none',
                result_content_level='message rows',
                success_effect='Lists active actor inbox messages with optional filters.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'active actor inbox messages',
                ),
                writes=(),
                does_not_write=(
                    'messages',
                    'tracks',
                    'tasks',
                    'artifacts',
                    'comments',
                    'actor_private files',
                ),
                preconditions=(
                    'env.tool role-action policy allows this action for the active role',
                ),
                returns=(
                    'messages',
                ),
                use_when=(
                    'You need to read active actor inbox messages, optionally filtered by sender role, keyword, or bounded count.',
                ),
                do_not_use_when=(
                    'You need to create a new direct message (use message.send) or discuss a Track thread (use track.add_comment).',
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
                description='Read active actor visible bidirectional direct messages with one target actor address.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['target_actor_address'],
                    'properties': {
                        'target_actor_address': {
                            'type': 'object',
                            'additionalProperties': False,
                            'required': ['role_id', 'actor_id'],
                            'properties': {
                                'role_id': {
                                    'type': 'string',
                                    'description': 'Target runtime actor role id.',
                                },
                                'actor_id': {
                                    'type': 'string',
                                    'description': 'Target runtime actor id.',
                                },
                            },
                            'description': 'Exact ActorAddress for the other conversation participant.',
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
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission='message.conversation',
                authority='message.active_actor_conversation',
                visibility='active actor visible direct conversation messages',
                durability='none',
                result_content_level='message rows',
                success_effect='Lists active actor visible bidirectional direct messages for the selected target actor address.',
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
                    'actor_private files',
                ),
                preconditions=(
                    'target_actor_address is provided and is a declared manifest role actor address',
                    'target_actor_address must not be the active actor',
                ),
                returns=(
                    'messages',
                    'count',
                    'selector',
                ),
                use_when=(
                    'You need bidirectional context between the active actor and one target actor address.',
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
