# iMessage Multi-Actor × Two-User Soak Design

Date: 2026-07-20

Status: approved conversational design; written-spec review pending

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
