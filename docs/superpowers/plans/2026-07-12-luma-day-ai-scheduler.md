# Luma Day AI Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished, responsive local AI scheduling MVP and matching landing page that turns one natural-language task into one explainable, user-confirmed TodayPlan time block.

**Architecture:** Use a build-free static web app with pure ES modules. Keep parsing, slot search, state transitions, and persistence independent from DOM rendering so behavior is deterministic and testable with Node's built-in test runner; use one shared visual system for `index.html` and `app.html`.

**Tech Stack:** HTML5, CSS custom properties, browser ES modules, Node.js `node:test`, `localStorage`, Python `http.server` for local serving.

---

## Source Boundary

All product writes happen in the launcher-managed shared product source:

```text
/Users/chen/.codex-buddyswitch/project/workspace/projects/app
```

BuddySwitch role workspaces see the same directory at `projects/app`. Do not write product files to `/Users/chen/Dev/buddyswitch/.worktrees/fea-webui/projects/app`; that directory is only the framework mount-point explanation.

Run product commands either from a BuddySwitch role workspace with `cd projects/app`, or directly in the canonical shared directory above.

The canonical shared product source lives inside the launcher-managed detached Git worktree `/Users/chen/.codex-buddyswitch/project/workspace`; `projects/app` is not an independent repository. Do not initialize a nested repository, create/switch a branch, or commit from that detached worktree as part of this task. Each implementation task instead ends in a red/green verification checkpoint and is recorded through the existing BuddySwitch Track/Artifact flow; the framework-side specification and this plan remain Git-versioned in `fea-webui`.

## File Map

```text
projects/app/
  package.json                 Node ESM mode and verification scripts
  README.md                    Product purpose, boundaries, run and test commands
  index.html                   Marketing landing page and CTA into the product
  app.html                     Semantic Today Decision View shell
  assets/
    styles.css                 Shared design tokens, landing/app layouts, responsive states
  src/
    planner.js                 Intent parsing, candidate generation, ranking, explanations
    state.js                   App state transitions, confirm/undo, persistence boundary
    sample-data.js             Stable local calendar and starter tasks
    app.js                     DOM rendering, interaction wiring, live feedback
  tests/
    planner.test.mjs           Parser, collision, ranking, explanation behavior
    state.test.mjs             State transition and persistence behavior
    ui-contract.test.mjs       Landing/app semantics, copy, CTA, accessibility contracts
```

## Task 1: Establish the ESM Test Harness

**Files:**
- Create: `projects/app/package.json`
- Modify: `projects/app/README.md`

- [ ] **Step 1: Replace the mount-point README with product run instructions**

Write `projects/app/README.md` with the exact product boundary and commands:

````markdown
# Luma Day

Luma Day is a local, explainable scheduling demo. It reads deterministic sample busy blocks, proposes one time block, and waits for explicit confirmation before adding it to the browser-only TodayPlan.

It does not connect to, modify, or claim to sync an external calendar.

## Run

```bash
python3 -m http.server 4173 --directory .
```

Open `http://127.0.0.1:4173/` for the landing page and `/app.html` for the product.

## Verify

```bash
npm test
npm run check
```
````

- [ ] **Step 2: Add the package scripts**

Create `projects/app/package.json`:

```json
{
  "name": "luma-day",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test tests/*.test.mjs",
    "check": "node --check src/planner.js && node --check src/state.js && node --check src/sample-data.js && node --check src/app.js"
  }
}
```

- [ ] **Step 3: Prove the empty harness is callable**

Run:

```bash
npm test
```

Expected: exit non-zero because `tests/*.test.mjs` does not exist yet. This is the intended red state before Task 2.

- [ ] **Step 4: Record the boundary checkpoint**

Run:

```bash
pwd
find . -maxdepth 2 -type f -print | sort
```

Expected: `pwd` is the shared project source or a role's mapped `projects/app`; only `README.md` and `package.json` are present.

## Task 2: Parse Natural-Language Scheduling Constraints

**Files:**
- Create: `projects/app/tests/planner.test.mjs`
- Create: `projects/app/src/planner.js`

- [ ] **Step 1: Write the failing parser tests**

Create `tests/planner.test.mjs`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { parseIntent } from '../src/planner.js';

test('parses Chinese duration and afternoon deadline', () => {
  const result = parseIntent('下午 4 点前安排 90 分钟准备发布 brief');
  assert.equal(result.durationMinutes, 90);
  assert.equal(result.deadlineMinute, 16 * 60);
  assert.equal(result.preferredPeriod, 'afternoon');
  assert.match(result.title, /发布 brief/);
  assert.deepEqual(result.missing, []);
});

test('parses English duration and deadline', () => {
  const result = parseIntent('Prepare launch brief for 1.5 hours by 4 pm');
  assert.equal(result.durationMinutes, 90);
  assert.equal(result.deadlineMinute, 16 * 60);
  assert.match(result.title, /launch brief/i);
});

test('flags missing duration instead of inventing one', () => {
  const result = parseIntent('今天回复合作伙伴');
  assert.equal(result.durationMinutes, null);
  assert.deepEqual(result.missing, ['durationMinutes']);
});
```

- [ ] **Step 2: Run the parser tests to verify red**

Run:

```bash
node --test tests/planner.test.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/planner.js`.

- [ ] **Step 3: Implement the minimal parser**

Create `src/planner.js` with these public contracts:

```js
export const WORKDAY = Object.freeze({ start: 9 * 60, end: 18 * 60, step: 15 });

function parseDuration(text) {
  const minutes = text.match(/(\d+)\s*(?:分钟|mins?|minutes?)/i);
  if (minutes) return Number(minutes[1]);
  const hours = text.match(/(\d+(?:\.\d+)?)\s*(?:小时|hours?|hrs?)/i);
  return hours ? Math.round(Number(hours[1]) * 60) : null;
}

function parseDeadline(text) {
  const zh = text.match(/(?:上午|下午)?\s*(\d{1,2})(?:[:：](\d{2}))?\s*点?前/);
  if (zh) {
    let hour = Number(zh[1]);
    if (/下午/.test(zh[0]) && hour < 12) hour += 12;
    return hour * 60 + Number(zh[2] ?? 0);
  }
  const en = text.match(/by\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?/i);
  if (!en) return null;
  let hour = Number(en[1]);
  if (en[3]?.toLowerCase() === 'pm' && hour < 12) hour += 12;
  if (en[3]?.toLowerCase() === 'am' && hour === 12) hour = 0;
  return hour * 60 + Number(en[2] ?? 0);
}

