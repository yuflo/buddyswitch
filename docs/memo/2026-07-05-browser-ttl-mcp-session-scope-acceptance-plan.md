# Browser TTL MCP Session Scope Acceptance Plan

Date: 2026-07-05

## 1. Acceptance Contract

The product contract to prove is:

```text
actor uses chrome-devtools-cockpit to open a real browser page
-> BuddySwitch TTL expires that page
-> TTL cleanup closes the actual page through chrome-devtools-mcp
-> browser release reclaims owned resources
-> host has no actor-owned browser process residue
```

Passing unit tests alone are not enough. This acceptance plan must prove the full loop with a real CLI actor instance.

## 2. Preflight

Start from a clean worktree:

```bash
git status --short --branch
```

Expected:

```text
## fea-tool...origin/fea-tool
```

Confirm TTL config:

```bash
rg -n 'BROWSER_PAGE_IDLE_SECONDS|BROWSER_COCKPIT_RELEASE_DELAY_SECONDS' scripts/env/cdp_browser_lifecycle.py
```

Expected:

```text
BROWSER_PAGE_IDLE_SECONDS = 40
BROWSER_COCKPIT_RELEASE_DELAY_SECONDS = 10
```

Run focused automated tests before the real actor test:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_page_expired_handler.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_cockpit_proxy.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_cdp_browser_session.py tests/test_browser_page_expired_handler.py tests/test_browser_lazy_release_integration.py tests/test_repo_consistency.py
```

Expected:

```text
all tests pass
```

## 3. Real CLI Actor Test Setup

Use an isolated shared root so cleanup is safe:

```bash
RUN_ROOT="$(mktemp -d /tmp/buddyswitch-ttl-mcp-scope.XXXXXX)"
BUDDYSWITCH_SHARED_ROOT="$RUN_ROOT" ./buddyswitch-codex instance start --role market --json > /tmp/buddyswitch-ttl-mcp-scope-start.json
ACTOR_ID="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('/tmp/buddyswitch-ttl-mcp-scope-start.json').read_text())['actor_id'])
PY
)"
INSTANCE_DIR="$RUN_ROOT/instances/$ACTOR_ID"
```

Record the actor id and root in the final result.

## 4. Actor Browser Flow

Send this exact CLI input:

```bash
BUDDYSWITCH_SHARED_ROOT="$RUN_ROOT" ./buddyswitch-codex instance input "$ACTOR_ID" --text '请只使用 chrome-devtools-cockpit，不要调用 search.open_browser、search__open_browser、search 工具或 native web search。请只做两步：1. 调用 chrome-devtools-cockpit.search_page，query 为 "BuddySwitch TTL MCP pageId scope acceptance"，engine 为 google；2. 调用 chrome-devtools-cockpit.list_pages。最后回复 opened pageId、URL、title，以及 BuddySwitch projection 中 current_page_id/selected_page_id。不要调用 select_page、take_snapshot、close_page。' --json > /tmp/buddyswitch-ttl-mcp-scope-input.json
```

Poll until task sys has no active tasks:

```bash
for i in $(seq 1 30); do
  BUDDYSWITCH_SHARED_ROOT="$RUN_ROOT" ./buddyswitch-codex instance status "$ACTOR_ID" --json > /tmp/buddyswitch-ttl-mcp-scope-status-poll.json 2>/tmp/buddyswitch-ttl-mcp-scope-status-poll.stderr || true
  python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('/tmp/buddyswitch-ttl-mcp-scope-status-poll.json').read_text())
by_status = (((data.get('daemon') or {}).get('task_sys') or {}).get('by_status') or {})
print(data.get('status'), (data.get('thread') or {}).get('status'), data.get('browser_port'), by_status)
raise SystemExit(0 if not by_status else 1)
PY
  if [ $? -eq 0 ]; then break; fi
  sleep 5
done
```

Capture initial evidence:

```bash
BUDDYSWITCH_SHARED_ROOT="$RUN_ROOT" ./buddyswitch-codex instance status "$ACTOR_ID" --json > /tmp/buddyswitch-ttl-mcp-scope-status-after-open.json
cp "$INSTANCE_DIR/runtime/browser/page_idle.json" /tmp/buddyswitch-ttl-mcp-scope-page-idle-after-open.json
BROWSER_PORT="$(python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('/tmp/buddyswitch-ttl-mcp-scope-status-after-open.json').read_text())
print(data['browser_port'])
PY
)"
curl -fsS "http://127.0.0.1:$BROWSER_PORT/json/list" > /tmp/buddyswitch-ttl-mcp-scope-cdp-after-open.json
```

Expected after open:

```text
page_idle.json contains one tracked Google search page
current_page_id == selected_page_id
Chrome /json/list contains the same Google URL plus about:blank
```

## 5. TTL And Release Verification

Wait beyond TTL plus release delay:

```bash
sleep 65
```

Capture post-TTL evidence:

```bash
BUDDYSWITCH_SHARED_ROOT="$RUN_ROOT" ./buddyswitch-codex instance status "$ACTOR_ID" --json > /tmp/buddyswitch-ttl-mcp-scope-status-after-ttl.json 2>/tmp/buddyswitch-ttl-mcp-scope-status-after-ttl.stderr || true
if [ -f "$INSTANCE_DIR/runtime/browser/page_idle.json" ]; then
  cp "$INSTANCE_DIR/runtime/browser/page_idle.json" /tmp/buddyswitch-ttl-mcp-scope-page-idle-after-ttl.json
