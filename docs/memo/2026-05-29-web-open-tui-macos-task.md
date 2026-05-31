# Web Open TUI macOS Task

Date: 2026-05-29
Status: aligned task memo after product and boundary discussion
Owner perspective: Web Management UI and Web API

## Core Task

给 BuddySwitch Web 管理页增加一个简洁的一键打开 TUI 体验：

```text
User clicks Open TUI in Web Management
-> Web API validates the selected instance
-> Web API asks macOS Terminal.app to open
-> Terminal.app runs the existing launcher attach command
-> user enters the Codex TUI for that buddy instance
```

The command executed in Terminal remains the existing stable launcher command:

```bash
./buddyswitch-codex instance attach <instance-id>
```

This task is a Web Management product-experience enhancement. It is not a launcher API expansion task.

## Product Experience

The UI should stay simple, clean, and CTA-focused.

Preferred first version:

- Add an `Open TUI` CTA in the selected instance action area.
- Every instance can be opened by selecting it, then clicking `Open TUI`.
- Do not introduce a new page, wizard, complex modal, terminal selector, or multi-step explanation.
- Keep the current Notion-like local control console style.
- Use restrained spacing, clear button hierarchy, and short status copy.

Button states:

- Active, healthy, thread present: `Open TUI` is enabled.
- Clicked: show `Opening...`.
- Success: show `Terminal opened.`
- Inactive: disable and show `Resume this instance first.`
- Unhealthy: disable and show `Instance is unhealthy.`
- Missing thread: disable and show `No thread to attach.`
- Failure: show `Could not open Terminal.` and expose `Copy command` fallback.

Fallback command should be easy to copy, ideally absolute-context safe:

```bash
cd <repo-root> && ./buddyswitch-codex instance attach <instance-id>
```

## Design Direction

Use the frontend design skills conservatively:

- `design-taste-frontend`: keep the operational console clear, quiet, and non-marketing.
- `high-end-visual-design`: borrow only CTA polish, spacing, and micro-interaction restraint.

Do not apply heavy visual effects, glassmorphism, cinematic motion, large decorative cards, or extra onboarding content. This is a local operations console, not a landing page.

The CTA should feel obvious and useful, but it should not compete with the main `Send` action or lifecycle controls.

## Boundary Decision

Keep this capability fully inside the Web Management layer.

Do not add:

```bash
./buddyswitch-codex instance attach-open <instance-id> --json
```

Rationale:

- `instance attach <id>` is already the launcher-owned core capability.
- Opening Terminal.app is a Web Management desktop-experience action, not a general launcher lifecycle primitive.
- Adding `attach-open` would make the launcher carry UI-specific behavior.
- Keeping the terminal opener in Web API avoids leaking this application-specific macOS interaction into the public launcher surface.

Final boundary:

```text
launcher
  owns: instance attach <id>
  does not own: opening macOS Terminal.app from Web

web_management.py
  owns: POST /api/instances/<id>/open-tui
  owns: macOS-only Terminal.app opener
  reuses: existing ./buddyswitch-codex instance attach <id>

frontend
  owns: Open TUI CTA, state display, fallback copy command
```

## API Shape

Add a Web Management route:

```http
POST /api/instances/<instance-id>/open-tui
```

Expected behavior:

1. Validate `instance-id` with the same existing instance id validation.
2. Fetch or inspect instance status.
3. Reject clearly invalid open attempts before touching Terminal:
   - inactive instance;
   - unhealthy app-server;
   - missing thread id;
   - unsupported operating system.
4. On macOS, call `osascript` to ask Terminal.app to run the existing attach command.
5. Return a structured JSON result.

Important: API success only means "Terminal open request was issued." It cannot guarantee that the Codex TUI successfully attached after Terminal starts. Attach failures belong in the Terminal session and should also be recoverable through the copy-command fallback.

Suggested response fields:

```json
{
  "ok": true,
  "instance_id": "inst-pm-example",
  "command": "cd ... && ./buddyswitch-codex instance attach inst-pm-example",
  "terminal": "Terminal.app"
}
```

## macOS Terminal Opener

Use a macOS-only AppleScript implementation through `osascript`.

Use Terminal.app directly:

```applescript
tell application "Terminal"
  activate
  do script "<quoted attach command>"
end tell
```

Implementation notes:

- Do not use `System Events`.
- Do not simulate keystrokes.
- Do not depend on iTerm or custom terminal preferences.
- Do not support Linux or Windows in this task.
- Prefer opening a new command session rather than hijacking a user's current terminal prompt.
- Quote both shell command content and AppleScript string content carefully.
- Validate the instance id before command construction.

Known reliability boundary:

- Reliable for an interactive macOS GUI user session.
- First use may trigger a macOS Automation / Apple Events permission prompt.
- If the permission is denied, return a visible Web error and offer `Copy command`.
- Headless, SSH-only, LaunchDaemon, or non-GUI environments are unsupported.

## Security And Safety Notes

This route is more sensitive than normal Web Management actions because it launches a local application.

Required protections:

- Keep Web Management bound to local hosts only.
- Require `POST`, not `GET`.
- Require `Content-Type: application/json`.
- Require a custom same-origin header such as `X-BuddySwitch-Web: 1`.
- Check `Origin` / `Host` where practical so random websites cannot trivially trigger localhost terminal opens.
- Do not accept arbitrary commands from the browser.
- Construct the command server-side from the validated repo root and instance id.

The custom header is not a full authentication system. It is a pragmatic CSRF barrier for a localhost-only development tool. A future stronger version can inject a per-server nonce into the served HTML if this action becomes more sensitive or widely distributed.

## Testing Expectations

Automated tests should not open a real Terminal window.

Cover:

- Web API route exists and delegates to a fake terminal opener.
- Unsupported OS returns a structured error.
- Invalid instance id is rejected before opener invocation.
- Inactive, unhealthy, or missing-thread instances do not invoke opener.
- Success response includes the copyable attach command.
- Frontend state helper enables `Open TUI` only for active, healthy instances with a thread id.
- Frontend contract test includes the `open-tui` CTA id and route string.

Manual verification on macOS:

1. Start Web Management locally.
2. Start or select an active healthy buddy instance.
3. Click `Open TUI`.
4. Confirm Terminal.app opens and runs `./buddyswitch-codex instance attach <id>`.
5. Confirm failed/denied Automation permission shows a clear Web error and copy fallback.

## Non-Goals

Do not:

- add a launcher `attach-open` command;
- change existing `instance attach` behavior;
- modify daemon, runtime broker, app-server transport, or task runtime;
- add cross-platform terminal support;
- add terminal choice settings;
- build a modal flow or new management page;
- add speculative plugin or opener abstraction beyond the minimum test seam.

## Definition Of Done

The task is done when:

- Web Management exposes a minimal `Open TUI` CTA for the selected instance.
- The CTA launches macOS Terminal.app through Web API only.
- The terminal runs the existing `./buddyswitch-codex instance attach <instance-id>` path.
- Launcher public command surface remains unchanged.
- Invalid states are blocked before opening Terminal.
- Failure gives a clear message and copy-command fallback.
- Automated tests cover API routing, state gating, and no-real-terminal behavior.
- Manual macOS verification confirms the main path.
