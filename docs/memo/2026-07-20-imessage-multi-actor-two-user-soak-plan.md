# iMessage Multi-Actor × Two-User Soak Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute one bounded real iMessage soak in which two consenting external users each complete three short text-generation rounds with two healthy actors, then prove routing, uniqueness, Central-event order, bridge latency, ACK, and cleanup.

**Architecture:** Make no executable change. Run the committed `fea-im` Web/iMessage worker as the only `imsg watch` owner, guide exact tokenized user messages, and correlate existing Central IM message/event records with iMessage state links and Messages DB rows. Treat actor generation time and iMessage bridge time as separate measurements.

**Tech Stack:** Existing BuddySwitch launcher, two current market actors, External IM/Central IM persisted records, `imsg`, macOS Messages DB, JSON iMessage channel state, `jq`, `sqlite3`, and user-visible device confirmation.

---

Source design: `docs/memo/2026-07-20-imessage-multi-actor-two-user-soak-design.md`

Write scope: the source design gains one execution-evidence section after the
soak. No production source, test, runtime contract, or schema is modified.

## Task 0: Freeze Source And Runtime Preconditions

**Files:** none

- [ ] **Step 1: Record the frozen repository identity**

```bash
git status --short
git rev-parse HEAD
```

Expected: clean worktree at or after the committed design; no unrelated changes.

- [ ] **Step 2: Prove actors and authorized contacts are ready**

```bash
./buddyswitch-codex instance list --role market
jq '{contacts:[.contacts|to_entries[]|select(.key=="sender:yuflo2024@126.com" or .key=="sender:hblouis@126.com")|{key:.key,identity:.value.external_identity_id,chat_id:.value.route.chat_id,retry:.value.outbound_retry,failure:.value.last_delivery_failure}]}' \
  /Users/chen/.codex-buddyswitch/state/buddyswitch/local/imessage-channel/state.json
```

Expected: `act-market-645c3ea1fe37` and `act-market-8164b055c113` are active and
healthy; both authorized contacts have routes and no retry/failure state.

- [ ] **Step 3: Start and prove the only current iMessage worker**

Run from `/Users/chen/Dev/buddyswitch/.worktrees/fea-im` in one owned PTY:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

Then probe:

```bash
curl -fsS http://127.0.0.1:8765/api/health
lsof -nP -iTCP:8765 -sTCP:LISTEN
ps -axo command | rg "imsg watch --json" | rg -v "rg "
```

Expected: health succeeds, the listener comes from `fea-im`, and exactly one
`imsg watch --json` process exists.

## Task 1: Round 1 — Staggered Baseline

**Files:** none

- [ ] **Step 1: Contact C sends these messages five seconds apart**

```text
@act-market-645c3ea1fe37 [SOAK-R1-C-M1] 这是纯文本生成任务，不浏览或调用外部工具。为“夏日午后”生成一个8字内标题。只回复一行，格式：[SOAK-R1-C-M1] <答案>
```

```text
@act-market-8164b055c113 [SOAK-R1-C-M2] 这是纯文本生成任务，不浏览或调用外部工具。为“夏日午后”生成一个8字内标题。只回复一行，格式：[SOAK-R1-C-M2] <答案>
```

- [ ] **Step 2: Wait for both C tokens; stop on anomaly**

Expected: each actor produces one one-line reply carrying its exact token in
Contact C's chat. Do not send replacements for missing, duplicate, or misrouted
responses.

- [ ] **Step 3: Contact B sends these messages five seconds apart**

```text
@act-market-645c3ea1fe37 [SOAK-R1-B-M1] 这是纯文本生成任务，不浏览或调用外部工具。为“夏日午后”生成一个8字内标题。只回复一行，格式：[SOAK-R1-B-M1] <答案>
```

```text
@act-market-8164b055c113 [SOAK-R1-B-M2] 这是纯文本生成任务，不浏览或调用外部工具。为“夏日午后”生成一个8字内标题。只回复一行，格式：[SOAK-R1-B-M2] <答案>
```

- [ ] **Step 4: Wait for both B tokens; stop on anomaly**

Expected: four Round-1 request tokens each have exactly one visible reply in the
originating chat.

## Task 2: Round 2 — Concurrent Rewrite

**Files:** none

