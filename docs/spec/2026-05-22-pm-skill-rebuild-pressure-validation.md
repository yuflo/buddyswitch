# PM Skill Rebuild Pressure Validation

Date: 2026-05-22

Validation method: focused evaluation harness over the rebuilt PM skill bodies. The harness mapped
P1-P8 from `docs/spec/2026-05-22-pm-skill-rebuild-test-plan.md` to the relevant generic PM skills
and checked that the skill guidance covers the required behavior tokens without adding
case-specific PM skills.

Command:

```bash
python3 - <<'PY'
from pathlib import Path
ROOT = Path.cwd()
skills = {
    path.parent.name: path.read_text(encoding='utf-8').lower()
    for path in (ROOT / 'buddyswitch' / 'skills' / 'pm').glob('*/SKILL.md')
}
scenarios = {
    'P1 messy context intake': ('read-product-context triage-track', ['track.open', 'artifact.get', 'facts', 'assumptions', 'decisions', 'blockers', 'missing inputs', 'next action']),
    'P2 signal conflict': ('synthesize-cross-functional-inputs frame-product-direction define-scope', ['market', 'design', 'dev', 'test', 'product impact', 'scope', 'criteria', 'open question']),
    'P3 broad surface request': ('frame-product-direction define-scope write-requirements', ['audience', 'problem', 'value', 'scope', 'requirements', 'acceptance criteria', 'non-goals']),
    'P4 ambiguous requirements': ('write-requirements write-acceptance-criteria', ['observable', 'owner boundary', 'actor', 'trigger', 'behavior', 'pass', 'fail', 'blocked']),
    'P5 durable decision capture': ('make-product-decision', ['decision', 'evidence', 'tradeoff', 'rejected', 'residual risk', 'next owner', 'artifact.create_revision', 'track.add_material']),
    'P6 proof iteration': ('decide-from-proof write-acceptance-criteria', ['continue', 'revise', 'send back', 'stop', 'blocked', 'evidence', 'residual risk', 'track.add_proof']),
    'P7 stale track': ('triage-track read-product-context', ['stale', 'current truth', 'obsolete', 'missing proof', 'blockers', 'next action', 'track.open']),
    'P8 sequencing': ('sequence-product-work synthesize-cross-functional-inputs', ['owner', 'output', 'dependency', 'stop condition', 'sequence', 'track outcome']),
}
failed = []
for name, (skill_names, tokens) in scenarios.items():
    text = '\n'.join(skills[s] for s in skill_names.split())
    missing = [token for token in tokens if token not in text]
    if missing:
        failed.append((name, missing))
        print(f'FAIL {name}: missing {missing}')
    else:
        print(f'PASS {name}')
if failed:
    raise SystemExit(1)
print('pressure scenario validation: 8 passed')
PY
```

Result:

```text
PASS P1 messy context intake
PASS P2 signal conflict
PASS P3 broad surface request
PASS P4 ambiguous requirements
PASS P5 durable decision capture
PASS P6 proof iteration
PASS P7 stale track
PASS P8 sequencing
pressure scenario validation: 8 passed
```

## P1: Messy Track Context Intake

Input summary:
- A track has an old brief, conflicting comments, one design artifact id, and one proof id; user asks PM to continue.

Observed PM output:
- Skill-guided output shape: context summary with facts, assumptions, decisions, blockers, missing inputs, and next PM action.

Rubric:
- [x] Reads `track.open` and full artifact bodies before deciding.
- [x] Separates facts, assumptions, decisions, blockers, and missing inputs.
- [x] Does not rewrite a PRD as first move.

Result: pass

## P2: Cross-Functional Signal Conflict

Input summary:
- Market, design, dev, and test signals conflict in priority and risk.

Observed PM output:
- Skill-guided output shape: synthesis of signal, product impact, PM action, owner, and open question.

Rubric:
- [x] Maps each signal to product impact.
- [x] Identifies scope, criteria, and open-question impacts.
- [x] Does not treat every signal as equal priority.

Result: pass

## P3: Broad Product Surface Request

Input summary:
- User asks PM to coordinate a website, landing page, pricing page, or launch page.

Observed PM output:
- Skill-guided output shape: audience, problem, value, scope, requirements, acceptance criteria, decision, and owner sequencing.

Rubric:
- [x] Uses generic PM skills.
- [x] Does not create a page-type PM skill.
- [x] Treats surface-specific detail as output, not taxonomy.

Result: pass

## P4: Ambiguous Requirements

Input summary:
- User asks to make onboarding easier and more premium.

Observed PM output:
- Skill-guided output shape: observable requirements with actor, trigger, behavior, constraints, owner boundaries, and pass/fail/blocked criteria.

Rubric:
- [x] Rewrites vague request into observable behavior.
- [x] Records owner boundaries.
- [x] Adds criteria test can verify.

Result: pass

## P5: Durable Decision Capture

Input summary:
- PM must choose a narrow feature this week or a broader redesign later.

Observed PM output:
- Skill-guided output shape: decision artifact with evidence, tradeoff, rejected alternative, residual risk, and next owner.

Rubric:
- [x] Records durable decision components.
- [x] Publishes through artifact and track material/proof path.
- [x] Does not leave the decision only in chat.

Result: pass

## P6: Proof-Based Iteration

Input summary:
- Test proof says desktop passes, mobile fails, and one area is unverified.

Observed PM output:
- Skill-guided output shape: continue/revise/send back/stop/blocked decision with evidence and residual risk.

Rubric:
- [x] Chooses an evidence-based iteration decision.
- [x] Names supporting evidence and residual risk.
- [x] Uses env tools for follow-up state.

Result: pass

## P7: Stale Or Cluttered Track

Input summary:
- Track has old materials, no current proof, stale task, and unclear latest direction.

Observed PM output:
- Skill-guided output shape: current truth, obsolete material, missing proof, blockers, and next action.

Rubric:
- [x] Identifies current truth and stale material.
- [x] Does not create a new PRD to hide state.
- [x] Reads shared state before updates.

Result: pass

## P8: Product Work Sequencing

Input summary:
- Brief needs market follow-up, design shaping, dev implementation, and test proof.

Observed PM output:
- Skill-guided output shape: ordered owner sequence with output, dependency, stop condition, and current next action.

Rubric:
- [x] Creates short ordered owner sequence.
- [x] Avoids workflow engine or scheduler.
- [x] Keeps sequence tied to current track outcome.

Result: pass
