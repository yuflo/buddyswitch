---
name: handle-review-feedback
description: Use when Dev must evaluate and address technical review feedback on an active change.
---

# Handle Review Feedback

## Purpose
- Convert review feedback into technically sound follow-up actions instead of performative agreement.

## Use when
- Review comments, requested changes, or inline feedback need evaluation and response.

## Do not use when
- There is no concrete feedback to process.

## Inputs
- Review feedback, requirements, changed files, and current verification evidence.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" -m buddyswitch.application.entrypoints.diagnostics status`.

## Steps
1. Read the feedback fully before touching code.
2. If the feedback is unclear or bundles multiple ideas, stop and clarify.
3. Verify the feedback against codebase reality, requirements, and current behavior.
4. Evaluate whether the suggestion is technically correct for this codebase.
5. Push back with technical reasoning when the feedback is wrong, over-scoped, or violates YAGNI.
6. Implement one item at a time and run focused verification for that item.
7. Report what changed, what was rejected, and why.

## Outputs
- Reviewed feedback disposition with changes, pushback, and focused verification evidence.

## Guardrails
- Do not blindly implement feedback.
- Do not agree just to look cooperative.
- Do not batch unrelated comments into one opaque patch.

## Stop Conditions
- Feedback remains unclear after clarification or changes product meaning beyond the approved scope.

## Verification
- Each accepted item has focused verification and each rejected item has explicit reasoning.

## Examples
- Reviewer suggests a simpler null guard; Dev verifies the code path, applies one item, and proves it with a focused test.

## Counterexamples
- Dev applies every comment at once without checking whether the advice fits the codebase.
