# iMessage Multi-Actor × Two-User Soak Design

Date: 2026-07-20

Status: accepted

## Purpose

Prove that the current iMessage bridge remains correctly routed, ordered, and
responsive across sustained real interaction between two healthy actors and two
consenting external users. This supplements—not replaces—the existing 100-contact
automated capacity proof and the completed two-contact physical-send acceptance.

The soak changes no code, schema, API, or runtime contract.

## Participants

| Label | Current identity |
| --- | --- |
| M1 | `act-market-645c3ea1fe37` |
| M2 | `act-market-8164b055c113` |
| C | `yuflo2024@126.com` |
| B | `hblouis@126.com` |

Only C and B are authorized test contacts. No other iMessage contact participates.

## Workload

Run three rounds. Every user addresses both actors once per round, producing 12
actor replies in total. Tasks require only short text generation; actors need no
browsing, research, file, calendar, or other external tool. The normal Central IM
reply operation is part of the product path and is not considered task work.

Every request carries one unique token and requires a one-line response beginning
with that same token.

### Round 1 — Staggered Baseline

Task: generate a title of at most eight Chinese characters for “夏日午后”.

1. C sends M1, then M2 five seconds apart.
2. After C receives both replies, B sends M1, then M2 five seconds apart.

### Round 2 — Concurrent Rewrite

Task: rewrite “今天适合散步和喝茶” as a phrase of at most ten Chinese
characters.

1. C and B begin together.
2. Each sends M1, then M2 within fifteen seconds.

### Round 3 — Concurrent Reversed Actor Order

Task: generate exactly three words meaning “轻松”, separated by `/`.

1. C and B begin together.
2. Each sends M2 first, then M1 within fifteen seconds.

The reversed final order distinguishes actor routing from an accidental fixed
submission order.

## Message Shape

Each guided message uses this exact structure:

```text
@<actor-id> [SOAK-R<round>-<user>-<actor>] 这是纯文本生成任务，不浏览或调用外部工具。<task> 只回复一行，格式：[SOAK-R<round>-<user>-<actor>] <答案>
```

Tokens are therefore unique across all 12 requests and observable in inbound,
Central IM, and device-visible reply evidence.

## Evidence And Timing

Record separately:

1. inbound iMessage GUID, chat route, and receive time;
2. actor-created Central event/message identity and creation time;
3. outbound iMessage GUID, Messages DB row, send/delivery flags, and send time;
4. user confirmation of visible token, route, uniqueness, and local order.

Actor duration is `inbound receive -> Central event creation`. Bridge duration is
`Central event creation -> outbound Messages DB send`. Only bridge duration is
evaluated against the iMessage scheduler SLO.

## Acceptance

- All 12 request tokens receive exactly one matching visible reply.
- Every reply is attributed to the addressed actor and reaches the originating
  user's chat only.
- For each user, physical iMessage order equals that external session's Central
  event order.
- Bridge P95 is at most 2 seconds and P99 is at most 5 seconds.
- Every outbound row has `error=0` and `is_sent=1`; `is_delivered=1` is required
  when macOS supplies delivery confirmation.
- Every linked event is ACKed; no retry, terminal failure, or unconsumed test event
  remains.
- The task-owned Web/iMessage worker, port, and `imsg watch` process are cleaned up
  after user confirmation.

## Failure Handling And Scope

Stop the round on wrong routing, duplicate reply, missing token, out-of-order
delivery relative to Central event order, terminal failure, or an unavailable
actor. Preserve the evidence and diagnose before continuing; do not mask a signal
by sending replacement messages.

The soak does not deliberately corrupt a live route or induce a real platform
failure. Contact-scoped failure isolation remains owned by the existing controlled
worker tests. No repository-wide suite is required because this soak makes no
executable change.

## Execution Evidence

The soak ran against source commit `a76451f69d1f08dfbf264d5ebc1bb4a976b31f56`
with the iMessage executable path unchanged from `5efe75c`. The commits between
those identities changed only iMessage memos. The worker command was
`./buddyswitch-codex web --host 127.0.0.1 --port 8765`, with one
`imsg 0.11.1 watch --json` process.

The fail-closed correlation probe in the execution plan found exactly these 12
unique paths. `Inbound` is `user/chat/DB ROWID/GUID`; `Central` is
`message/event`; `Outbound` is `DB ROWID/GUID`.