fi
if [ -n "${BROWSER_PORT:-}" ]; then
  curl -fsS "http://127.0.0.1:$BROWSER_PORT/json/list" > /tmp/buddyswitch-ttl-mcp-scope-cdp-after-ttl.json || true
fi
cp "$INSTANCE_DIR/runtime/daemon/state.json" /tmp/buddyswitch-ttl-mcp-scope-daemon-state-after-ttl.json
tail -n 240 "$INSTANCE_DIR/runtime/daemon/daemon.log" > /tmp/buddyswitch-ttl-mcp-scope-daemon-tail-after-ttl.log
ps -axo pid,pgid,command | rg "$RUN_ROOT|$ACTOR_ID|--remote-debugging-port=|chrome-devtools-mcp" > /tmp/buddyswitch-ttl-mcp-scope-processes-after-ttl.txt || true
```

Expected post-TTL status:

```text
browser.page.expired delivered and handled
browser.cockpit.release delivered and handled
browser_port is null
page_idle.json is absent or has pages: {}
Chrome /json/list for the old port is unreachable, or contains no actor-owned Google page
daemon log does not contain Browser cockpit release skipped: real_user_page_present for the final release
```

Expected process state:

```text
no actor-owned Google Chrome process remains
no actor-owned chrome-devtools-mcp process remains
no actor-owned telemetry watchdog remains
```

## 6. Negative Regression Evidence

Inspect post-TTL evidence for the old failure:

```bash
python3 - <<'PY'
import json
from pathlib import Path

status = json.loads(Path('/tmp/buddyswitch-ttl-mcp-scope-status-after-ttl.json').read_text())
print('browser_port', status.get('browser_port'))

daemon = status.get('daemon') or {}
schedules = ((daemon.get('schedules') or {}).get('items') or {})
for sid, item in schedules.items():
    if item.get('type') in {'browser.page.expired', 'browser.cockpit.release'}:
        print(sid, item.get('type'), item.get('status'), item.get('last_error'), (item.get('dispatch_result') or {}).get('handling_status'))

log = Path('/tmp/buddyswitch-ttl-mcp-scope-daemon-tail-after-ttl.log').read_text(errors='replace')
print('real_user_page_present' in log)

cdp_path = Path('/tmp/buddyswitch-ttl-mcp-scope-cdp-after-ttl.json')
if cdp_path.exists() and cdp_path.stat().st_size:
    try:
        pages = json.loads(cdp_path.read_text())
    except Exception:
        pages = []
    print([page.get('url') for page in pages if isinstance(page, dict)])
PY
```

Failure if any of these are true:

```text
browser_port remains non-null after release
page_idle.json is cleared but old Google URL is still visible in /json/list
daemon log shows final release skipped with real_user_page_present
actor-owned Chrome or MCP process remains after TTL release
browser.page.expired failed without retry/diagnostic clarity
```

## 7. Explicit Cleanup

Always clean the actor:

```bash
BUDDYSWITCH_SHARED_ROOT="$RUN_ROOT" ./buddyswitch-codex instance stop "$ACTOR_ID" --json > /tmp/buddyswitch-ttl-mcp-scope-stop.json 2>/tmp/buddyswitch-ttl-mcp-scope-stop.stderr || true
BUDDYSWITCH_SHARED_ROOT="$RUN_ROOT" ./buddyswitch-codex instance delete "$ACTOR_ID" --yes --json > /tmp/buddyswitch-ttl-mcp-scope-delete.json 2>/tmp/buddyswitch-ttl-mcp-scope-delete.stderr || true
ps -axo pid,pgid,command | rg "$RUN_ROOT|$ACTOR_ID" > /tmp/buddyswitch-ttl-mcp-scope-processes-after-delete.txt || true
rm -rf "$RUN_ROOT"
ps -axo pid,pgid,command | rg "$RUN_ROOT|$ACTOR_ID" > /tmp/buddyswitch-ttl-mcp-scope-processes-after-root-remove.txt || true
```

Expected:

```text
stop returns inactive
delete returns deleted true
process scans are empty
isolated shared root is removed
```

If actor-owned telemetry watchdog remains after stop/delete, manually kill it and report that as a remaining cleanup defect.

## 8. Acceptance Result Format

Final acceptance report must include:

- actor id;
- commit sha;
- test commands and pass counts;
- opened URL;
- open-time `page_idle.json` summary;
- post-TTL daemon schedule summary;
- post-TTL browser_port value;
- post-TTL `/json/list` result or connection failure;
- post-TTL process scan result;
- stop/delete cleanup result;
- whether any manual kill was required.

## 9. Pass Criteria

The rebuild passes only if:

```text
automated focused tests pass
broader browser/resource tests pass
real actor opens page through chrome-devtools-cockpit
TTL closes the actual page, not only the BuddySwitch projection
browser release clears browser_port
host process scan returns to baseline
no manual cleanup is required
```

If the behavior works only after manual `chrome-devtools-cockpit.close_page`, the rebuild fails.