- [ ] **Step 1: Both users begin together and send M1 then M2 within fifteen seconds**

Contact C sends:

```text
@act-market-645c3ea1fe37 [SOAK-R2-C-M1] 这是纯文本生成任务，不浏览或调用外部工具。把“今天适合散步和喝茶”改写成10字内短句。只回复一行，格式：[SOAK-R2-C-M1] <答案>
```

```text
@act-market-8164b055c113 [SOAK-R2-C-M2] 这是纯文本生成任务，不浏览或调用外部工具。把“今天适合散步和喝茶”改写成10字内短句。只回复一行，格式：[SOAK-R2-C-M2] <答案>
```

Contact B sends:

```text
@act-market-645c3ea1fe37 [SOAK-R2-B-M1] 这是纯文本生成任务，不浏览或调用外部工具。把“今天适合散步和喝茶”改写成10字内短句。只回复一行，格式：[SOAK-R2-B-M1] <答案>
```

```text
@act-market-8164b055c113 [SOAK-R2-B-M2] 这是纯文本生成任务，不浏览或调用外部工具。把“今天适合散步和喝茶”改写成10字内短句。只回复一行，格式：[SOAK-R2-B-M2] <答案>
```

- [ ] **Step 2: Wait for all four Round-2 tokens; stop on anomaly**

Expected: each user sees one reply from each addressed actor, with no token in
the other user's chat.

## Task 3: Round 3 — Concurrent Reversed Actor Order

**Files:** none

- [ ] **Step 1: Both users begin together and send M2 then M1 within fifteen seconds**

Contact C sends M2 first:

```text
@act-market-8164b055c113 [SOAK-R3-C-M2] 这是纯文本生成任务，不浏览或调用外部工具。生成3个表示“轻松”的词，用/分隔。只回复一行，格式：[SOAK-R3-C-M2] <答案>
```

Then C sends M1:

```text
@act-market-645c3ea1fe37 [SOAK-R3-C-M1] 这是纯文本生成任务，不浏览或调用外部工具。生成3个表示“轻松”的词，用/分隔。只回复一行，格式：[SOAK-R3-C-M1] <答案>
```

Contact B sends M2 first:

```text
@act-market-8164b055c113 [SOAK-R3-B-M2] 这是纯文本生成任务，不浏览或调用外部工具。生成3个表示“轻松”的词，用/分隔。只回复一行，格式：[SOAK-R3-B-M2] <答案>
```

Then B sends M1:

```text
@act-market-645c3ea1fe37 [SOAK-R3-B-M1] 这是纯文本生成任务，不浏览或调用外部工具。生成3个表示“轻松”的词，用/分隔。只回复一行，格式：[SOAK-R3-B-M1] <答案>
```

- [ ] **Step 2: Wait for all four Round-3 tokens; stop on anomaly**

Expected: reversed actor submission remains correctly attributed and isolated;
the full soak now has 12 unique visible replies.

## Task 4: Correlate Product Evidence

**Files:** none

- [ ] **Step 1: Generate one exact correlation report**

Run this read-only probe with the normal runtime roots. It discovers all 12 tokens,
Central reply messages/events, persisted event/GUID links, inbound and outbound DB
rows, and both duration classes without a fixed ID list:

