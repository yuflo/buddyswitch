# BuddySwitch Parallel Modular Architecture

## 已落地基础

BuddySwitch runtime tools are split into discovery-safe contracts and runtime-only implementations:

- `scripts/env/tool_runtime/definition.py` owns tool/action metadata, schema shape, and validation.
- `scripts/env/tool_runtime/registry.py` owns black-box discovery, authorization, and dispatch.
- `scripts/env/tools/<tool>/tool.py` owns the public tool definition and lazy invoke entrypoint.
- `scripts/env/tools/<tool>/_impl.py` owns runtime implementation details and may load repos, domains, or services.

This keeps catalog discovery cheap and prevents stable guidance from depending on private implementation modules.

## Skill / Tool Contract 衔接规则

Skill 通过 runtime discovery 消费能力，不复制能力. Skills should point actors to current discovery surfaces such as `context.get.tool_catalog` and the diagnostic fallback `python3 scripts/turn_runtime.py status`.

Skills must not freeze payload schemas, duplicate action semantics, or teach private module paths as product workflow. The runtime registry remains the source of truth for available tools, payload fields, effects, and rejection metadata.

## Boundaries

Do not add a workflow engine, plugin system, or event bus for imagined coordination needs. Keep tool contracts concrete, implementation modules direct, and runtime routing explicit until repeated product usage proves a stable abstraction is needed.
