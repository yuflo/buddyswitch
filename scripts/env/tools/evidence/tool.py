#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.evidence."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='evidence',
        title='Market Evidence',
        description='Issue target-scoped transient evidence token metadata for artifact quality gates.',
        scope='target-scoped browser evidence for market quality gates',
        capability_boundary='Evidence actions are target-scoped and return transient token metadata.',
        object_model=(
            'Evidence actions issue transient target-scoped token metadata for artifact quality gates. Evidence tokens do not persist product objects and do not replace durable artifact, track, request, or comment state.'
        ),
        use_when=(
            'You need artifact-scoped evidence token metadata.',
        ),
        do_not_use_when=(
            'You need durable runtime object mutation.',
        ),
        actions=(
            ActionDefinition(
                name='issue_browser',
                title='evidence.issue_browser',
                description='Issue one browser evidence token metadata row.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['target_type', 'target_id'],
                    'properties': {
                        'target_type': {
                            'type': 'string',
                            'description': 'Evidence target type.',
                            'enum': ['artifact'],
                        },
                        'target_id': {
                            'type': 'string',
                            'description': 'Readable target id.',
                        },
                        'mode': {
                            'type': 'string',
                            'description': 'Optional evidence mode hint.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='issue',
                mutates='broker_token',
                required_permission='evidence.issue',
                authority='market.evidence_scope',
                visibility='active-buddy token response only',
                durability='transient',
                result_content_level='token metadata',
                success_effect='Issues one transient browser evidence token metadata row for an artifact target.',
                failure_state_guarantee='Rejected token issuance does not create token metadata and does not mutate product state.',
                reads=(
                    'target artifact metadata',
                    'browser evidence payload',
                ),
                writes=(
                    'transient evidence token metadata',
                ),
                does_not_write=(
                    'artifact body',
                    'artifact state',
                    'track state',
                    'request lifecycle',
                    'buddybox files',
                ),
                preconditions=(
                    'target_type is artifact',
                    'target_id references readable target',
                ),
                returns=(
                    'tool_evidence',
                ),
                use_when=(
                    'You need transient browser evidence token metadata for one artifact target.',
                ),
                do_not_use_when=(
                    'You need durable evidence persistence or mutation of product objects.',
                    'The target is not an artifact.',
                    'You are recording explicit downgrade approval metadata; use evidence.approve_downgrade.',
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
                name='approve_downgrade',
                title='evidence.approve_downgrade',
                description='Issue one downgrade approval token metadata row.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['target_type', 'target_id', 'reason'],
                    'properties': {
                        'target_type': {
                            'type': 'string',
                            'description': 'Evidence target type.',
                            'enum': ['artifact'],
                        },
                        'target_id': {
                            'type': 'string',
                            'description': 'Readable target id.',
                        },
                        'reason': {
                            'type': 'string',
                            'description': 'Reason text approving downgrade.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='issue',
                mutates='broker_token',
                required_permission='evidence.approve',
                authority='market.evidence_scope',
                visibility='active-buddy token response only',
                durability='transient',
                result_content_level='token metadata',
                success_effect='Issues one transient downgrade approval token metadata row with a non-empty reason.',
                failure_state_guarantee='Rejected token issuance does not create token metadata and does not mutate product state.',
                reads=(
                    'target artifact metadata',
                    'reason payload',
                ),
                writes=(
                    'transient downgrade approval token metadata',
                ),
                does_not_write=(
                    'artifact body',
                    'artifact state',
                    'track state',
                    'request lifecycle',
                    'buddybox files',
                ),
                preconditions=(
                    'target_type is artifact',
                    'reason is non-empty',
                ),
                returns=(
                    'tool_evidence',
                ),
                use_when=(
                    'You need an explicit one-off artifact downgrade approval token with a non-empty reason.',
                ),
                do_not_use_when=(
                    'You need a standing or blanket downgrade policy instead of one-off approval.',
                    'Reason text is empty or omitted.',
                    'You need normal browser evidence metadata issuance; use evidence.issue_browser after browser work.',
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
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
