# AI Reviewer Rubric

Use this for self-review or reviewer-agent review before claiming completion on substantial work.

## Review Questions

### 1. Problem framing
- Does the change target the stated bottleneck?
- Is the claimed problem supported by evidence instead of guesswork?

### 2. Root cause
- Does the fix address the actual cause?
- Is it avoiding symptom-only patches?

### 3. Boundary integrity
- Does the change respect existing contracts, metadata, and layer boundaries?
- Did it avoid solving a generic boundary problem with a buddy-specific or file-local special case?

### 4. Change shape
- Did the change replace, simplify, or delete baggage where possible?
- Did it avoid wrappers, fallback drift, and long-lived compatibility layering?

### 5. Verification quality
- Do the executed tests or inspections actually prove the claimed outcome?
- Was the key path verified, not just adjacent code?

### 6. Scope control
- Did the work stay aligned with the original task?
- Did it avoid unrelated cleanup or speculative redesign?

### 7. Remaining risk
- What is still unverified?
- Is the remaining risk acceptable for this batch, or does it block completion?

## Fail Signals

Treat the review as failed when any of these are true:

- the fix is mainly a symptom patch
- the change adds new compatibility baggage without a hard reason
- verification is missing, weak, or unrelated to the claim
- the implementation crosses boundaries that the analysis did not justify
