#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.request."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition


_REF_ITEM_SCHEMA = {
    "type": "object",
    "description": "Track-scoped request reference object.",
    "additionalProperties": False,
    "required": ["type", "id"],
    "properties": {
        "type": {
            "type": "string",
            "description": "Reference object type.",
            "enum": ["track", "artifact", "comment"],
        },
        "id": {
            "type": "string",
            "description": "Reference object id.",
        },
    },
}


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id="request",
        title="Cross-Buddy Requests",
        description="Create and manage explicit cross-buddy collaboration requests on tracks.",
        cli_resource="request",
        command="python3 scripts/env/client.py request <action> --payload '<json-object>'",
        scope="durable cross-buddy collaboration request lifecycle on readable tracks",
        capability_boundary="Request mutations are constrained by requester/recipient role and request state transitions.",
        object_model=(
            'Requests are durable cross-buddy collaboration lifecycle rows bound to readable tracks. They model requester/recipient accepted-blocked-done-canceled state and are separate from private tasks and informal messages.'
        ),
        use_when=(
            "You need durable requester/recipient accepted-blocked-done-canceled state on a track.",
        ),
        do_not_use_when=(
            "You only need informal direct text; use message.send or comment.add.",
        ),
        actions=(
            ActionDefinition(
                name="create",
                title="request.create",
                description="Create one durable cross-buddy request bound to one readable track.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["track_id", "to_buddy", "title", "summary"],
                    "properties": {
                        "track_id": {
                            "type": "string",
                            "description": "Track id the request belongs to.",
                        },
                        "to_buddy": {
                            "type": "string",
                            "description": "Manifest buddy id receiving this request.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Short request title.",
                        },
                        "summary": {
                            "type": "string",
                            "description": "Detailed request summary.",
                        },
                        "target_refs": {
                            "type": "array",
                            "description": "Optional track-context refs the recipient should read before acting.",
                            "items": _REF_ITEM_SCHEMA,
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates="runtime_objects",
                required_permission="request.create",
                authority="request.cross_buddy_scope",
                visibility='requester, recipient, and PM',
                durability='durable',
                result_content_level='request row and id',
                success_effect='Creates one durable track-scoped cross-buddy request for a recipient buddy.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'readable non-archived track',
                    'manifest buddy ids',
                    'target refs',
                ),
                writes=(
                    'request row',
                ),
                does_not_write=(
                    'task state',
                    'track timeline',
                    'artifact body',
                    'comment status',
                    'message inbox',
                    'buddybox files',
                ),
                preconditions=(
                    "track_id references a readable non-archived track",
                    "to_buddy is a manifest buddy and differs from active_buddy",
                ),
                returns=("request_id", "request"),
                use_when=(
                    "You need to ask a specific recipient buddy for track-scoped request work, review, or response with durable lifecycle state.",
                ),
                do_not_use_when=(
                    "You need private task planning only; use task.create/task.update.",
                ),
                risk_hints={
                    "read_only": False,
                    "destructive": False,
                    "idempotent": False,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
            ActionDefinition(
                name="list",
                title="request.list",
                description="List visible requests for active buddy with optional filters.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {
                        "box": {
                            "type": "string",
                            "description": "Optional mailbox filter.",
                            "enum": ["all", "inbox", "outbox"],
                        },
                        "status": {
                            "type": "string",
                            "description": "Optional lifecycle status filter.",
                            "enum": ["open", "accepted", "blocked", "done", "canceled"],
                        },
                        "track_id": {
                            "type": "string",
                            "description": "Optional track id filter.",
                        },
                        "buddy": {
                            "type": "string",
                            "description": "Optional buddy filter across requester/recipient endpoints.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="read",
                mutates="none",
                required_permission="request.read",
                authority="request.visibility_scope",
                visibility='requester, recipient, and PM filtered visibility',
                durability='none',
                result_content_level='request summary rows',
                success_effect='Lists requests visible to the active buddy for inbox/outbox/status scanning.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'visible request rows',
                ),
                writes=(),
                does_not_write=(
                    'request lifecycle',
                    'task state',
                    'track state',
                    'artifact body',
                    'message inbox',
                    'buddybox files',
                ),
                preconditions=(
                    "active buddy is requester, recipient, or pm for each returned request",
                ),
                returns=("requests",),
                use_when=(
                    "You need inbox/outbox request visibility, status filtering, and lifecycle scanning.",
                ),
                do_not_use_when=(
                    "You need one exact request row by id; use request.get.",
                ),
                risk_hints={
                    "read_only": True,
                    "destructive": False,
                    "idempotent": True,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
            ActionDefinition(
                name="get",
                title="request.get",
                description="Read one visible request row by request id.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["request_id"],
                    "properties": {
                        "request_id": {
                            "type": "string",
                            "description": "Request id to fetch.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="read",
                mutates="none",
                required_permission="request.read",
                authority="request.visibility_scope",
                visibility='requester, recipient, and PM filtered visibility',
                durability='none',
                result_content_level='request row',
                success_effect='Reads one durable request row by id.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'one visible request row',
                ),
                writes=(),
                does_not_write=(
                    'request lifecycle',
                    'task state',
                    'track state',
                    'artifact body',
                    'message inbox',
                    'buddybox files',
                ),
                preconditions=(
                    "request_id references a visible request",
                ),
                returns=("request",),
                use_when=(
                    "You need one durable request row with current visibility and track-linked lifecycle fields.",
                ),
                do_not_use_when=(
                    "You need broader request scanning/filtering; use request.list.",
                ),
                risk_hints={
                    "read_only": True,
                    "destructive": False,
                    "idempotent": True,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
            ActionDefinition(
                name="accept",
                title="request.accept",
                description="Recipient accepts one open or blocked request.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["request_id"],
                    "properties": {
                        "request_id": {
                            "type": "string",
                            "description": "Request id to accept.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates="runtime_objects",
                required_permission="request.accept",
                authority="request.recipient_scope",
                visibility='requester, recipient, and PM',
                durability='durable',
                result_content_level='request row',
                success_effect='Recipient moves one open or blocked request to accepted.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'one visible request row',
                ),
                writes=(
                    'request status',
                ),
                does_not_write=(
                    'task state',
                    'track timeline',
                    'artifact body',
                    'comment status',
                    'message inbox',
                    'buddybox files',
                ),
                preconditions=(
                    "active buddy matches request.to_buddy",
                    "status is open or blocked",
                ),
                returns=("request",),
                use_when=(
                    "You are the request recipient and can move this request into accepted state to start work now.",
                ),
                do_not_use_when=(
                    "You need to indicate a blocker; use request.block.",
                ),
                risk_hints={
                    "read_only": False,
                    "destructive": False,
                    "idempotent": False,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
            ActionDefinition(
                name="block",
                title="request.block",
                description="Recipient marks an accepted request as blocked with blocker text.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["request_id", "blocker"],
                    "properties": {
                        "request_id": {
                            "type": "string",
                            "description": "Request id to block.",
                        },
                        "blocker": {
                            "type": "string",
                            "description": "Non-empty blocker explanation.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates="runtime_objects",
                required_permission="request.block",
                authority="request.recipient_scope",
                visibility='requester, recipient, and PM',
                durability='durable',
                result_content_level='request row',
                success_effect='Recipient marks an accepted request blocked with blocker text.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'one visible request row',
                ),
                writes=(
                    'request status and blocker',
                ),
                does_not_write=(
                    'task state',
                    'track timeline',
                    'artifact body',
                    'comment status',
                    'message inbox',
                    'buddybox files',
                ),
                preconditions=(
                    "active buddy matches request.to_buddy",
                    "status is accepted",
                ),
                returns=("request",),
                use_when=(
                    "You are the recipient and cannot proceed until a blocker is addressed.",
                ),
                do_not_use_when=(
                    "You can finish delivery now; use request.complete.",
                ),
                risk_hints={
                    "read_only": False,
                    "destructive": False,
                    "idempotent": False,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
            ActionDefinition(
                name="complete",
                title="request.complete",
                description="Recipient marks an accepted or blocked request done with result refs.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["request_id", "result_refs"],
                    "properties": {
                        "request_id": {
                            "type": "string",
                            "description": "Request id to complete.",
                        },
                        "result_refs": {
                            "type": "array",
                            "description": "Non-empty track-context refs proving completion outcome.",
                            "items": _REF_ITEM_SCHEMA,
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates="runtime_objects",
                required_permission="request.complete",
                authority="request.recipient_scope",
                visibility='requester, recipient, and PM',
                durability='durable',
                result_content_level='request row',
                success_effect='Recipient marks an accepted or blocked request done with result refs.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'one visible request row',
                    'result refs',
                ),
                writes=(
                    'request status and result refs',
                ),
                does_not_write=(
                    'task state',
                    'track timeline',
                    'artifact body',
                    'comment status',
                    'message inbox',
                    'buddybox files',
                ),
                preconditions=(
                    "active buddy matches request.to_buddy",
                    "status is accepted or blocked",
                    "result_refs is non-empty",
                ),
                returns=("request",),
                use_when=(
                    "You are the recipient and finished the requested work, so the request can move to done with durable result refs.",
                ),
                do_not_use_when=(
                    "Work is blocked and not complete; use request.block.",
                ),
                risk_hints={
                    "read_only": False,
                    "destructive": False,
                    "idempotent": False,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
            ActionDefinition(
                name="cancel",
                title="request.cancel",
                description="Requester cancels one open, accepted, or blocked request.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["request_id"],
                    "properties": {
                        "request_id": {
                            "type": "string",
                            "description": "Request id to cancel.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates="runtime_objects",
                required_permission="request.cancel",
                authority="request.requester_scope",
                visibility='requester, recipient, and PM',
                durability='durable',
                result_content_level='request row',
                success_effect='Requester cancels one request that is no longer needed.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'one visible request row',
                ),
                writes=(
                    'request status',
                ),
                does_not_write=(
                    'task state',
                    'track timeline',
                    'artifact body',
                    'comment status',
                    'message inbox',
                    'buddybox files',
                ),
                preconditions=(
                    "active buddy matches request.from_buddy",
                    "status is open, accepted, or blocked",
                ),
                returns=("request",),
                use_when=(
                    "You are the requester and this request should be canceled because it is no longer needed in current iteration scope.",
                ),
                do_not_use_when=(
                    "You are not the request sender; recipient/third-party should not cancel.",
                ),
                risk_hints={
                    "read_only": False,
                    "destructive": True,
                    "idempotent": False,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
