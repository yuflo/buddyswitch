#!/usr/bin/env python3
"""evidence env.tool contract."""

from __future__ import annotations

from typing import Any

from env.tools.model import MUTATES_BROKER_TOKEN

TOOL_ID = "evidence"

TOOL_SPEC: dict[str, Any] = {
    "tool": TOOL_ID,
    "cli_resource": "evidence",
    "command": "python3 scripts/env/client.py evidence <operation>",
    "scope": "target-scoped browser evidence for market quality gates",
    "actions": [
        {
            "name": "issue_browser",
            "payload_fields": ["target_type", "target_id", "mode"],
            "kind": "issue",
            "mutates": MUTATES_BROKER_TOKEN,
            "required_permission": "evidence.issue",
            "authority": "market.evidence_scope",
            "preconditions": ["target_type is artifact", "target_id references readable target"],
            "returns": ["tool_evidence"],
        },
        {
            "name": "approve_downgrade",
            "payload_fields": ["target_type", "target_id", "reason"],
            "kind": "issue",
            "mutates": MUTATES_BROKER_TOKEN,
            "required_permission": "evidence.approve",
            "authority": "market.evidence_scope",
            "preconditions": ["target_type is artifact", "reason is non-empty"],
            "returns": ["tool_evidence"],
        },
    ],
}