```bash
BUDDYSWITCH_SHARED_ROOT=/Users/chen/.codex-buddyswitch \
BUDDYSWITCH_STATE_ROOT=/Users/chen/.codex-buddyswitch/state \
PYTHONPATH="$(pwd)/scripts:$(pwd)/tools/launcher" \
/Users/chen/miniconda3/bin/python - <<'PY'
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sqlite3

from env.repos import messages

TOKEN = re.compile(r"\[SOAK-R(?P<round>[123])-(?P<user>[CB])-(?P<actor>M[12])\]")
STATE = Path("/Users/chen/.codex-buddyswitch/state/buddyswitch/local/imessage-channel/state.json")
DB = Path.home() / "Library" / "Messages" / "chat.db"
APPLE_EPOCH_UNIX = 978_307_200.0
ACTORS = {
    "M1": "act-market-645c3ea1fe37",
    "M2": "act-market-8164b055c113",
}
EXTERNALS = {
    "C": "ext-548aad2fe42d",
    "B": "ext-47a3f3a23828",
}
EXPECTED_TOKENS = {
    f"[SOAK-R{round_number}-{user}-{actor}]"
    for round_number in range(1, 4)
    for user in EXTERNALS
    for actor in ACTORS
}

def iso_unix(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()

def mac_unix(value: int) -> float:
    return APPLE_EPOCH_UNIX + value / 1_000_000_000

all_messages = messages.list_im_messages()
reply_rows_by_token = defaultdict(list)
for row in all_messages:
    match = TOKEN.search(str(row.get("content") or ""))
    sender = row.get("sender_identity")
    if match and isinstance(sender, dict) and sender.get("type") == "actor":
        reply_rows_by_token[match.group(0)].append(row)

assert set(reply_rows_by_token) == EXPECTED_TOKENS, sorted(reply_rows_by_token)
assert all(len(rows) == 1 for rows in reply_rows_by_token.values()), {
    token: len(rows) for token, rows in reply_rows_by_token.items()
}
reply_by_token = {token: rows[0] for token, rows in reply_rows_by_token.items()}

events_by_message = defaultdict(list)
for identity_id in EXTERNALS.values():
    for event in messages.list_im_events_for_identity(identity_id):
        events_by_message[str(event["message_id"])].append(event)

state = json.loads(STATE.read_text(encoding="utf-8"))
guids_by_event = defaultdict(list)
for contact in state["contacts"].values():
    for guid, link in contact.get("message_links", {}).items():
        guids_by_event[str(link["event_id"])].append(guid)

with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as db:
    inbound_rows = db.execute(
        "SELECT text,date FROM message WHERE COALESCE(is_from_me,0)=0 AND text LIKE '%[SOAK-R%'"
    ).fetchall()
    inbound_dates_by_token = defaultdict(list)
    for text, date in inbound_rows:
        match = TOKEN.search(str(text or ""))
        if match:
            inbound_dates_by_token[match.group(0)].append(int(date))

    assert set(inbound_dates_by_token) == EXPECTED_TOKENS, sorted(inbound_dates_by_token)
    assert all(len(rows) == 1 for rows in inbound_dates_by_token.values()), {
        token: len(rows) for token, rows in inbound_dates_by_token.items()
    }

    report = []
    for token in sorted(EXPECTED_TOKENS):
        match = TOKEN.fullmatch(token)
        assert match is not None
        reply = reply_by_token[token]
        assert reply["sender_identity"]["id"] == ACTORS[match.group("actor")]

        candidate_events = events_by_message[str(reply["id"])]
        assert len(candidate_events) == 1, (token, candidate_events)
        event = candidate_events[0]
        assert event["visible_to_identity_id"] == EXTERNALS[match.group("user")]

        candidate_guids = guids_by_event[str(event["event_id"])]
        assert len(candidate_guids) == 1, (token, candidate_guids)
        guid = candidate_guids[0]
        physical_rows = db.execute(
            "SELECT ROWID,date,error,is_sent,is_delivered,is_finished FROM message WHERE guid=?",
            (guid,),
        ).fetchall()
        assert len(physical_rows) == 1, (token, physical_rows)
        physical = physical_rows[0]
        event_at = iso_unix(str(event["created_at"]))
        inbound_at = mac_unix(inbound_dates_by_token[token][0])
        outbound_at = mac_unix(int(physical[1]))
        report.append(
            {
                "token": token,
                "actor_id": reply["sender_identity"]["id"],
                "external_id": event["visible_to_identity_id"],
                "message_id": reply["id"],
                "event_id": event["event_id"],
                "event_created_at": event["created_at"],
                "event_sequence": event["sequence"],
                "guid": guid,
                "db_rowid": physical[0],
                "actor_seconds": event_at - inbound_at,
                "bridge_seconds": outbound_at - event_at,
                "error": physical[2],
                "is_sent": physical[3],
                "is_delivered": physical[4],
                "is_finished": physical[5],
            }
        )

assert len(report) == 12
for field in ("message_id", "event_id", "guid", "db_rowid"):
    assert len({row[field] for row in report}) == 12, field
assert all(row["actor_seconds"] >= 0 and row["bridge_seconds"] >= 0 for row in report)
assert all(row["error"] == 0 and row["is_sent"] == 1 for row in report)

order = {}
for external_id in EXTERNALS.values():
    external_rows = [row for row in report if row["external_id"] == external_id]
    central_order = sorted(
        external_rows,
        key=lambda row: (row["event_created_at"], row["event_sequence"], row["event_id"]),
    )
    rowids = [row["db_rowid"] for row in central_order]
    assert rowids == sorted(rowids), (external_id, rowids)
    order[external_id] = rowids

bridge_values = sorted(row["bridge_seconds"] for row in report)
nearest_rank = lambda percentile: bridge_values[math.ceil(percentile * len(bridge_values)) - 1]
summary = {
    "count": len(report),
    "bridge_p95_seconds": nearest_rank(0.95),
    "bridge_p99_seconds": nearest_rank(0.99),
    "actor_min_seconds": min(row["actor_seconds"] for row in report),
    "actor_max_seconds": max(row["actor_seconds"] for row in report),
    "db_rowids_in_central_order": order,
}
assert summary["bridge_p95_seconds"] <= 2.0, summary
assert summary["bridge_p99_seconds"] <= 5.0, summary
print(json.dumps({"summary": summary, "rows": report}, ensure_ascii=True, indent=2))
PY
```

