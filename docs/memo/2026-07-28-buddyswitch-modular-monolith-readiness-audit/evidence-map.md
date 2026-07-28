# Modular Monolith Readiness Evidence Map

## 1. Evidence identity

```text
commit: 9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3
branch: fea-tool
runtime code diff: none
audit documents: untracked preparation scope
```

## 2. Consumer-path evidence

| Path | Current owner/evidence | Target obligation | Audit state |
|---|---|---|---|
| public launch | `buddyswitch-codex:4-30` -> `tools/launcher/cli.py` | thin wrapper into installed package entrypoint | COMPLETE |
| test launch | `buddyswitch-test:4-9`; `tests/runner.py:65-120,240-287` | one package-aware runner; co-located roots; no source path surgery | COMPLETE |
| instance start | `host_control.sh:309-591`; `HostControl.start` | package-owned lifecycle operation and exact result | COMPLETE |
| Actor build | `actor_environment.py:26-49,101-205,328-437` | atomic selected Role/config/private/project projection; no implementation | COMPLETE |
| remaining lifecycle | `host_control.sh:595-1132` | lifecycle matrix preserved in every runtime stage | COMPLETE |
| runtime provenance | `runtime_broker.sh:31-104`; `env.sh:225-296`; dispatcher dynamic loads | one installed distribution identity for all BuddySwitch processes | COMPLETE |
| shared project | Actor builder seed/link path | preserve seed-once and Actor projection semantics | COMPLETE |
| Role bootstrap | manifest, runtime Skills and selected Role AGENTS | RoleHost + assembled Skill exports; selected projection only | COMPLETE |
| Runtime Broker | workspace broker plus checkout dynamic handlers | package entrypoint with no runtime source lookup | COMPLETE |
| Env MCP | checkout server to Broker socket | same installed runtime identity | COMPLETE |
| Daemon | `instance_daemon.py:18-52` | business-neutral host receives full component registrations | COMPLETE |
| Web/IM | `web_management.py` route/projection/worker imports | WebHost contributions; Communication owns channel worker | COMPLETE |
| Browser | lifecycle, broker and daemon paths | Actor foundation capability | COMPLETE |
| state paths | `runtime_files.py:20-90`; shared/instance tree | explicit immutable locators, no package-depth inference | COMPLETE |
| cleanup | `env_cleanup.py` product attribution and instance traversal | lifecycle host plus module cleanup contributions | COMPLETE |
| product owners | Demand/Task/Track/Artifact/Communication and cross-cutting tools | explicit component assemblies and small Public contracts | COMPLETE |
| Search/Evidence/Context | Tool implementations and broad ToolContext | capability/projection components, not generic host semantics | COMPLETE |
| guidance/tests | active docs, Roles, Skills and topology-sensitive tests | stage-local replacement and distribution/residue proof | COMPLETE |

## 3. Evidence completion rule

For each A01–A12 surface, add:

- consumer action;
- entrypoint and source lines;
- semantic owner;
- files/config/state/processes consumed;
- failure and cleanup path;
- current direct tests;
- required target owner/projection;
- migration stage and replacement proof.