function cleanTitle(text) {
  return text
    .replace(/(?:上午|下午)?\s*\d{1,2}(?:[:：]\d{2})?\s*点?前/g, '')
    .replace(/\d+\s*(?:分钟|mins?|minutes?)/gi, '')
    .replace(/\d+(?:\.\d+)?\s*(?:小时|hours?|hrs?)/gi, '')
    .replace(/\b(?:for|by)\b\s*/gi, '')
    .replace(/^(?:安排|add|schedule)\s*/i, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function parseIntent(text) {
  const durationMinutes = parseDuration(text);
  const deadlineMinute = parseDeadline(text);
  return {
    title: cleanTitle(text),
    durationMinutes,
    deadlineMinute,
    preferredPeriod: /下午|afternoon/i.test(text) ? 'afternoon' : null,
    movable: true,
    missing: durationMinutes == null ? ['durationMinutes'] : [],
    rawText: text
  };
}
```

- [ ] **Step 4: Run the parser tests to verify green**

Run:

```bash
node --test tests/planner.test.mjs
```

Expected: 3 tests pass.

## Task 3: Generate, Rank, and Explain Valid Time Blocks

**Files:**
- Modify: `projects/app/tests/planner.test.mjs`
- Modify: `projects/app/src/planner.js`

- [ ] **Step 1: Add failing slot and explanation tests**

Append to `tests/planner.test.mjs`:

```js
import {
  findCandidateSlots,
  rankCandidates,
  buildSuggestion
} from '../src/planner.js';

const busyBlocks = [
  { id: 'sync', startMinute: 9 * 60, endMinute: 9 * 60 + 30 },
  { id: 'call', startMinute: 11 * 60, endMinute: 12 * 60 },
  { id: 'review', startMinute: 15 * 60, endMinute: 16 * 60 }
];

test('finds slots without crossing busy blocks', () => {
  const task = { durationMinutes: 90, deadlineMinute: 16 * 60, preferredPeriod: 'afternoon' };
  const slots = findCandidateSlots(task, busyBlocks, []);
  assert.ok(slots.length > 0);
  assert.ok(slots.every((slot) =>
    busyBlocks.every((busy) => slot.endMinute <= busy.startMinute || slot.startMinute >= busy.endMinute)
  ));
});

test('ranks the latest valid afternoon block before the deadline', () => {
  const task = { durationMinutes: 90, deadlineMinute: 16 * 60, preferredPeriod: 'afternoon' };
  const ranked = rankCandidates(findCandidateSlots(task, busyBlocks, []), task);
  assert.deepEqual(ranked[0], { startMinute: 13 * 60 + 30, endMinute: 15 * 60 });
});

test('returns a traceable reason set', () => {
  const task = { id: 'launch', title: '准备发布 brief', durationMinutes: 90, deadlineMinute: 16 * 60, preferredPeriod: 'afternoon' };
  const suggestion = buildSuggestion(task, busyBlocks, [], 'fresh');
  assert.equal(suggestion.startMinute, 13 * 60 + 30);
  assert.equal(suggestion.endMinute, 15 * 60);
  assert.ok(suggestion.reasons.some((reason) => reason.includes('90')));
  assert.ok(suggestion.reasons.some((reason) => reason.includes('16:00')));
  assert.ok(suggestion.reasons.length <= 3);
});

test('returns an explicit no-slot result', () => {
  const task = { id: 'blocked', title: 'Long task', durationMinutes: 240, deadlineMinute: 12 * 60 };
  const result = buildSuggestion(task, [{ startMinute: 9 * 60, endMinute: 12 * 60 }], [], 'fresh');
  assert.deepEqual(result, {
    status: 'no-slot',
    conflicts: ['工作时间与现有忙碌时段无法容纳 240 分钟连续时间']
  });
});

test('refuses to claim availability from stale data', () => {
  const task = { id: 'stale', title: 'Draft', durationMinutes: 30 };
  assert.deepEqual(buildSuggestion(task, [], [], 'stale'), {
    status: 'stale-calendar',
    conflicts: ['忙碌信息已过期，请先刷新示例日历']
  });
});
```

- [ ] **Step 2: Run the expanded planner tests to verify red**

Run:

```bash
node --test tests/planner.test.mjs
```

Expected: FAIL because the three planning exports do not exist.

- [ ] **Step 3: Implement collision-safe candidate generation**

Append to `src/planner.js`:

```js
function overlaps(slot, block) {
  return slot.startMinute < block.endMinute && slot.endMinute > block.startMinute;
}

export function findCandidateSlots(task, busyBlocks, todayPlan) {
  if (!task.durationMinutes) return [];
  const hardEnd = Math.min(task.deadlineMinute ?? WORKDAY.end, WORKDAY.end);
  const occupied = [...busyBlocks, ...todayPlan];
  const candidates = [];
  for (let start = WORKDAY.start; start + task.durationMinutes <= hardEnd; start += WORKDAY.step) {
    const slot = { startMinute: start, endMinute: start + task.durationMinutes };
    if (occupied.every((block) => !overlaps(slot, block))) candidates.push(slot);
  }
  return candidates;
}

export function rankCandidates(candidates, task) {
  return [...candidates]
    .map((candidate) => ({
      candidate,
      score:
        (task.preferredPeriod === 'afternoon' && candidate.startMinute >= 12 * 60 ? 1000 : 0) +
        (task.deadlineMinute ? candidate.startMinute : -candidate.startMinute)
    }))
    .sort((a, b) => b.score - a.score || a.candidate.startMinute - b.candidate.startMinute)
    .map(({ candidate }) => candidate);
}
```

- [ ] **Step 4: Implement bounded explanations and explicit failures**

Append to `src/planner.js`:

```js
export function formatMinute(minute) {
  const hour = Math.floor(minute / 60);
  const minutes = minute % 60;
  return `${String(hour).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

export function buildSuggestion(task, busyBlocks, todayPlan, calendarFreshness) {
  if (calendarFreshness !== 'fresh') {
    return { status: 'stale-calendar', conflicts: ['忙碌信息已过期，请先刷新示例日历'] };
  }
  const ranked = rankCandidates(findCandidateSlots(task, busyBlocks, todayPlan), task);
  if (ranked.length === 0) {
    return {
      status: 'no-slot',
      conflicts: [`工作时间与现有忙碌时段无法容纳 ${task.durationMinutes} 分钟连续时间`]
    };
  }
  const best = ranked[0];
  const reasons = [`提供连续 ${task.durationMinutes} 分钟，不与现有安排冲突`];
  if (task.deadlineMinute) reasons.push(`在 ${formatMinute(task.deadlineMinute)} 截止前完成`);
  if (task.preferredPeriod === 'afternoon') reasons.push('符合下午处理的时间偏好');
  return {
    id: `suggestion-${task.id}`,
    status: 'ready',
    taskId: task.id,
    startMinute: best.startMinute,
    endMinute: best.endMinute,
    alternatives: ranked.slice(1, 3),
    reasons: reasons.slice(0, 3),
    constraintSnapshot: { ...task }
  };
}
```

- [ ] **Step 5: Run the planner tests to verify green**

Run:

```bash
node --test tests/planner.test.mjs
```

Expected: all parser and planner tests pass.

## Task 4: Implement Explicit State Transitions and Persistence

**Files:**
- Create: `projects/app/tests/state.test.mjs`
- Create: `projects/app/src/state.js`
- Create: `projects/app/src/sample-data.js`

- [ ] **Step 1: Write failing state tests**

Create `tests/state.test.mjs`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createInitialState,
  reduceState,
  persistState,
  restoreState
} from '../src/state.js';

test('starts disconnected and cannot request a suggestion', () => {
  const state = createInitialState();
  assert.equal(state.calendar.status, 'disconnected');
  assert.throws(() => reduceState(state, { type: 'suggestion/requested' }), /连接示例日历/);
});

test('stale busy data blocks suggestion generation', () => {
  const connected = reduceState(createInitialState(), { type: 'calendar/connected', busyBlocks: [] });
  const stale = reduceState(connected, { type: 'calendar/staled' });
  assert.equal(stale.calendar.freshness, 'stale');
  assert.throws(() => reduceState(stale, { type: 'suggestion/requested' }), /刷新示例日历/);
});

test('confirm adds a TodayPlan item and supports undo', () => {
  const connected = reduceState(createInitialState(), {
    type: 'calendar/connected',
    busyBlocks: []
  });
  const withTask = reduceState(connected, {
    type: 'task/added',
    task: { id: 'task-1', title: 'Draft', durationMinutes: 30 }
  });
  const suggested = reduceState(withTask, {
    type: 'suggestion/created',
    suggestion: { id: 'suggestion-task-1', taskId: 'task-1', startMinute: 600, endMinute: 630, status: 'ready' }
  });
  const confirmed = reduceState(suggested, { type: 'suggestion/confirmed' });
  assert.equal(confirmed.todayPlan.length, 1);
  assert.equal(confirmed.tasks[0].status, 'planned');
  const undone = reduceState(confirmed, { type: 'plan/undone' });
  assert.equal(undone.todayPlan.length, 0);
  assert.equal(undone.tasks[0].status, 'inbox');
});

test('persists and restores tasks and TodayPlan', () => {
  const data = new Map();
  const storage = {
    setItem: (key, value) => data.set(key, value),
    getItem: (key) => data.get(key) ?? null
  };
  const state = { ...createInitialState(), tasks: [{ id: 'task-1' }], todayPlan: [{ id: 'plan-1' }] };
  persistState(storage, state);
  assert.deepEqual(restoreState(storage), state);
});
```

- [ ] **Step 2: Run the state tests to verify red**

Run:

```bash
node --test tests/state.test.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/state.js`.

- [ ] **Step 3: Implement the reducer and storage boundary**

Create `src/state.js`:

```js
const STORAGE_KEY = 'luma-day-state-v1';

export function createInitialState() {
  return {
    calendar: { status: 'disconnected', freshness: 'fresh', updatedAt: null },
    busyBlocks: [],
    tasks: [],
    activeTaskId: null,
    suggestion: null,
    todayPlan: [],
    lastAction: null
  };
}

export function reduceState(state, action) {
  switch (action.type) {
    case 'calendar/connected':
      return {
        ...state,
        calendar: { status: 'connected', freshness: 'fresh', updatedAt: action.updatedAt ?? new Date().toISOString() },
        busyBlocks: action.busyBlocks,
        tasks: state.tasks.length > 0 ? state.tasks : (action.starterTasks ?? []).map((task) => ({ ...task }))
      };
    case 'calendar/staled':
      return { ...state, calendar: { ...state.calendar, freshness: 'stale' }, suggestion: null };
    case 'task/added':
      return {
        ...state,
        tasks: [...state.tasks, { ...action.task, status: 'inbox' }],
        activeTaskId: action.task.id,
        suggestion: null
      };
    case 'task/updated':
      return { ...state, tasks: state.tasks.map((task) => task.id === action.task.id ? action.task : task), suggestion: null };
    case 'task/selected':
      return { ...state, activeTaskId: action.taskId, suggestion: null };
    case 'suggestion/requested':
      if (state.calendar.status !== 'connected') throw new Error('请先连接示例日历');
      if (state.calendar.freshness !== 'fresh') throw new Error('请先刷新示例日历');
      return { ...state, suggestion: { status: 'loading' } };
    case 'suggestion/created':
      return { ...state, suggestion: action.suggestion };
    case 'suggestion/confirmed': {
      const suggestion = state.suggestion;
      const planItem = {
        id: `plan-${suggestion.id}`,
        taskId: suggestion.taskId,
        startMinute: suggestion.startMinute,
        endMinute: suggestion.endMinute,
        createdFromSuggestionId: suggestion.id
      };
      return {
        ...state,
        tasks: state.tasks.map((task) => task.id === suggestion.taskId ? { ...task, status: 'planned' } : task),
        todayPlan: [...state.todayPlan, planItem],
        suggestion: null,
        lastAction: { type: 'plan/confirmed', planItem, taskId: suggestion.taskId, suggestion }
      };
    }
    case 'plan/undone': {
      const last = state.lastAction;
      if (last?.type !== 'plan/confirmed') return state;
      return {
        ...state,
        tasks: state.tasks.map((task) => task.id === last.taskId ? { ...task, status: 'inbox' } : task),
        todayPlan: state.todayPlan.filter((item) => item.id !== last.planItem.id),
        suggestion: last.suggestion,
        lastAction: null
      };
    }
    default:
      return state;
  }
}

export function persistState(storage, state) {
  storage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function restoreState(storage) {
  const raw = storage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : createInitialState();
}
```

- [ ] **Step 4: Add stable sample data**

Create `src/sample-data.js`:

```js
export const sampleBusyBlocks = Object.freeze([
  { id: 'sync', title: '团队同步', startMinute: 9 * 60, endMinute: 9 * 60 + 30, source: '示例日历' },
  { id: 'call', title: '客户电话', startMinute: 11 * 60, endMinute: 12 * 60, source: '示例日历' },
  { id: 'review', title: '设计评审', startMinute: 15 * 60, endMinute: 16 * 60, source: '示例日历' }
]);

export const starterTasks = Object.freeze([
  { id: 'metrics', title: '复盘本周指标', durationMinutes: 30, deadlineMinute: 18 * 60, movable: true, status: 'inbox' },
  { id: 'reply', title: '回复合作伙伴', durationMinutes: 15, deadlineMinute: 17 * 60, movable: true, status: 'inbox' }
]);
```

- [ ] **Step 5: Run state and planner tests to verify green**

Run:

```bash
npm test
```

Expected: all planner and state tests pass.

## Task 5: Build the Semantic Today Decision View Shell

**Files:**
- Create: `projects/app/tests/ui-contract.test.mjs`
- Create: `projects/app/app.html`
- Create: `projects/app/assets/styles.css`

- [ ] **Step 1: Write failing product shell contract tests**

Create `tests/ui-contract.test.mjs`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('app exposes the three Today Decision View regions', async () => {
  const html = await read('../app.html');
  assert.match(html, /<main[^>]+class="[^"]*app-layout/);
  assert.match(html, /data-testid="task-inbox"/);
  assert.match(html, /data-testid="today-timeline"/);
  assert.match(html, /data-testid="suggestion-panel"/);
});

test('app contains accessible input, live status, and explicit calendar boundary', async () => {
  const html = await read('../app.html');
  assert.match(html, /<label[^>]+for="quick-capture"/);
  assert.match(html, /id="quick-capture"/);
  assert.match(html, /aria-live="polite"/);
  assert.match(html, /未修改外部日历/);
  assert.match(html, /data-action="connect-sample"/);
  assert.match(html, /data-action="simulate-stale"/);
});

test('shared CSS defines tokens, mobile layout, reduced motion, and visible focus', async () => {
  const css = await read('../assets/styles.css');
  assert.match(css, /--paper:\s*#f4f1e8/i);
  assert.match(css, /@media\s*\(max-width:\s*760px\)/);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /:focus-visible/);
});
```

- [ ] **Step 2: Run the UI contract tests to verify red**

Run:

```bash
node --test tests/ui-contract.test.mjs
```

Expected: FAIL because `app.html` and `assets/styles.css` do not exist.

- [ ] **Step 3: Create the semantic app shell**

Create `app.html` with this structure and the exact IDs/data attributes used by `app.js`:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Luma Day 将一句待办变成可解释、需确认的今日时间块。">
  <title>Luma Day · 今日决策</title>
  <link rel="stylesheet" href="assets/styles.css">
</head>
<body class="app-page">
  <header class="app-header">
    <a class="brand" href="index.html" aria-label="Luma Day 首页">Luma Day</a>
    <div class="day-heading"><span>今天</span><strong id="today-label"></strong></div>
    <div class="calendar-controls">
      <span class="calendar-status" id="calendar-status">示例日历未连接</span>
      <button class="text-button" data-action="simulate-stale" type="button">模拟数据过期</button>
    </div>
  </header>

  <main class="app-layout">
    <aside class="panel task-panel" data-testid="task-inbox" aria-labelledby="tasks-title">
      <div class="panel-heading"><p class="eyebrow">Inbox</p><h1 id="tasks-title">待安排</h1></div>
      <form id="capture-form" class="capture-form">
        <label for="quick-capture">用一句话添加待办</label>
        <textarea id="quick-capture" rows="3" placeholder="下午 4 点前安排 90 分钟准备发布 brief"></textarea>
        <button class="button button-dark" type="submit">理解这件事</button>
      </form>
      <div id="constraint-editor" class="constraint-editor" hidden></div>
      <ul id="task-list" class="task-list"></ul>
    </aside>

    <section class="panel timeline-panel" data-testid="today-timeline" aria-labelledby="timeline-title">
      <div class="panel-heading timeline-heading">
        <div><p class="eyebrow">Today</p><h2 id="timeline-title">今天的空间</h2></div>
        <button class="button button-ghost" data-action="connect-sample" type="button">使用示例日历</button>
      </div>
      <p class="boundary-note">仅读取示例忙碌信息 · 确认后也不会修改外部日历</p>
      <div id="timeline" class="timeline"></div>
    </section>

    <aside class="panel suggestion-panel" data-testid="suggestion-panel" aria-labelledby="suggestion-title">
      <div class="panel-heading"><p class="eyebrow">One good next move</p><h2 id="suggestion-title">下一步建议</h2></div>
      <div id="suggestion-content" class="suggestion-content"></div>
    </aside>
  </main>

  <div id="live-status" class="sr-only" aria-live="polite"></div>
  <div id="toast" class="toast" role="status" hidden></div>
  <script type="module" src="src/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Establish the visual system and three-column layout**

Create `assets/styles.css` with the approved tokens, then implement these layout contracts:

```css
:root {
  --paper: #f4f1e8;
  --surface: #fffdfa;
  --surface-muted: #ece9df;
  --ink: #1c2421;
  --ink-muted: #686c66;
  --forest: #164c43;
  --forest-soft: #dcebe4;
  --signal: #d8ff98;
  --clay: #c97b63;
  --line: #d8d4ca;
  --danger: #b4493f;
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 24px;
  --shadow-soft: 0 18px 52px rgba(31, 39, 35, .08);
  --font-sans: "Avenir Next", "Segoe UI", sans-serif;
  --font-serif: Georgia, "Times New Roman", serif;
}

* { box-sizing: border-box; }
body { margin: 0; color: var(--ink); background: var(--paper); font-family: var(--font-sans); }
button, textarea, input { font: inherit; }
button { min-height: 44px; }
:focus-visible { outline: 3px solid var(--clay); outline-offset: 3px; }
.app-header { min-height: 76px; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; padding: 0 28px; border-bottom: 1px solid var(--line); }
.calendar-status { justify-self: end; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); padding: 0 16px; }
.app-layout { min-height: calc(100vh - 76px); display: grid; grid-template-columns: minmax(250px,.78fr) minmax(420px,1.35fr) minmax(290px,.92fr); gap: 14px; padding: 14px; }
.panel { min-width: 0; border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--surface); box-shadow: var(--shadow-soft); overflow: hidden; }
.panel-heading { padding: 22px 22px 14px; }
.eyebrow { margin: 0 0 5px; color: var(--ink-muted); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; }
.capture-form, .constraint-editor, .task-list, .suggestion-content { margin: 0; padding: 0 22px 22px; }
.capture-form textarea { width: 100%; resize: vertical; border: 1px solid var(--line); border-radius: var(--radius-md); background: #fff; padding: 14px; }
.button { min-height: 44px; display: inline-flex; align-items: center; justify-content: center; border: 0; border-radius: 12px; padding: 0 16px; cursor: pointer; text-decoration: none; }
.button-dark { color: #fff; background: var(--forest); }
.capture-form .button-dark { width: 100%; margin-top: 10px; }
.button-primary { color: var(--forest); background: var(--signal); font-weight: 700; }
.button-ghost { border: 1px solid var(--line); background: transparent; }
.timeline { position: relative; min-height: 720px; margin: 0 22px 24px 74px; border-left: 1px solid var(--line); }
.suggestion-card { margin: 0 22px; border-radius: var(--radius-md); color: #fff; background: var(--forest); padding: 20px; }
.reason-list { padding-left: 20px; color: rgba(255,255,255,.8); }
.toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); border-radius: 999px; background: var(--ink); color: #fff; padding: 12px 16px; box-shadow: var(--shadow-soft); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }

@media (max-width: 1040px) {
  .app-layout { grid-template-columns: minmax(230px,.8fr) minmax(390px,1.3fr); }
  .suggestion-panel { grid-column: 1 / -1; }
}

@media (max-width: 760px) {
  .app-header { grid-template-columns: 1fr auto; padding: 0 16px; }
  .day-heading { display: none; }
  .app-layout { display: block; padding: 10px; }
  .panel { margin-bottom: 10px; }
  .timeline { min-height: 620px; }
  .suggestion-panel { position: sticky; bottom: 8px; z-index: 10; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; }
}
```

- [ ] **Step 5: Run the UI contract tests to verify green**

Run:

```bash
node --test tests/ui-contract.test.mjs
```

Expected: all shell and shared-style contract tests pass.

## Task 6: Wire the End-to-End Product Interaction

**Files:**
- Create: `projects/app/src/app.js`
- Modify: `projects/app/assets/styles.css`

- [ ] **Step 1: Implement a single render loop and explicit dispatch**

Create `src/app.js` with this module boundary:

```js
import { parseIntent, buildSuggestion, formatMinute } from './planner.js';
import { createInitialState, reduceState, persistState, restoreState } from './state.js';
import { sampleBusyBlocks, starterTasks } from './sample-data.js';

const elements = {
  captureForm: document.querySelector('#capture-form'),
  capture: document.querySelector('#quick-capture'),
  constraints: document.querySelector('#constraint-editor'),
  taskList: document.querySelector('#task-list'),
  timeline: document.querySelector('#timeline'),
  suggestion: document.querySelector('#suggestion-content'),
  live: document.querySelector('#live-status'),
  toast: document.querySelector('#toast'),
  today: document.querySelector('#today-label'),
  calendarStatus: document.querySelector('#calendar-status'),
  connectSample: document.querySelector('[data-action="connect-sample"]'),
  simulateStale: document.querySelector('[data-action="simulate-stale"]')
};

let state = restoreState(localStorage);
if (!state || !state.calendar) state = createInitialState();
elements.today.textContent = new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric', weekday: 'short' }).format(new Date());

const HTML_ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => HTML_ENTITIES[character]);

function dispatch(action) {
  state = reduceState(state, action);
  persistState(localStorage, state);
  render();
}

function activeTask() {
  return state.tasks.find((task) => task.id === state.activeTaskId) ?? null;
}
```

- [ ] **Step 2: Render tasks, editable constraints, and semantic timeline blocks**

Add functions with these exact responsibilities:

```js
function renderTasks() {
  elements.taskList.innerHTML = state.tasks
    .filter((task) => task.status === 'inbox')
    .map((task) => `<li><button class="task-card ${task.id === state.activeTaskId ? 'is-active' : ''}" data-task-id="${task.id}" type="button"><strong>${escapeHtml(task.title)}</strong><span>${task.durationMinutes ?? '补充'} 分钟</span></button></li>`)
    .join('') || '<li class="empty-state">一句话添加今天需要安排的任务。</li>';
}

function renderConstraints() {
  const task = activeTask();
  elements.constraints.hidden = !task;
  elements.constraints.innerHTML = task ? `
    <div class="constraint-grid">
      <label>时长（分钟）<input name="duration" type="number" min="15" step="15" value="${task.durationMinutes ?? ''}"></label>
      <label>最晚完成<input name="deadline" type="time" value="${task.deadlineMinute ? formatMinute(task.deadlineMinute) : ''}"></label>
    </div>
    <p class="constraint-note">系统不会替你猜优先级或时长；修改后再生成建议。</p>
    <button class="button button-dark" data-action="generate" type="button" ${task.durationMinutes ? '' : 'disabled'}>为下一件重要任务生成建议</button>
  ` : '';
}

function renderTimeline() {
  if (state.calendar.status !== 'connected') {
    elements.timeline.innerHTML = '<div class="empty-state timeline-empty">连接本地示例日历，查看今天的忙碌时段和空档。</div>';
    return;
  }
  const blocks = [
    ...state.busyBlocks.map((block) => ({ ...block, kind: 'busy' })),
    ...state.todayPlan.map((block) => ({ ...block, title: state.tasks.find((task) => task.id === block.taskId)?.title, kind: 'planned' }))
  ];
  elements.timeline.innerHTML = blocks.map((block) => {
    const top = ((block.startMinute - 9 * 60) / (9 * 60)) * 100;
    const height = ((block.endMinute - block.startMinute) / (9 * 60)) * 100;
    return `<article class="timeline-block ${block.kind}" style="--top:${top}%;--height:${height}%"><span>${formatMinute(block.startMinute)}</span><strong>${escapeHtml(block.title)}</strong></article>`;
  }).join('');
}
```

- [ ] **Step 3: Render loading, failure, suggestion, and confirmation states**

Add:

```js
function renderSuggestion() {
  const suggestion = state.suggestion;
  if (!suggestion) {
    elements.suggestion.innerHTML = '<div class="empty-state">选择或添加一项任务，再生成一个可解释的时间块。</div>';
    return;
  }
  if (suggestion.status === 'loading') {
    elements.suggestion.innerHTML = '<ol class="progress-steps"><li>理解约束</li><li>检查今天的空档</li><li>准备理由</li></ol>';
    return;
  }
  if (suggestion.status !== 'ready') {
    elements.suggestion.innerHTML = `<div class="conflict-state"><strong>暂时找不到可信时段</strong><p>${suggestion.conflicts.join('；')}</p><button class="button button-ghost" data-action="edit-constraints" type="button">修改约束</button></div>`;
    return;
  }
  elements.suggestion.innerHTML = `
    <article class="suggestion-card">
      <p class="eyebrow">Best fit · 未修改外部日历</p>
      <h3>${formatMinute(suggestion.startMinute)}–${formatMinute(suggestion.endMinute)}</h3>
      <p>${escapeHtml(activeTask().title)}</p>
      <ul class="reason-list">${suggestion.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}</ul>
      <p class="freshness-note">忙碌信息更新于 ${escapeHtml(state.calendar.updatedAt ?? '刚刚')}</p>
      <div class="suggestion-actions">
        <button class="button button-primary" data-action="confirm" type="button">加入我的今天</button>
        <button class="button button-ghost" data-action="alternate" type="button">换个时段</button>
        <button class="button button-ghost" data-action="edit-constraints" type="button">编辑约束</button>
        <button class="text-button" data-action="skip" type="button">暂时跳过</button>
      </div>
    </article>`;
}

function renderCalendarStatus() {
  if (state.calendar.status !== 'connected') {
    elements.calendarStatus.textContent = '示例日历未连接';
    elements.connectSample.textContent = '使用示例日历';
    elements.simulateStale.disabled = true;
    return;
  }
  elements.calendarStatus.textContent = state.calendar.freshness === 'fresh' ? '示例日历 · 只读' : '示例日历 · 数据已过期';
  elements.connectSample.textContent = state.calendar.freshness === 'fresh' ? '刷新示例日历' : '立即刷新';
  elements.simulateStale.disabled = state.calendar.freshness !== 'fresh';
}

function render() {
  renderCalendarStatus();
  renderTasks();
  renderConstraints();
  renderTimeline();
  renderSuggestion();
}
```

- [ ] **Step 4: Wire interactions with immediate feedback**

Add event handlers that preserve user input and show state progression:

```js
document.addEventListener('click', (event) => {
  const taskButton = event.target.closest('[data-task-id]');
  if (taskButton) dispatch({ type: 'task/selected', taskId: taskButton.dataset.taskId });

  const action = event.target.closest('[data-action]')?.dataset.action;
  if (action === 'connect-sample') {
    dispatch({ type: 'calendar/connected', busyBlocks: sampleBusyBlocks, starterTasks });
    elements.live.textContent = '示例日历已连接。只读忙碌信息。';
  }
  if (action === 'simulate-stale') {
    dispatch({ type: 'calendar/staled' });
    elements.live.textContent = '示例忙碌信息已标记为过期，刷新前不会生成建议。';
  }
  if (action === 'generate') generateSuggestion();
  if (action === 'confirm') {
    dispatch({ type: 'suggestion/confirmed' });
    showToast('已加入 TodayPlan。外部日历未被修改。', true);
  }
  if (action === 'alternate') useAlternate();
  if (action === 'skip') dispatch({ type: 'suggestion/created', suggestion: null });
  if (action === 'edit-constraints') elements.constraints.querySelector('[name="duration"]')?.focus();
});

elements.captureForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const text = elements.capture.value.trim();
  if (!text) return;
  const parsed = parseIntent(text);
  dispatch({ type: 'task/added', task: { id: `task-${Date.now()}`, ...parsed } });
  elements.capture.value = '';
  elements.live.textContent = parsed.missing.length ? '已理解任务，请补充时长。' : '已理解任务，请确认约束。';
});

elements.constraints.addEventListener('change', () => {
  const task = activeTask();
  const duration = Number(elements.constraints.querySelector('[name="duration"]').value) || null;
  const deadline = elements.constraints.querySelector('[name="deadline"]').value;
  const [hours, minutes] = deadline ? deadline.split(':').map(Number) : [null, null];
  dispatch({
    type: 'task/updated',
    task: { ...task, durationMinutes: duration, deadlineMinute: hours == null ? null : hours * 60 + minutes, missing: duration ? [] : ['durationMinutes'] }
  });
});

function generateSuggestion() {
  const task = activeTask();
  dispatch({ type: 'suggestion/requested' });
  elements.live.textContent = '正在理解约束、检查空档并准备理由。';
  window.setTimeout(() => {
    try {
      const suggestion = buildSuggestion(task, state.busyBlocks, state.todayPlan, state.calendar.freshness);
      dispatch({ type: 'suggestion/created', suggestion });
      elements.live.textContent = suggestion.status === 'ready' ? '建议已准备好。' : suggestion.conflicts.join('；');
    } catch {
      const suggestion = { status: 'error', conflicts: ['生成失败，任务和约束已保留，请重试'] };
      dispatch({ type: 'suggestion/created', suggestion });
      elements.live.textContent = suggestion.conflicts[0];
    }
  }, 480);
}

function useAlternate() {
  const current = state.suggestion;
  const alternate = current?.alternatives?.[0];
  if (!alternate) return;
  dispatch({ type: 'suggestion/created', suggestion: { ...current, ...alternate, alternatives: current.alternatives.slice(1) } });
  elements.live.textContent = '已换到下一个有效时段。';
}

function showToast(message, undoable) {
  elements.toast.hidden = false;
  elements.toast.innerHTML = `${message}${undoable ? ' <button data-action="undo" type="button">撤销</button>' : ''}`;
}

document.addEventListener('click', (event) => {
  if (event.target.closest('[data-action="undo"]')) {
    dispatch({ type: 'plan/undone' });
    elements.toast.hidden = true;
    elements.live.textContent = '已撤销，建议恢复为待确认。';
  }
});

render();
```

- [ ] **Step 5: Add styles for tasks, timeline blocks, reasons, states, and mobile sticky decision panel**

Append this product-state CSS to `assets/styles.css`:

```css
.calendar-controls { justify-self: end; display: flex; align-items: center; gap: 10px; }
.calendar-status { display: inline-flex; align-items: center; min-height: 44px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); padding: 0 16px; }
.text-button { min-height: 44px; border: 0; color: var(--ink-muted); background: transparent; text-decoration: underline; text-underline-offset: 4px; cursor: pointer; }
.task-list { list-style: none; }
.task-card { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--surface); padding: 14px; text-align: left; }
.task-card.is-active { border-color: var(--forest); background: var(--forest-soft); }
.task-card span, .constraint-note, .freshness-note, .boundary-note { color: var(--ink-muted); font-size: 12px; }
.constraint-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.constraint-grid label { display: grid; gap: 6px; color: var(--ink-muted); font-size: 12px; }
.constraint-grid input { width: 100%; min-height: 44px; border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 0 10px; }
.button:disabled { cursor: not-allowed; opacity: .45; }
.boundary-note { margin: 0 22px 18px; }
.timeline-block { position: absolute; top: var(--top); left: 12px; right: 12px; height: max(42px, var(--height)); border-left: 4px solid var(--clay); border-radius: var(--radius-sm); background: #efe5dc; padding: 9px 11px; overflow: hidden; }
.timeline-block.planned { border-color: var(--forest); background: var(--forest-soft); }
.timeline-block span { display: block; color: var(--ink-muted); font-size: 11px; }
.timeline-block strong { display: block; margin-top: 2px; }
.empty-state, .conflict-state { border: 1px dashed var(--line); border-radius: var(--radius-md); background: var(--surface-muted); padding: 18px; color: var(--ink-muted); line-height: 1.55; }
.timeline-empty { margin: 24px 0 0 18px; }
.conflict-state { border-color: color-mix(in srgb, var(--danger) 45%, var(--line)); color: var(--ink); }
.progress-steps { margin: 0 22px; padding: 0; list-style: none; counter-reset: progress; }
.progress-steps li { counter-increment: progress; min-height: 48px; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--line); color: var(--ink-muted); }
.progress-steps li::before { content: counter(progress); width: 24px; height: 24px; display: grid; place-items: center; border-radius: 50%; color: var(--forest); background: var(--forest-soft); font-size: 11px; }
.suggestion-card h3 { margin: 8px 0; font-family: var(--font-serif); font-size: 38px; font-weight: 400; }
.suggestion-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 18px; }
.suggestion-actions .button-primary { grid-column: 1 / -1; }
.suggestion-actions .text-button { grid-column: 1 / -1; color: rgba(255,255,255,.75); }
.freshness-note { color: rgba(255,255,255,.65); }
.toast button { border: 0; color: var(--signal); background: transparent; font-weight: 700; cursor: pointer; }

@media (max-width: 760px) {
  .calendar-controls .text-button { display: none; }
  .constraint-grid { grid-template-columns: 1fr; }
  .suggestion-panel { max-height: min(72vh, 620px); overflow: auto; }
}
```

Use `--forest-soft` for selected tasks, `--clay` for busy blocks, and `--signal` only for confirmation. Do not introduce gradients, generic icon libraries, or infinite spinners.

- [ ] **Step 6: Run automated checks**

Run:

```bash
npm test
npm run check
```

Expected: all tests pass and every JavaScript file passes syntax checking.

## Task 7: Build the Matching Landing Page

**Files:**
- Modify: `projects/app/tests/ui-contract.test.mjs`
- Create: `projects/app/index.html`
- Modify: `projects/app/assets/styles.css`

- [ ] **Step 1: Add failing marketing contract tests**

Append to `tests/ui-contract.test.mjs`:

```js
test('landing page states the promise, boundary, and concrete CTA', async () => {
  const html = await read('../index.html');
  assert.match(html, /把一句安排，变成你看得懂、愿意确认的日程/);
  assert.match(html, /不会偷偷重排整周/);
  assert.match(html, /href="app\.html"/);
  assert.match(html, /用一句话生成我的日程方案/);
});

test('landing page contains trust, workflow, comparison, and FAQ sections', async () => {
  const html = await read('../index.html');
  for (const id of ['trust', 'how-it-works', 'product', 'comparison', 'faq']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /浏览器本地/);
  assert.match(html, /外部日历/);
});
```

- [ ] **Step 2: Run the marketing tests to verify red**

Run:

```bash
node --test tests/ui-contract.test.mjs
```

Expected: FAIL because `index.html` does not exist.

- [ ] **Step 3: Create the landing page with an honest conversion flow**

Create `index.html` with these semantic sections and exact messaging:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Luma Day 为下一件重要任务找到一个可解释、由你确认的今日时间块。">
  <title>Luma Day · 今天的工作，不该靠猜</title>
  <link rel="stylesheet" href="assets/styles.css">
</head>
<body class="landing-page">
  <header class="site-header">
    <a class="brand" href="#top">Luma Day</a>
    <nav aria-label="主导航"><a href="#how-it-works">工作方式</a><a href="#product">产品预览</a><a href="#faq">FAQ</a></nav>
    <a class="button button-dark" href="app.html">开始规划今天</a>
  </header>
  <main id="top">
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">Explainable daily planning</p>
        <h1>把一句安排，变成你看得懂、愿意确认的日程。</h1>
        <p class="hero-lead">Luma Day 读取今天的忙碌信息，为下一件重要任务找到一个合理时间块。它解释原因，等你确认，不会偷偷重排整周。</p>
        <div class="hero-actions"><a class="button button-primary" href="app.html">用一句话生成我的日程方案</a><a href="#product">看看它如何决定</a></div>
      </div>
      <div class="product-mock" aria-label="Luma Day 产品预览">
        <div class="mock-tasks"><span class="mock-label">待安排</span><strong>准备发布 brief</strong><small>90 分钟 · 16:00 前</small><span>复盘本周指标</span><span>回复合作伙伴</span></div>
        <div class="mock-timeline"><span class="mock-label">今天</span><div class="mock-event">09:00 · 团队同步</div><div class="mock-space">可用时间</div><div class="mock-event">11:00 · 客户电话</div><div class="mock-plan">13:30 · 准备发布 brief</div><div class="mock-event">15:00 · 设计评审</div></div>
        <div class="mock-suggestion"><span class="mock-label">One good next move</span><strong>13:30–15:00</strong><p>连续 90 分钟，在 16:00 前完成，并符合下午偏好。</p><span class="mock-confirm">加入我的今天</span></div>
      </div>
    </section>
    <section id="trust" class="trust-strip" aria-label="信任边界"><span>仅读取示例忙碌信息</span><span>确认后才进入 TodayPlan</span><span>不修改外部日历</span></section>
    <section id="how-it-works" class="section-block"><p class="eyebrow">How it works</p><h2>少做计划，多做决定。</h2><ol class="step-grid"><li><strong>01</strong><h3>说出意图</h3><p>一句话描述任务、时长和最晚时间。</p></li><li><strong>02</strong><h3>理解理由</h3><p>查看约束、空档和最多三条可追溯理由。</p></li><li><strong>03</strong><h3>确认今天</h3><p>由你确认、换时段或跳过，外部日历保持不变。</p></li></ol></section>
    <section id="product" class="section-block product-story"><div><p class="eyebrow">Today Decision View</p><h2>任务、时间和理由，同屏但不拥挤。</h2><p>左侧保留未安排任务，中间显示今天的真实空间，右侧只出现一个下一步建议。</p></div><div class="product-detail"><p class="eyebrow">为什么是 13:30？</p><ul><li>提供连续 90 分钟</li><li>在 16:00 截止前完成</li><li>符合下午处理的偏好</li></ul><p class="boundary-note">确认只会加入应用内 TodayPlan。</p></div></section>
    <section id="comparison" class="section-block"><p class="eyebrow">Built for trust</p><h2>不是自动驾驶，也不是另一个聊天框。</h2><div class="comparison-grid"><article><h3>Luma Day</h3><p>一个建议、清楚理由、显式确认。</p></article><article><h3>全自动排程</h3><p>规则多、变化隐蔽、纠错成本高。</p></article><article><h3>纯聊天助手</h3><p>表达自然，但日程上下文难扫描。</p></article></div></section>
    <section id="faq" class="section-block"><p class="eyebrow">FAQ</p><h2>边界说在前面。</h2><details><summary>它会修改我的外部日历吗？</summary><p>不会。本地演示只读取确定性的示例忙碌信息，确认结果仅保存在浏览器本地 TodayPlan。</p></details><details><summary>这是真实的 AI 集成吗？</summary><p>第一版使用可测试的本地意图解析和确定性规划规则，重点验证解释、控制和决策动线。</p></details><details><summary>数据保存在哪里？</summary><p>任务和 TodayPlan 只保存在当前浏览器的 localStorage 中。</p></details></section>
    <section class="final-cta"><p class="eyebrow">Your day, with reasons</p><h2>今天的工作，不该靠猜。</h2><a class="button button-primary" href="app.html">开始本地演示</a></section>
  </main>
  <footer><span>Luma Day · Local MVP</span><span>External calendars stay untouched.</span></footer>
</body>
</html>
```

- [ ] **Step 4: Extend the shared CSS for editorial landing polish**

Use the same tokens as the app. Add:

```css
.site-header { min-height: 76px; display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 0 max(24px, calc((100vw - 1280px) / 2)); }
.site-header nav { display: flex; gap: 24px; }
.hero { min-height: 760px; display: grid; grid-template-columns: minmax(0,.9fr) minmax(520px,1.1fr); align-items: center; gap: 64px; max-width: 1280px; margin: auto; padding: 72px 24px 96px; }
.hero h1, .section-block h2, .final-cta h2 { font-family: var(--font-serif); font-weight: 400; letter-spacing: -.035em; }
.hero h1 { max-width: 760px; margin: 12px 0 24px; font-size: clamp(50px, 6.8vw, 96px); line-height: .98; }
.hero-lead { max-width: 620px; color: var(--ink-muted); font-size: 20px; line-height: 1.65; }
.hero-actions { display: flex; align-items: center; gap: 20px; margin-top: 32px; }
.product-mock { min-height: 580px; display: grid; grid-template-columns: .72fr 1.25fr .9fr; gap: 10px; border: 1px solid var(--line); border-radius: 32px; background: var(--surface); box-shadow: 0 40px 100px rgba(31,39,35,.14); padding: 18px; transform: rotate(1.2deg); }
.mock-tasks, .mock-timeline, .mock-suggestion { min-width: 0; border: 1px solid var(--line); border-radius: var(--radius-md); padding: 16px; }
.mock-tasks { display: flex; flex-direction: column; gap: 10px; }
.mock-tasks strong, .mock-tasks span:not(.mock-label) { border-radius: 10px; background: var(--surface-muted); padding: 10px; }
.mock-tasks strong { background: var(--forest-soft); }
.mock-label { color: var(--ink-muted); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; }
.mock-event, .mock-plan, .mock-space { margin-top: 14px; border-left: 3px solid var(--clay); border-radius: 8px; background: #efe5dc; padding: 10px; font-size: 12px; }
.mock-space { border-style: dashed; border-color: var(--line); color: var(--ink-muted); background: transparent; }
.mock-plan { border-color: var(--forest); background: var(--forest-soft); }
.mock-suggestion { align-self: center; color: #fff; background: var(--forest); }
.mock-suggestion strong { display: block; margin: 18px 0 10px; font-family: var(--font-serif); font-size: 30px; font-weight: 400; }
.mock-suggestion p { color: rgba(255,255,255,.74); line-height: 1.55; }
.mock-confirm { display: block; margin-top: 18px; border-radius: 10px; color: var(--forest); background: var(--signal); padding: 10px; text-align: center; font-weight: 700; }
.product-story { display: grid; grid-template-columns: 1fr 1fr; gap: 56px; align-items: center; }
.product-detail { border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--surface); padding: 30px; }
.trust-strip { display: grid; grid-template-columns: repeat(3,1fr); max-width: 1100px; margin: 0 auto; border-block: 1px solid var(--line); }
.trust-strip span { padding: 20px; text-align: center; }
.section-block { max-width: 1180px; margin: 0 auto; padding: 120px 24px; }
.step-grid, .comparison-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 18px; padding: 0; list-style: none; }
.step-grid li, .comparison-grid article { border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--surface); padding: 28px; }
.final-cta { max-width: 1180px; margin: 40px auto 80px; border-radius: 36px; color: #fff; background: var(--forest); padding: 88px; text-align: center; }

@media (max-width: 900px) {
  .hero { grid-template-columns: 1fr; min-height: auto; }
  .product-mock { min-height: 460px; transform: none; }
  .product-story { grid-template-columns: 1fr; }
  .step-grid, .comparison-grid { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .site-header nav { display: none; }
  .hero h1 { font-size: 48px; }
  .hero-actions { align-items: stretch; flex-direction: column; }
  .product-mock { grid-template-columns: 1fr; }
  .mock-tasks { display: none; }
  .trust-strip { grid-template-columns: 1fr; }
  .final-cta { margin-inline: 10px; padding: 56px 24px; }
}
```

- [ ] **Step 5: Run the full automated suite**

Run:

```bash
npm test
npm run check
```

Expected: all parser, planner, state, product shell, accessibility, and marketing contract tests pass.

## Task 8: Verify the Real Browser Experience and Fix Escaped Issues

**Files:**
- Verify: `projects/app/index.html`
- Verify: `projects/app/app.html`
- Verify: `projects/app/assets/styles.css`
- Verify: `projects/app/src/app.js`
- Regression tests: `projects/app/tests/planner.test.mjs`, `projects/app/tests/state.test.mjs`, or `projects/app/tests/ui-contract.test.mjs`

- [ ] **Step 1: Start the shared product source**

From the canonical shared source, run:

```bash
python3 -m http.server 4173 --directory .
```

Expected: `Serving HTTP on ... port 4173`.

- [ ] **Step 2: Verify the landing conversion path in the in-app Browser**

Open `http://127.0.0.1:4173/` and verify:

1. Hero, product mock, trust strip, three-step flow, comparison, FAQ, and final CTA render.
2. The primary CTA label is “用一句话生成我的日程方案”.
3. The page explicitly says it does not modify external calendars.
4. The CTA navigates to `/app.html`.
5. Browser console has no warning or error from product code.

- [ ] **Step 3: Verify the product main path**

In `/app.html`:

1. Click “使用示例日历”.
2. Confirm the timeline shows 团队同步、客户电话、设计评审.
3. Enter `下午 4 点前安排 90 分钟准备发布 brief`.
4. Confirm extracted duration is 90 minutes and deadline is 16:00.
5. Generate a suggestion.
6. Verify the suggestion is 13:30–15:00 and shows no more than three reasons.
7. Confirm it and verify the new TodayPlan block appears immediately.
8. Verify the toast says the external calendar was not changed.
9. Undo and verify the block disappears and the suggestion returns.

- [ ] **Step 4: Verify recovery states**

Use the UI to verify:

1. A task without duration requests duration rather than inventing it.
2. A 240-minute task before noon shows the no-slot explanation.
3. Mark the sample calendar stale using the exposed demo status control; generation is blocked until refresh.
4. Refresh preserves tasks and TodayPlan.
5. Reload restores persisted tasks and TodayPlan from localStorage.

The visible “模拟数据过期” control is required by the Task 5 shell contract. Do not replace it with a debug query parameter or hidden control.

- [ ] **Step 5: Verify responsive and accessibility behavior**

At desktop, tablet, 390px mobile, and 320px minimum widths, verify:

1. No horizontal scrolling.
2. All controls remain at least 44px tall.
3. Suggestion panel does not cover the selected timeline block.
4. Keyboard Tab order follows visual order.
5. Focus is visible.
6. Live status announces generation, confirmation, and undo.
7. Reduced-motion mode removes nonessential transitions.

- [ ] **Step 6: Add the smallest regression test for every escaped defect**

For each browser-discovered defect, first add a failing test to the nearest existing test file, run it red, apply the smallest direct fix, and rerun green. Do not batch unrelated visual tweaks without proof.

## Task 9: Final Verification and Handoff

**Files:**
- Modify: `projects/app/README.md`

- [ ] **Step 1: Ensure the README matches the actual product**

Confirm the README contains the final run/test commands, route list, localStorage note, and external-calendar boundary. Remove the original mount-point-only scaffold copy.

- [ ] **Step 2: Run the complete automated proof**

Run:

```bash
npm test
npm run check
find . -type f \( -name '*.html' -o -name '*.css' -o -name '*.js' -o -name '*.mjs' \) -print0 | xargs -0 grep -nE 'TO''DO|TB''D|PLACE''HOLDER' && exit 1 || true
```

Expected: all tests and syntax checks pass; the incomplete-marker scan prints nothing.

- [ ] **Step 3: Verify shared-source visibility from every role**

From Dev and Test actor workspaces, run:

```bash
test -f projects/app/index.html
test -f projects/app/app.html
test -f projects/app/src/planner.js
```

Expected: all commands exit 0, proving the launcher-managed shared source is visible.

- [ ] **Step 4: Produce the implementation handoff record**

The final report must include:

- canonical product source path;
- routes and run command;
- exact automated verification output;
- browser-tested main and recovery paths;
- screenshots of landing and product desktop/mobile states;
- remaining limitation: deterministic local planner and sample calendar, not production AI/calendar integration;
- BuddySwitch Track/Artifact IDs used for Market, PM, and Design decisions.

No task is complete until both automated checks and real-browser verification pass.