| Token | Inbound | Actor | Central | Outbound | Actor s | Bridge s |
| --- | --- | --- | --- | --- | ---: | ---: |
| `[SOAK-R1-C-M1]` | `C/3211/27127/52C1AC9D-A940-4EC8-ABF6-08BF5A063B7F` | M1 | `msg-be5b13d4c99e/imev-58e9fd72a140` | `27129/0653951B-4FF4-425F-8607-1563479F0391` | 14.695 | 0.614 |
| `[SOAK-R1-C-M2]` | `C/3211/27128/FBEB27F4-B01B-49C4-8EFF-E03DF6D8877B` | M2 | `msg-2d3fc729694f/imev-08e4f11304d4` | `27130/486966AC-5ED8-4D33-AC61-752CC30C3461` | 17.705 | 1.149 |
| `[SOAK-R1-B-M1]` | `B/3213/27131/A26526CA-F1F8-4534-B862-2E0B5B7DAD34` | M1 | `msg-66aeacb6570f/imev-e010ce0582a5` | `27133/6520A0D4-28A3-4E1F-BC4C-B3B21FB6172E` | 18.511 | 0.549 |
| `[SOAK-R1-B-M2]` | `B/3213/27132/5A455636-374D-4454-A08C-40FF783A7675` | M2 | `msg-a3e62a718ca4/imev-397269aadb76` | `27134/FD242D4F-2D70-4338-A71E-F73D6AF6E1DB` | 18.331 | 0.423 |
| `[SOAK-R2-C-M1]` | `C/3211/27135/D3DF6C69-4A22-4F33-81ED-85D59FDA6A21` | M1 | `msg-208a1fadd9d6/imev-9ecac24d9967` | `27140/786A9D3F-137F-4067-93CF-DCA1F85E35C7` | 23.923 | 1.142 |
| `[SOAK-R2-C-M2]` | `C/3211/27137/6C135E27-02FC-4108-A617-54121D89B6F9` | M2 | `msg-ae7ef898762e/imev-2e0b0559fc74` | `27142/EF5DA2D8-9A5C-49C6-BAFB-9E7C07B0B29A` | 28.759 | 1.267 |
| `[SOAK-R2-B-M1]` | `B/3213/27136/BB848EA5-10E9-41A5-A194-6A7487970BC4` | M1 | `msg-dd988bfa793f/imev-2d716de9ae85` | `27139/237DF18E-ECCB-4C6B-BCBC-B077AA50AB0E` | 19.871 | 0.707 |
| `[SOAK-R2-B-M2]` | `B/3213/27138/1978D420-C4CD-402C-BDF1-17DBB0DC8DFF` | M2 | `msg-3b9b468c9428/imev-978964a11550` | `27141/71F68662-3273-493B-97F7-A902092D22F3` | 26.739 | 0.759 |
| `[SOAK-R3-C-M2]` | `C/3211/27143/068EB7DA-359B-497B-B268-71CFCBC95454` | M2 | `msg-7655490a3823/imev-d7e788490271` | `27146/12F8E56E-88AB-4AD1-A119-971C4EF2C2DE` | 16.974 | 0.714 |
| `[SOAK-R3-C-M1]` | `C/3211/27145/863E5CFC-7FC2-4192-90F8-DC0505AADC16` | M1 | `msg-ccb033416639/imev-8a2f90c66cd5` | `27149/133EFABF-6986-40C0-9FA6-E1158E23C8C2` | 40.292 | 1.348 |
| `[SOAK-R3-B-M2]` | `B/3213/27144/2523E8E8-FA02-4A77-8522-1D4D560190AB` | M2 | `msg-454911267b96/imev-d91d532cdfea` | `27147/6D5008E3-0242-42C2-B16E-35F05F1C5F4B` | 19.584 | 1.011 |
| `[SOAK-R3-B-M1]` | `B/3213/27148/FE83B305-940C-49EE-B5D3-6CF2509E63CB` | M1 | `msg-5d3bdf9cc522/imev-7d065acd03fa` | `27150/75B3F507-A77A-4F90-A172-0C5C49B5D575` | 32.134 | 1.366 |

Nearest-rank bridge P95 and P99 were both `1.366` seconds. Actor duration ranged
from `14.695` to `40.292` seconds and is reported separately from the bridge SLO.
For C, Central event order mapped to outbound ROWIDs
`27129,27130,27140,27142,27146,27149`; for B it mapped to
`27133,27134,27139,27141,27147,27150`. Both sequences were strictly increasing.

All 12 outbound rows had `error=0`, `is_sent=1`, `is_delivered=1`, and
`is_finished=1`. Both external event polls returned empty lists after delivery;
channel state contained no outbound retry or terminal failure. The user confirmed
that each device displayed its own six tokens exactly once with the intended actor
content and no cross-contact token.

After confirmation, the task-owned worker was interrupted. Port `8765` had no
listener and no `imsg watch --json` process remained. An early exploratory monitor
briefly reported no reply because it searched the physical outgoing `text` column,
which is `NULL` for these `imsg` rows; the authoritative event-to-GUID probe and
device observation both showed that delivery had already succeeded.

Residual risk is bounded to the accepted workload: this proves two real contacts,
two actors, three rounds, and 12 replies. It does not simulate a long-duration
carrier or Apple service outage; contact-scoped failure isolation and larger
capacity remain covered by the existing controlled worker and capacity evidence.