Expected: exactly 12 rows, correct actor and external identity per token, unique
message/event/GUID/DB row identities, no negative duration, physical order equal
to Central order per external identity, and bridge P95/P99 within the accepted SLO.

- [ ] **Step 2: Review the generated summary without recomputing evidence**

Expected: the script has already failed closed on duplicates, routing mismatch,
identity reuse, order mismatch, send errors, negative durations, or an exceeded
bridge SLO. Actor duration remains reported separately without an iMessage
threshold. `is_delivered` is recorded rather than required when macOS does not
supply delivery confirmation.

- [ ] **Step 3: Confirm ACK and clean state**

```bash
curl -fsS -H 'Authorization: Bearer imsk-d0553fc7d13a2814e83b3202f2eb9182d0784f201bed0af9' \
  'http://127.0.0.1:8765/api/im/events?limit=20&wait_ms=0'
curl -fsS -H 'Authorization: Bearer imsk-2907d4b5cc17e0ec241dec875764b67e8a18b9e0844b87e5' \
  'http://127.0.0.1:8765/api/im/events?limit=20&wait_ms=0'
jq '{retry:[.contacts[].outbound_retry|select(. != null)],failure:[.contacts[].last_delivery_failure|select(. != null)]}' \
  /Users/chen/.codex-buddyswitch/state/buddyswitch/local/imessage-channel/state.json
```

Expected: both event lists and both state arrays are empty.

## Task 5: Device Confirmation, Cleanup, And Evidence Commit

**Files:**
- Modify: `docs/memo/2026-07-20-imessage-multi-actor-two-user-soak-design.md`
- Modify: `docs/memo/2026-07-20-imessage-multi-actor-two-user-soak-plan.md`

- [ ] **Step 1: Obtain one exact user confirmation**

Ask the user to confirm that both devices show all six local tokens exactly once,
with the correct actor token/content and no cross-contact token.

- [ ] **Step 2: Stop the task-owned worker and prove cleanup**

Send `Ctrl-C` to the owned launcher PTY, then run:

```bash
if lsof -nP -iTCP:8765 -sTCP:LISTEN; then exit 1; fi
if ps -axo command | rg "imsg watch --json" | rg -v "rg "; then exit 1; fi
```

Expected: neither command finds a resource.

- [ ] **Step 3: Append compact evidence and update statuses**

Record source commit, C/B and M1/M2 labels, 12 token mappings, actor-duration
summary, bridge P95/P99, DB flags, ACK/state result, user confirmation, cleanup,
and residual risk in the source design. Check off this operational plan. Do not add
a second evidence file.

- [ ] **Step 4: Verify and commit the non-executable evidence change**

```bash
git diff --check
git status --short
git add docs/memo/2026-07-20-imessage-multi-actor-two-user-soak-design.md docs/memo/2026-07-20-imessage-multi-actor-two-user-soak-plan.md
git commit -m "docs(imessage): record multi-actor soak"
```

Expected: only the design evidence and checked-off operational plan are committed;
no executable test rerun is required because executable identity did not change.
