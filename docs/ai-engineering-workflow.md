# AI Engineering Workflow

> **Purpose:** Freeze the working method used in this repo so future Claude/GPT/Codex sessions can restart cleanly without re-negotiating process. This is a workflow doc, not a product spec.

## Roles

**Lorenzo** — Human orchestrator. Supplies repo context and files. Decides priorities. Approves final direction. Runs DB tests locally (Codex sandbox has no PostgreSQL). Tiebreaker when Claude and GPT disagree.

**Claude** — Main engineer / initiator. Responsible for first-pass architecture, sequencing, scope proposals, and Codex prompt drafting. Writes implementation-complete prompts (exact file paths, exact code, exact test assertions — typically 300–800 lines). Verifies Codex output by reading actual files against invariant checklists. Claude initiates, but Claude's framing is not automatically trusted.

**GPT** — Senior reviewer / reactor. Reviews Claude's output aggressively, including the initial framing itself — not just later implementation details. Challenges scope, sequencing, trust posture, UX assumptions, and commercial implications where needed. Stays anchored to the current problem; does not wander into random redesign. Provides structured feedback for Claude (see format below).

**Codex** — Implementer (GPT-5.4 in VS Code, agent mode). Reads files, writes code, runs non-DB tests, commits. Does not make architecture decisions. Executes prompts.

## Standard loop

### 1. Fresh session starts
- Lorenzo shares relevant repo files and BUILD_LOG
- Claude reviews and proposes framing / next step / Codex prompt

### 2. GPT reviews Claude's output
- Checks framing, scope, design, sequencing, trust/risk issues, repo alignment
- Provides structured feedback (see format below)

### 3. Claude revises
- Evaluates each point — incorporates what's right, pushes back with evidence on what's wrong
- Multiple review rounds are normal (ST1 had 4, ST2 had 3, ST3 had 8+)

### 4. Codex executes
- Lorenzo sends approved prompt to Codex
- Codex writes code, runs non-DB tests, commits

### 5. Verification
- Lorenzo uploads Codex's output files and test results
- Claude reviews every changed file against the invariant checklist
- GPT reviews independently if needed
- Terminal evidence matters — passing tests alone do not automatically prove correctness
- Lorenzo runs full suite locally (including DB tests)

### 6. Fix loop (if needed)
- Claude diagnoses failures from error output
- Writes targeted fix prompts
- Repeat until green

### 7. Close-out
- BUILD_LOG updated with current state, decisions, test evidence
- opportunities.md updated if strategic insight emerged
- Next step framed before moving on

## Mandatory framing pass

A framing pass is required:
- At the start of every milestone
- At the start of every sub-task

**No Codex prompt should be drafted until the framing pass is acceptable.**

### Framing checklist

1. What is the exact goal of this step?
2. What is explicitly out of scope?
3. Which docs / repo files were reviewed?
4. What completed prior work changes the frame?
5. What decisions / invariants from BUILD_LOG constrain this step?
6. Are any items from `docs/opportunities.md` relevant now?
7. What must be deferred even if interesting?
8. What is the first implementation slice?
9. What is the validation / exit condition?

## GPT feedback format for Claude

When GPT reviews Claude's output and Claude needs actionable feedback, GPT should append a self-contained structured feedback block. This block must be copy-pasteable and must not spill into normal chat.

Use this exact format:

```text
Senior Engineer Review

Context
[What was reviewed and current repo state]

Verdict
[Approved / Not approved / Approved with changes — one line]

What stays
[Bullet list of things that are correct and should not change]

Risks/concerns
[Numbered list of specific issues found]

Required changes
[Numbered list of concrete changes needed before proceeding]

Open questions
[Questions that need answers but don't block — or "None blocking"]

Recommended next step
[One concrete action]
```

Rules:
- No fluff
- Repo-grounded (reference actual files, actual behavior, actual test results)
- Use this for feedback to Claude, not for general chat with Lorenzo

## Memory / document layering

| Document | Contains | Does NOT contain |
|----------|----------|-----------------|
| `BUILD_LOG.md` | Current state, decisions, queued items, test evidence, concise operating memory | Strategy essays, opportunity lists, workflow details |
| `docs/opportunities.md` | Strategic / commercial / product-direction discoveries not yet committed | Engineering TODOs, committed roadmap items |
| `docs/trajectory.md` | Committed roadmap with milestone ownership | Speculative ideas, uncommitted opportunities |
| `docs/ai-engineering-workflow.md` | Full collaboration process, roles, framing rules, review format | Product decisions, current state, test counts |

**Graduation rule:** Opportunities enter trajectory only when they get explicit milestone ownership. Until then they stay in opportunities.md.

## Fresh-window startup checklist

Read in this order:
1. `BUILD_LOG.md` — current state, what's next
2. `docs/ai-engineering-workflow.md` — how we work
3. `docs/opportunities.md` — strategic context
4. `docs/trajectory.md` — committed roadmap
5. Relevant product/architecture docs for the current sub-task
6. Relevant repo files for the current sub-task

**First action in a new milestone or sub-task is framing, not implementation prompting.**

## Close-out checklist

Before ending a session or moving to the next step:
1. Confirm repo changes are actually correct — not just test-green
2. Update BUILD_LOG if state, decisions, or queued items changed
3. Update opportunities.md if strategic insight emerged
4. Promote to trajectory only if roadmap commitment is made
5. Frame the next step before handing off
