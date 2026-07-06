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
        title='Central IM Messages',
        description='Message tools cover optional actor discovery views, Central IM target-identity sends through the IM target resolver, exact processable inbound reads, replies, conversation context, and disposition marking.',
        scope='Central IM identity messaging for the active actor',
        capability_boundary='Messages use identity-addressed Central IM conversations, messages, events, and per-identity dispositions. Actor and external identities are valid Central IM direct targets when resolved by IM target rules; message.contacts is a read-only view and does not decide message.send permission.',
        object_model=(
            'Messages are Central IM conversation records with actor or external identity ids, durable message rows, identity-visible events, and per-identity dispositions. They do not mutate tracks, artifacts, tasks, comments, browser state, or actor private files.'
        ),
        use_when=(
            'You need Central IM messaging between the active actor identity and another actor or external identity by explicit target_identity_id, or a reply_to wrapper for one processable inbound IM message.',
        ),
        do_not_use_when=(
            'You need object-level discussion; use comment tool actions.',
        ),
        actions=(
            ActionDefinition(
                name='contacts',
                title='message.contacts',
                description='List optional actor discovery target identities backed by actor runtime presence; this read-only view does not decide message.send permission, and the active actor identity is not sendable as self.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'role': {
                            'type': 'string',
                            'description': 'Optional manifest role id filter for actor discovery targets backed by actor runtime presence.',
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
                visibility='optional actor discovery view',
                durability='none',
                result_content_level='actor identity discovery rows',
                success_effect='Returns optional actor discovery identities projected from actor runtime presence.',
                failure_state_guarantee='Rejected contact reads do not mutate runtime state.',
                reads=(
                    'actor runtime presence',
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
                    'actors',
                    'count',
                ),
                use_when=(
                    'You need an optional actor contact discovery view for possible actor target identities.',
                ),
                do_not_use_when=(
                    'message.send already has an explicit actor or external target_identity_id, or you need to read Central IM events.',
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
                description=(
                    'Send one Central IM message. Use target_identity_id for an explicit target send. Use reply_to '
                    'when replying to one processable inbound message; the reply wrapper resolves the original sender '
                    'into target_identity_id, validates it through the same IM target resolver, writes through the '
                    'unified send path, then marks the original message replied after durable send success. The IM '
                    'target resolver checks identity profiles and actor runtime reachability for actor targets; '
                    'external identities can be direct Central IM targets when an external profile exists. For actor-to-actor handoffs, make '
                    "the content actionable from the recipient's visible context; include the relevant "
                    'source intent, concrete inputs, and requested output instead of relying on private '
                    'message/conversation ids.'
                ),
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['content'],
                    'properties': {
                        'target_identity_id': {
                            'type': 'string',
                            'description': 'Explicit target identity id for target sends. Omit it when using reply_to; the reply wrapper resolves the original sender into target_identity_id and uses the same IM target resolver.',
                        },
                        'content': {
                            'type': 'string',
                            'description': 'Message body text.',
                        },
                        'reply_to': {
                            'type': 'string',
                            'description': 'Processable inbound message id addressed to the active actor identity. The reply wrapper resolves the original sender into target_identity_id, validates it through the same IM target resolver, writes through the unified send path, and marks that original message replied after durable send success.',
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
                authority='message.central_im_channel',
                visibility='sender and recipient Central IM conversation visibility',
                durability='durable',
                result_content_level='message id, target identity, delivery status, and actor_handling_status for actor targets',
                success_effect=(
                    'Creates one durable Central IM message. For actor targets, the runtime projection may submit '
                    'one target actor local inbound event after the Central IM write and return actor_handling_status. '
                    'Explicit target sends and reply wrapper sends both use the same IM target resolver before the '
                    'unified send path. When reply_to is provided the original processable inbound message transitions '
                    'to replied after durable send success. Target identities are accepted only after the IM target '
                    'resolver validates identity profiles and actor runtime reachability for actor targets.'
                ),
                failure_state_guarantee='IM target resolver, reply wrapper, and payload rejections do not mutate state; reply disposition save failure can leave the accepted Central IM reply durable while the original remains in its previous disposition.',
                reads=(
                    'reply source message when reply_to is provided',
                    'identity profiles for target identities',
                    'actor runtime reachability for actor targets',
                ),
                writes=(
                    'Central IM message',
                    'target actor local inbound event when the final target identity is actor',
                    'original message replied disposition when reply_to succeeds',
                ),
                does_not_write=(
                    'tracks',
                    'artifacts',
                    'comments',
                    'actor_private files',
                    'browser session',
                ),
                preconditions=(
                    'content is non-empty',
                    'exactly one of target_identity_id or reply_to is provided',
                    'IM target resolver accepts the final target_identity_id',
                    'reply_to, when provided, references a processable inbound message addressed to the active actor',
                ),
                returns=(
                    'message_id',
                    'target_identity',
                    'delivery_status',
                    'actor_handling_status',
                    'original_message_id and original_final_disposition when reply_to is provided',
                ),
                use_when=(
                    'You need to create a new Central IM message from the active actor identity to a specific actor or external target identity.',
                    'You need to reply to one processable inbound message, including external-origin messages, using reply_to so the runtime resolves the original sender through the normal target-identity path.',
                ),
                do_not_use_when=(
                    'You are starting a new target-identity conversation and do not have an explicit target identity id.',
                    'You need Track discussion; use track.add_comment instead of Central IM.',
                    'Use message.mark(absorbed) when no reply is needed.',
                    'Use task_sys.need_parent when a task_sys.side_frame needs parent handling.',
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
                authority='message.current_identity_exact_message',
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
                    'You need the Central IM event feed (use message.list) or conversation context (use message.conversation).',
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
                description='Set only non-reply absorbed disposition for one exact inbound message.',
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
                            'description': 'Allowed value is absorbed. Use message.send(reply_to=...) for replied and task_sys.need_parent for parent handoff.',
                            'enum': ['absorbed'],
                        },
                        'reason': {
                            'type': 'string',
                            'description': 'Ignored or omitted for absorbed.',
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
                authority='message.current_identity_message_disposition',
                visibility='active actor exact processable inbound message disposition',
                durability='durable',
                result_content_level='updated message disposition metadata',
                success_effect='absorbed saves the message as processed without a reply.',
                failure_state_guarantee='Validation failures do not mutate message state.',
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
                ),
                returns=(
                    'message_id',
                    'disposition',
                    'message',
                ),
                use_when=(
                    'You processed an exact inbound message and need to mark disposition absorbed.',
                ),
                do_not_use_when=(
                    'You need to reply; use message.send with reply_to so the message is marked replied after delivery.',
                    'You need parent handling from a task_sys.side_frame; use task_sys.need_parent.',
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
                description='Read active actor visible Central IM events after a cursor.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'cursor': {
                            'type': 'string',
                            'description': 'Optional Central IM event cursor. Omit to read from the initial event cursor.',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Optional maximum number of events to return.',
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
                authority='message.central_im_identity_events',
                visibility='active actor Central IM identity event feed',
                durability='none',
                result_content_level='event rows and next_cursor',
                success_effect='Returns active actor visible Central IM events after the supplied cursor.',
                failure_state_guarantee='Rejected reads do not mutate runtime state.',
                reads=(
                    'active actor visible Central IM identity events',
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
                    'events',
                    'next_cursor',
                ),
                use_when=(
                    'You need to read Central IM delivery events visible to the active actor from a cursor.',
                ),
                do_not_use_when=(
                    'You need full message content for a specific event message_id (use message.get) or a direct conversation transcript (use message.conversation).',
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
                description='Read active actor visible bidirectional direct messages with one target identity.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['target_identity_id'],
                    'properties': {
                        'target_identity_id': {
                            'type': 'string',
                            'description': 'Identity id for the other conversation peer.',
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
                authority='message.current_identity_conversation',
                visibility='active actor visible direct conversation messages',
                durability='none',
                result_content_level='message rows',
                success_effect='Lists active actor visible bidirectional direct messages for the selected target identity.',
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
                    'target_identity_id is provided',
                    'target_identity_id must not be the active actor identity',
                ),
                returns=(
                    'messages',
                    'count',
                    'selector',
                ),
                use_when=(
                    'You need bidirectional context between the active actor and one target identity.',
                ),
                do_not_use_when=(
                    'You only need Central IM event notifications (use message.list) or need to send a new message (use message.send).',
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
