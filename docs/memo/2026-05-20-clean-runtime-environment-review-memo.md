# Clean Runtime Environment Review Memo

Date: 2026-05-20
Status: review memo only; no runtime code changes implemented here.

## Background Problem

Recent BuddySwitch runtime hardening made filesystem permission rules real enough to affect normal
Codex host behavior.

The visible symptom is repeated permission prompts while running buddies or native sub-agents:

```text
Reason: command failed; retry without sandbox?
rg --files ...
rg -n ...
```

The concrete failing pattern is not a business-task permission need. It is ordinary Codex exploration
running inside a workspace that still contains launcher-owned runtime surfaces that the permission
profile denies.

Current runtime shape:

- `tools/launcher/codex_config.py` enables sandbox approval prompts through
  `sandbox_approval = true`.
- The BuddySwitch permission profile uses a broad default read rule, `"/" = "read"`.
- The same profile then denies selected runtime workspace paths such as
  `workspace/buddyswitch/objects`.
- `tools/launcher/workspace.sh` still projects runtime object state into the ordinary workspace under
  `buddyswitch/objects/*`.
- Native Codex exploration such as `rg --files`, `rg -n ... .`, or `git status` can traverse into
  those visible-but-denied paths and receive `Operation not permitted`.

That failure is host-visible. Codex sees a normal command fail under sandbox, then the current
approval policy turns that failure into a request to retry outside the sandbox.

## Review Verdict

The proposed clean runtime environment is the right repair direction and is sufficiently small.

The problem is a runtime environment contract mismatch:

```text
The workspace shows paths that the sandbox says must not be touched.
```

The clean repair is:

```text
Only expose what the host should inspect through ordinary filesystem exploration.
Everything else should be reached through the runtime tool surface.
```

This avoids solving the issue with prompt instructions such as "do not run rg" or "always remember to
exclude this path." Those instructions would be brittle because `rg --files`, `git status`, and
similar commands are normal host behavior when Codex needs to orient itself.

## Recommended Contract

BuddySwitch product runtime should present a clean host-visible environment:

- Ordinary workspace search must not hit denied runtime state directories.
- Runtime product objects remain broker-owned and are accessed through env tools.
- Buddybox private files remain active-buddy private and are addressed by `logical_name` through
  buddybox env tools.
- The permission profile should be close to an allowlist, not broad host read plus many denies.
- A sandbox denial in product runtime should not normally become an unsandboxed retry prompt.

In short:

```text
sandbox = permission boundary
clean runtime workspace = visibility boundary
env tools = runtime state boundary
```

All three need to agree.

## Minimal Repair Path

### P0: Remove Denied Runtime State From Normal Search

Do not project broker-owned product state into the ordinary workspace in a way that root-level
exploration can traverse.

The main target is `buddyswitch/objects/**`. It should not be a visible directory tree that ordinary
commands can enter and then fail on. Runtime object access should stay behind env tools such as
`track`, `task`, `artifact`, `message`, `comment`, and `context`.

This directly fixes the observed `rg --files` / `rg -n .` prompt loop without teaching Codex a new
search ritual.

### P0: Make Permission Profile Match The Visible World

Replace the broad `"/" = "read"` posture for product sessions with a tighter allowlist-style profile.

The profile should grant only the surfaces the buddy can actually use:

- runtime workspace files that are intended to be host-visible;
- `scripts/env/client.py` and required runtime client modules;
- `projects/app` with read or write access according to the active buddy profile;
- active broker socket access;
- safe temp and instance-local Codex/home/config roots;
- active-buddy private workspace only if direct filesystem visibility remains intentionally required.

Avoid placing denied child paths under commonly searched visible parents.

### P0: Stop Sandbox Failures From Becoming The Main UI

Product runtime should avoid turning expected sandbox denials into "retry without sandbox" prompts.

If a command crosses a real boundary, the preferred behavior is a bounded failure plus structured
runtime guidance. It should not invite the host to bypass the sandbox unless the user explicitly enters
a maintenance/debug mode.

