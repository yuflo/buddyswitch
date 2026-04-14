# Source Map

Use this source map to decide where to search first, what to extract, and when to stop for login.

## How to use this map

- Prefer **public, high-signal sources first**.
- Start with **user-language** sources before polished company messaging.
- Mix **community + review/comparison + official/competitor** sources.
- If a useful source requires login, **stop and ask the user to log in before continuing**.

## Source legend

- **Priority**: High / Medium / Optional
- **Auth**:
  - Public = usually accessible without login
  - Optional login = some value is public, more depth may require login
  - Login required = do not proceed without user login
- **Signal type**: what the source is best for

---

## 1) User-language communities

### Reddit
- Priority: High
- Auth: Public, but may rate-limit or show modals
- Signal type: raw pain language, complaints, workarounds, niche communities
- Best for: discovering repeated pain, emotionally charged phrasing, “what are you using instead?” patterns
- Good extraction targets:
  - repeated complaints
  - “I hate using X because…”
  - “How do you solve…”
  - manual hacks and spreadsheet workflows
- If blocked by login/modal: stop and ask user to log in, or switch to other public communities

### Hacker News / Show HN / Launch HN
- Priority: High
- Auth: Public
- Signal type: technical user feedback, critique, market reactions, early adopter language
- Best for: dev tools, infrastructure, AI tooling, technical workflow products
- Good extraction targets:
  - critical objections
  - technical adoption friction
  - comments revealing who actually needs the product

### GitHub Issues / Discussions
- Priority: High for developer or open-source-adjacent products
- Auth: Public for many repos
- Signal type: feature requests, bugs, workflow pain, community priorities
- Best for: developer tooling, API products, OSS alternatives, integration pain
- Good extraction targets:
  - repeated feature requests
  - complaints around setup, docs, integration, pricing, limits
  - signals of where teams are forced to build internal tools

### Indie Hackers
- Priority: Medium
- Auth: Optional login
- Signal type: indie builder workflows, validation experiments, small-business pain, monetization reality
- Best for: bootstrapped SaaS, solo founder workflows, launch and validation patterns
- If login is needed for deeper threads or user context: stop and ask user to log in before continuing

### MicroConf content
- Priority: Medium
- Auth: Public
- Signal type: bootstrapped B2B SaaS guidance, positioning, validation heuristics
- Best for: interpreting signals for small teams and solo founders

### TinySeed content
- Priority: Medium
- Auth: Public
- Signal type: bootstrapped SaaS growth and PMF framing
- Best for: revenue-minded B2B SaaS and realistic PMF interpretation

---

## 2) Review and comparison sources

### G2
- Priority: High
- Auth: Public
- Signal type: structured pros/cons, competitor dissatisfaction, onboarding and pricing friction
- Best for: B2B SaaS categories and incumbent complaints
- Good extraction targets:
  - “what users dislike”
  - implementation pain
  - company-size-specific complaints
  - support, pricing, reliability, and integration complaints

### Capterra
- Priority: High
- Auth: Public
- Signal type: verified review summaries, feature tradeoffs, alternative comparisons
- Best for: SMB / mid-market tooling and operational software
- Good extraction targets:
  - review themes
  - side-by-side competitor comparisons
  - complaints by business size or role

### Product Hunt
- Priority: High for new or fast-moving product categories
- Auth: Public for many pages; some actions or deeper community behavior may need login
- Signal type: launch positioning, early traction, user comments, alternatives
- Best for: emerging categories, AI products, builder-facing products
- Good extraction targets:
  - launch framing
  - comment objections and excitement
  - similar products in adjacent categories
- If deeper comment access or account context is required: stop and ask for login

### App marketplaces (Chrome Web Store, Slack App Directory, Shopify App Store, VS Code Marketplace, etc.)
- Priority: Medium to High when relevant
- Auth: Usually public
- Signal type: short reviews, install/use friction, keyword framing, category comparison
- Best for: extensions, integrations, plugins, ecosystem tools

---

## 3) Official and competitor sources

### Competitor homepage
- Priority: High
- Auth: Public
- Signal type: positioning, ICP hints, category language, pricing anchors
- Best for: understanding what is already promised to the market
- Caution: marketing claims are not user evidence

### Pricing pages
- Priority: High
- Auth: Public
- Signal type: budget assumptions, packaging, who the product is really for
- Best for: willingness-to-pay inference and competitor tiering

### Documentation / help center / changelog
- Priority: High
- Auth: Usually public
- Signal type: real product scope, complexity, missing pieces, maturity
- Best for: reality-checking homepage claims

### Case studies / testimonials
- Priority: Medium
- Auth: Public
- Signal type: target segments and success framing
- Caution: use only as supporting evidence, never as primary proof of pain

---

## 4) Logged-in / private / high-friction sources

### X / Twitter
- Priority: Optional
- Auth: Optional login or rate-limit friction
- Signal type: fast-moving reactions, complaint bursts, distribution and positioning signals
- Use when: category is very new or conversation is heavily happening there
- If blocked: stop and ask for login

### LinkedIn posts / comments
- Priority: Optional
- Auth: Often login required for meaningful browsing
- Signal type: operator pain, B2B workflow commentary, buyer persona clues
- If blocked: stop and ask for login

### Slack / Discord communities
- Priority: Optional but high-value when niche-specific
- Auth: Login required / invite required
- Signal type: candid pain, operational workflows, buying context, language of practitioners
- Never proceed without user login and explicit confirmation

### Facebook groups / private communities / private forums
- Priority: Optional
- Auth: Login required
- Signal type: candid niche pain and peer recommendations
- Never proceed without user login and explicit confirmation

---

## Minimum source coverage rules

For most standard PMF research, aim to cover:
- at least **1 user-language community source**
- at least **1 review/comparison source**
- at least **1 official/competitor source**

When the product is developer-facing, try to include:
- GitHub Issues / Discussions
- Hacker News
- competitor docs / changelog

When the product is SMB operations / SaaS-facing, try to include:
- Reddit
- G2 or Capterra
- Product Hunt or competitor site

When the category is brand new or AI-native, try to include:
- Product Hunt
- Hacker News
- X if accessible and only after public sources are exhausted
