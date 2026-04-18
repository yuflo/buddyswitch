# Market Declarative Tool Scoping Manual Checklist

## Preconditions

1. Run `./buddyswitch-codex start`.
2. Confirm `chrome-devtools-cockpit` is available in the active session.

## Case 1: Broad scan

Command:

```text
switch market: Research demand for AI companion live spaces
```

Check:

- Choose `research-scan`.
- `prepare-execution` returns `selected_skill_packet.tool_scope.profile = "market-browser-native"`.
- The host starts with `chrome-devtools-cockpit`.

## Case 2: PMF validation

Command:

```text
switch market: Validate whether an AI note-taking tool for consultants has enough PMF signal to test
```

Check:

- Choose `pmf-recon`.
- `prepare-execution` returns the same `tool_scope`.
- Browser-external search is not used unless an explicit `user-approved` one-off downgrade is requested.

## Case 3: Positioning from upstream artifacts

Command:

```text
switch market -> track-ai-note: Turn the PMF findings into founder-facing homepage positioning
```

Check:

- Choose `positioning-copy`.
- `prepare-execution` returns selected inputs plus the same `tool_scope`.
- The host still starts from the browser-native scope before any downgrade path.
