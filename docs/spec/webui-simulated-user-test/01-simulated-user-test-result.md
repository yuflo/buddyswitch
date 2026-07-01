# WebUI Simulated User Test Result

## Summary

Result: **Partial / blocked by actor creation failure**

The rebuilt WebUI could be opened and operated in the browser. The Team Room and Track Studio visual structure matched the intended rebuilt shell at the tested desktop and narrow widths, with no old shell terms, fake visual data, or horizontal overflow found in the checked states.

However, the core simulated user path failed at actor creation. Creating `dev`, `pm`, and `test` teammates through the browser all returned `502 COMMAND_FAILED` with message `Preparing worktree (detached HEAD 8c138a6)`. Because no actor could be created, the test could not honestly execute direct message send, actor switching, or lifecycle controls beyond disabled-state inspection.

## Artifacts

- Plan: `docs/spec/webui-simulated-user-test/00-simulated-user-test-plan.md`
- Browser observations: `docs/spec/webui-simulated-user-test/browser-observations.md`
- Server log: `docs/spec/webui-simulated-user-test/webui-server-log.txt`
- Desktop Team Room screenshot: `docs/spec/webui-simulated-user-test/team-room-desktop.png`
- Mobile Team Room screenshot: `docs/spec/webui-simulated-user-test/team-room-mobile.png`
- Mobile Tracks screenshot: `docs/spec/webui-simulated-user-test/tracks-mobile.png`

## Scenario Results

| Scenario | Result | Evidence |
| --- | --- | --- |
| A. First Arrival And Empty State | Pass | Browser loaded `/`, Team Room was first screen, tabs were `Team room` and `Tracks`, initial API fetches were 200, no console messages, no old/fake terms, no desktop overflow. |
| B. Create Dev And Send Direct Message | Fail / blocked | Browser `POST /api/instances` with `{"role":"dev"}` returned 502 `COMMAND_FAILED`. No actor appeared, so message send could not be performed. |
| C. Create PM/Test And Rapid Switch | Fail / blocked | Browser `POST /api/instances` with `{"role":"pm"}` and `{"role":"test"}` both returned the same 502. No People rows existed to switch. |
| D. Lifecycle Controls | Blocked | No actor existed. Buttons correctly stayed disabled; `Clear disabled: Select an actor.` was visible. Open TUI/Clear/Stop/Resume/Delete could not be exercised on a real actor. |
| E. Tracks Tab / Studio Read View | Pass for empty state | Browser opened Tracks, showed read-only Track Studio empty state, no write controls in `#track-view`, no old/write terms, no overflow. |
| F. Responsiveness And Interaction Smoothness | Pass for available states | Effective narrow width was 500px; Team Room and Tracks became single-column, no overflow elements found, sections remained reachable. |

## Defects And Findings

### P0: Actor creation fails for all tested roles

Severity: **High / core flow blocker**

Browser evidence:

```http
POST /api/instances {"role":"dev"}  -> 502 COMMAND_FAILED
POST /api/instances {"role":"pm"}   -> 502 COMMAND_FAILED
POST /api/instances {"role":"test"} -> 502 COMMAND_FAILED
```

Response message for all roles:

```text
Preparing worktree (detached HEAD 8c138a6)
```

Impact:

- User cannot start teammates from WebUI.
- Direct thread cannot be used with a real teammate.
- Actor switching cannot be tested or used.
- Lifecycle controls cannot be tested or used on created actors.

Likely area:

- Web management `_create_instance` command boundary or underlying instance-start command error handling.
- The response message looks like a command progress line being treated as the failure message, so the actual underlying failure may be hidden from the WebUI user and from `webui-server-log.txt`.

### P1: Long pending create state lacks clear visible progress copy

Severity: **Medium**

Observed:

- Start button disabled while the request was pending for roughly 35 seconds.
- The UI did not show a clear `Starting teammate...` or role-specific progress message near the Start panel.
- After failure, the backend error appeared in the right Actions message area, not close to the Start teammate panel.

Impact:

- User may not understand whether Start is working, stuck, or failed.

### P1: Server log does not contain failed request detail

Severity: **Medium**

Observed:

- Captured server log only contained startup line:

  ```text
  BuddySwitch web management listening on http://127.0.0.1:8767
  ```

- No request summary, command error detail, traceback, or command stderr for the three 502 failures.

Impact:

- Browser network panel had the only actionable failure evidence.
- Log-based operational diagnosis is weak for the WebUI actor creation path.

## Positive Observations

- Initial API boot path succeeded: health, roles, actors, tracks, and IM session all returned 200.
- The rebuilt visual shell is present in the browser: Team Room left rail, Direct thread center, selected teammate card right.
- Old visible shell terms and fake data were absent in tested states.
- Tracks is read-only in the UI and did not expose comment/write controls.
- Desktop and narrow layouts had no horizontal overflow in tested states.
- Disabled action reasons are at least partially clear when no actor is selected.

## Cleanup Result

- No test actors were created, so no actor deletion was required.
- WebUI server shutdown was performed after result recording.
- Port cleanup check is recorded in the final assistant verification, not inside this file.

## Recommendation

Fix the actor creation command failure first. It is the current bottleneck because it blocks the main Team Room product loop and prevents meaningful user testing of direct thread, actor switching, TUI, and lifecycle controls.

After that fix, rerun this same plan and require the previously blocked scenarios B, C, and D to complete through the browser before considering the WebUI interaction experience verified.
