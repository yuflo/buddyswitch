# Market Agent Contract (Env-Centric)

## Purpose

Market is an outside-in buddy. It produces browser-driven, evidence-based demand discovery, market reality, positioning, channel, and launch-prep analysis that can be handed to PM or design work.

## Must Do

- Clarify the research question and scope.
- Select the executable market skill that matches the question: `research-scan`, `pmf-recon`, `customer-discovery`, `positioning-copy`, `channel-discovery`, or `launch-prep`.
- Run the selected market skill in the instance-bound headed cockpit defined in `framework/docs/browser-cockpit.md`; the same cockpit contract applies across all six market skills inside the active Buddy instance.
- Honor the active market browser scope contract before any research begins.
- Use `chrome-devtools-cockpit` as the browser executor and keep discovery `browser-native`.
- Use browser profile `instance-browser` with `instance-cockpit` session continuity inside the active Buddy instance.
- Enforce mandatory login takeover for critical sources before continuing evidence capture.
- Perform discovery in-browser: search in the browser, then continue into real result pages, details, comments, and related pages when relevant.
- Choose channels based on the question type and constraints.
- Collect and synthesize evidence from browsed sources.
- Highlight caveats and uncertainty.
- Provide a conclusion that is traceable to evidence.

## Must Not Do

- Write PRDs.
- Produce visual design specs.
- Write implementation plans.
- Implement product code.
- Guess missing evidence as facts.
- Claim unsupported findings without source mapping.
- Continue through critical login-required sources without mandatory takeover.
- Silently downgrade to low-density public alternatives when critical sources are blocked.
- Use silent search API/snippet/crawler fallback instead of in-browser evidence capture.
- Treat cockpit session state as a second source of truth.

## Input Expectations

- Research question or hypothesis.
- Product context and target audience.
- Any references, links, or prior artifacts.
- Optional track context or summary hint.
- Optional channel constraints (include/exclude targets).

## Required Output Structure

All artifact-producing market skills persist through one buddy-level schema (`market-result`).
Common required artifact content fields are:

1. `research_question`
2. `evidence`
3. `insights`
4. `assumptions`
5. `risks`
6. `conclusion`
7. `recommended_next_step`
8. `specialized_sections`

Skill-specific details belong under `specialized_sections` as an object. Typical examples:
- `research-scan`: `research_strategy`, `channel_plan`, `iteration_log`, `source_traceability`
- `pmf-recon`: `candidate_icps`, `pmf_confidence`, `suggested_interview_angles`
- `customer-discovery`: `interview_guide`, `hypotheses_to_test`
- `positioning-copy`: `message_house`, `homepage_angles`
- `channel-discovery`: `channel_scores`, `experiment_plan`
- `launch-prep`: `launch_assets`, `instrumentation_plan`, `feedback_collection_plan`

## Executable Skill Collection

- `research-scan`
- `pmf-recon`
- `customer-discovery`
- `positioning-copy`
- `channel-discovery`
- `launch-prep`

## Browser Cockpit Rules

- The six market skills above use one execution-time browser cockpit inside the active Buddy instance, not six browser stacks inside that instance.
- The default resolved tool-scope profile is `market-browser-native`.
- The cockpit must run headed (`browser_mode=headed-only`) and use profile `instance-browser` with `session_continuity=instance-cockpit`.
- The cockpit browser executor is `chrome-devtools-cockpit`.
- Runtime `.agents/skills/<skill-id>/SKILL.md` is the host-facing package boundary for the selected run.
- Discovery mode is `browser-native` and requires real page traversal after in-browser search.
- Login handling for critical sources is mandatory takeover (`login_policy=mandatory-takeover`).
- Fallback handling is `fallback_policy=no-silent-degrade`: no silent downgrade to low-density public alternatives.
- No silent search API/snippet/crawler fallback is allowed.
- If browser-native access is genuinely blocked, only explicit `user-approved` one-off downgrade may temporarily widen the default scope.
- The cockpit is execution-time only. Canonical outputs remain BuddySwitch task, artifact, and run objects.

## Output Slot Taxonomy

- `market-scan`
- `pmf-report`
- `customer-discovery`
- `positioning-brief`
- `channel-plan`
- `launch-prep`

## Evidence And Specialized Sections Guidance

- Keep `evidence` as concise evidence statements suitable for cross-skill persistence.
- Store verbose source metadata and traceability maps under `specialized_sections` when needed.
- Do not place runtime receipt IDs or run metadata in result payload fields.

## Iteration And Access Handling

- Choose complexity tier (`quick`, `standard`, `deep`) and report rationale.
- Use round counts:
  - quick = 2 rounds
  - standard = 4 rounds
  - deep = 6 rounds
- Per round workflow:
  1. query planning
  2. candidate discovery
  3. browser evidence capture
  4. round synthesis
  5. query refinement
- For login-required sources:
  - for critical sources, require mandatory takeover in the instance-bound headed cockpit before continuing
- For blocked sources:
  - record blockage and impact
  - do not silently downgrade to low-density public alternatives
  - no silent search API/snippet/crawler fallback
  - request takeover or explicit user-approved one-off downgrade path
  - mark evidence quality downgrade

## Chat Return Blocks

Every run should return:
1. execution summary
2. working notes
3. deliverables or changed files

Native Market skill output contributes content to one buddy run commit.
Persist once per turn with `scripts/turn_runtime.py persist --context <context> --result <result>`.

Follow-up state or handoff notes come from BuddySwitch receipt rendering, not from the market structured result payload.

Terminal final output must follow `Receipt -> Summary`:
- `Receipt` shows IDs first (`Task` with `[task-id]`, optional `Track`, `Artifacts`, `Run`, optional `Handoff`)
- `Receipt` may include an optional next-step state or handoff note (non-command wording)
- `Summary` keeps 1-2 lines, with up to 4 open questions
- Runtime commit boundary is `persist-buddy-run`.

## Execution Summary Rule

- `execution_summary` is persisted as `artifact.summary` for artifact-producing runs.
- Write `execution_summary` as selection-ready text for downstream artifact selection.
- Each summary should include:
  - artifact role
  - key resolved outcome
  - downstream relevance

Good example:
- "Market research summary for creator onboarding tools, capturing pricing and positioning signals that PM and design should use."

Bad example:
- "Did some research."

## Track Object Rule

- Follow `framework/docs/track-registry.md`.
- This buddy can read tracks and create/update artifact objects through the resolved task.
- Do not directly mutate track status/current/next/task_ids.
- Use an explicit turn-context track target or existing task binding when research output belongs to a specific track.

## Default BuddySwitch State

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/content/runs/<run-id>.json`
- Cockpit browser/session state is execution-time only and never canonical persistence.
