# Merge Plan: fea-daemon and fea-webui Into main

Date: 2026-05-31
Target branch: `main`
Branches:

- `fea-daemon` at `6cd6629`
- `fea-webui` at `a949d48`
- `main` / `origin/main` at `4e51a41` before merge

## Goal

Merge both feature branches into `main`, resolve conflicts, run verification, review the final state, and push `main` to `origin/main`.

## Pre-Merge Findings

- `fea-daemon -> main` simulated cleanly.
- `fea-webui -> main` conflicts in one file: `tests/test_buddyswitch_launcher.py`.
- The conflict is limited to `test_start_with_buddy_allocates_next_browser_port_when_default_is_busy`.
- Web management / open TUI files changed only on `fea-webui`; `fea-daemon` does not touch those paths.

## Merge Order

1. Merge `fea-daemon` into `main`.
2. Merge `fea-webui` into `main`.
3. Resolve the expected `tests/test_buddyswitch_launcher.py` conflict.

## Conflict Resolution Intent

For the browser port allocation test, keep the more flexible port discovery from `fea-webui` while preserving the stricter cockpit proxy registration assertion from `fea-daemon` / `main`.

Expected resolved shape:

```python
expected_port = self._first_available_browser_port()
if expected_port is None:
    self.skipTest("no browser cockpit port is available in range 9222..9321")

self.assertEqual(instance_json["browser_port"], expected_port)
self._assert_cockpit_proxy_registration(cockpit_add["argv"], f"http://127.0.0.1:{expected_port}")
```

## Verification

Run the full suite after the merge:

```bash
python3 -m pytest -q
```

Then check for launcher/runtime process residue:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

## Completion

Completion requires:

- both feature branches are merged into `main`;
- the merge plan is committed;
- full tests pass;
- process residue check is clean;
- `main` is pushed to `origin/main`.
