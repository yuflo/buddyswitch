# S1.6 Replacement and Acceptance

## Outcome

> S1 is one runnable installed-package truth with no old executable/source
> route, copied implementation, stale guidance or residual process.

## Required deletion

Delete after consumer cutover:

```text
scripts/**
tools/launcher/**
tools/__init__.py
buddyswitch/manifest.toml
buddyswitch/env-profiles/**
buddyswitch/skills/**
framework/contracts/**
framework/config/**
framework/schemas/**
framework/agent-registry.md
```

Root `buddyswitch-codex`, `buddyswitch-test`, root tests/docs and
`projects/app` remain under decisions D-007, D-020 and D-026.

## Required active-guidance replacement

Update exact current consumers:

- root `README.md`;
- root `AGENTS.md` stable paths;
- `docs/arch/**` whose executable paths changed;
- Role `AGENTS.md`;
- every packaged Skill invoking old diagnostics/paths;
- CLI/help/error text;
- tests/fakes/fixtures asserting old paths.

Historical memos remain historical and may name old paths.

## Residue scans

Scan active source/tests/guidance for:

```text
scripts/
tools/launcher
framework/contracts
buddyswitch/manifest.toml
buddyswitch/env-profiles
buddyswitch/skills
env_legacy_store
sys.path.insert
PYTHONPATH
spec_from_file_location
--repo-root runtime source loading
workspace implementation roots
```

Every match is classified as:

- forbidden live residue;
- exact negative absence guard;
- historical memo;
- valid unrelated text with evidence.

## Final proof

1. clean build/install;
2. distribution content allowlist;
3. focused package/runtime/lifecycle proofs;
4. frozen `./buddyswitch-test full`;
5. representative real Actor start/Tool/clear/resume/stop/delete;
6. Web/IM/Browser/Daemon operations;
7. runtime identity agreement;
8. Actor workspace allowlist;
9. old-root/current-guidance absence;
10. `git diff --check`;
11. clean process/socket/lock/temp state.

## Acceptance record

Use `../stage-acceptance-template.md` and attach:

- exact move/delete manifest;
- built distribution manifest/digest;
- runtime identities;
- test run IDs/results/duration;
- real Actor/process identities;
- residue closure rows;
- current docs changed;
- omitted checks and residual risk.

S1 acceptance unlocks S2 Demand. It does not authorize S2 in the same
execution plan.