### P1: Keep Buddybox Tool-First

Buddybox should remain a tool-backed private data plane. The durable contract is `logical_name`, not
direct filesystem paths.

If BuddySwitch keeps an active-buddy writable buddybox directory, it should not create ambiguity that
sub-agents are supposed to locate shared coordination files through generic filesystem search. The
runtime surface should make the env-tool route the most host-visible route.

### P1: Add Host-Visible Regression Tests

Existing tests cover profile rendering and one sandbox script-read smoke path. They do not prove the
real incident path.

Add tests that launch or simulate the generated runtime profile and prove:

- `rg --files` from the runtime workspace exits cleanly without `Operation not permitted`;
- `rg -n ... .` over ordinary visible workspace paths does not prompt for sandbox bypass;
- `git status --short --untracked-files=all` does not warn on denied runtime directories;
- `python3 scripts/env/client.py buddybox read --logical-name ...` still works through the broker;
- direct reads or writes of broker-owned runtime objects remain blocked.

These tests should assert host-visible behavior, not only config shape.

## Why This Is Not Over-Complex

This proposal does not add a workflow engine, a new agent coordinator, a rule DSL, or a prompt
classification layer.

It removes a mismatch:

```text
visible path + denied permission + sandbox approval prompt
```

and replaces it with one simpler contract:

```text
visible paths are safe to explore; private/runtime state uses tools.
```

That is narrower than trying to enumerate all commands Codex may run. It also handles future host
behavior better because it fixes the environment shape rather than one command pattern.

## Alignment With docs/bitter

This plan is tightly aligned with
`docs/bitter/2026-05-18-tool-skill-layering-principles.md`.

The relevant bitter rule is:

```text
When behavior is wrong, fix the layer that owns the wrong contract.
```

Here, the broken contract belongs to the workspace, sandbox, and runtime tool boundary layers. It does
not belong to AGENTS or sub-agent prompt wording.

Alignment points:

- It fixes host-visible runtime behavior instead of adding prompt bulk.
- It keeps AGENTS short; no command blacklist or phrase-to-tool router is required.
- It makes tool-backed runtime state the authoritative access path.
- It asks for tests that catch the actual host-visible break.
- It preserves the distinction between workflow skills and atomic tool capability semantics.

The main thing to avoid is a workaround that says:

```text
Tell Codex not to run rg --files, or tell it to always exclude buddyswitch/objects.
```

That would violate `docs/bitter` because it compensates for an unclear runtime boundary with host
memory and prompt discipline.

## Non-Goals

This memo does not recommend:

- broadening source write permissions;
- weakening runtime object privacy;
- making buddybox product-readable;
- replacing env tools with direct file access;
- adding a general sandbox framework inside BuddySwitch;
- changing PM, Design, Dev, or Market business workflows.

## External Reference Notes

OpenAI Codex CLI documentation describes Codex as operating in a selected directory with sandbox and
approval controls. Those controls govern execution permission; they do not by themselves create a
clean virtual filesystem view.

Docker AI sandbox practice is closer to the desired visibility model: the agent sees a mounted working
environment, while host files outside that environment are not part of ordinary exploration.

Useful references:

- `https://developers.openai.com/codex/cli`
- `https://developers.openai.com/codex/permissions`
- `https://developers.openai.com/codex/agent-approvals-security`
- `https://docs.docker.com/ai/sandboxes/agents/codex/`
- `https://docs.docker.com/ai/sandboxes/security/defaults/`

## Short Review Summary

The clean runtime environment proposal is the smallest durable fix for the current permission-prompt
incident.

The current system asks Codex to work in a filesystem that advertises paths it is not allowed to
touch. The repair should make the visible workspace and permission profile agree, and keep runtime
state access behind env tools. This is more faithful to `docs/bitter` than any prompt-side rule that
tries to train the host around the mismatch.
