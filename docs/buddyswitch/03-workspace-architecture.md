# BuddySwitch v1 — Workspace Architecture

## 1. Architecture decision

For the MVP, BuddySwitch should run inside a **single workspace repository**.

Do not split the framework and the target project into separate Git repositories for the first version.

## 2. Why a single workspace repo

A single workspace repo gives the cleanest path for:

- project-level instructions
- project-scoped custom agents
- repo-local skills
- shared artifacts
- simple Git synchronization
- low setup friction for Codex CLI experiments

It also reduces ambiguity about where:
- the framework lives
- the project code lives
- the artifacts live
- the noisy run dumps live

## 3. Recommended layout

```text
workspace/
├─ .git/
├─ AGENTS.md
├─ README.md
├─ .gitignore
├─ .codex/
│  ├─ config.toml
│  └─ agents/
│     ├─ market.toml
│     ├─ pm.toml
│     ├─ design.toml
│     ├─ dev.toml
│     └─ test.toml
├─ .agents/
│  └─ skills/
├─ framework/
│  ├─ docs/
│  ├─ templates/
│  └─ contracts/
├─ projects/
│  └─ app/
├─ artifacts/
│  ├─ research/
│  ├─ prd/
│  ├─ design/
│  ├─ build/
│  └─ test/
├─ runs/
│  ├─ raw/
│  └─ summaries/
└─ evals/
   ├─ cases/
   └─ rubrics/
```

## 4. Directory responsibilities

### Root
Holds the canonical framework entry points and Git boundary.

### `.codex/`
Codex-specific project configuration and custom agent definitions.

### `.agents/skills/`
Reusable skill bundles used by BuddySwitch agents.

### `framework/`
Framework-native docs, templates, contracts, and notes.

### `projects/app/`
The main MVP target product code.

### `artifacts/`
Durable outputs meant to remain part of the working knowledge base.

### `runs/raw/`
Noisy, temporary, or debugging-oriented intermediate outputs.

### `runs/summaries/`
Compact summaries of runs that are useful to keep.

### `evals/`
Small evaluation cases used to check that the framework still behaves correctly over time.

## 5. Artifact vs run-dump model

BuddySwitch needs a clear distinction:

### Durable artifact
A reusable or handoff-worthy document.
Examples:
- final research memo
- PRD
- design spec
- implementation report
- test report

### Raw run dump
Temporary intermediate output that helped the agent think or operate.
Examples:
- scratch notes
- raw logs
- raw traces
- copied snippets
- partial step notes
- transient debugging output

## 6. Workspace philosophy

The workspace is not only a code repo.
It is a **development collaboration environment**.

That means the repository must support both:

- software implementation
- structured human-agent collaboration memory

## 7. Why not separate framework and app for MVP

Splitting too early creates unnecessary questions:

- where should Codex start from?
- which repo owns the artifacts?
- where do raw dumps belong?
- how do project-scoped instructions stay visible?
- how should Git history represent framework changes vs project changes?

For BuddySwitch v1, keep one repo.
Split later only if real usage proves a strong need.
