# AI Engineering Workflow

> **Purpose:** Freeze the working method used in this repo so future Claude/GPT/Codex sessions can restart cleanly without re-negotiating process. This is a workflow doc, not a product spec.

## Roles

**Lorenzo** — Human orchestrator. Supplies repo context and files. Decides priorities. Approves final direction. Runs DB tests locally (Codex sandbox has no PostgreSQL). Tiebreaker when Claude and GPT disagree.

**Claude** — Main engineer / initiator. Responsible for first-pass architecture, sequencing, scope proposals, and Codex prompt drafting. Writes implementation-complete prompts (exact file paths, exact code, exact test assertions — typically 300–800 lines). Verifies Codex output by reading actual files against invariant checklists. Claude initiates, but Claude's framing is not automatically trusted.

**GPT** — Senior reviewer / reactor. Reviews Claude's output aggressively, including the initial framing itself — not just later implementation details. Challenges scope, sequencing, trust posture, UX assumptions, and commercial implications where needed. Stays anchored to the current problem; does not wander into random redesign. Provides structured feedback for Claude (see format below).

**Codex** — Implementer (GPT-5.4 in VS Code, agent mode). Reads files, writes code, runs non-DB tests, commits. Does not make architecture decisions. Executes prompts.

## Standard loop

### 1. Fresh session starts
- On Claude Desktop (Code tab): `CLAUDE.md` pre-loads all repo context automatically before the first message. The handoff prompt should contain only:
  - Session mode (framing / sub-task / Codex prompt drafting / verification / audit)
  - Step-specific files if needed (Codex output, test results, changed source files)
  - One line of context if something changed since the last BUILD_LOG update
- On browser: Lorenzo shares relevant repo files and BUILD_LOG as before.
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
6. Route post-completion insights to the correct doc owner:
   - What happened and what was deferred → BUILD_LOG
   - Future capabilities not yet committed → opportunities.md
   - Enduring product principle change → constitution.md
   - Technical design principle change → architecture.md
   - Wedge scope or commercial positioning change → wedge-v1.md
   - Update the narrowest owner only — do not duplicate the same truth across docs

## Review gate vs audit gate

Two different verification levels exist. They are not interchangeable.

**Review gate (every sub-task and prompt):**
- Validate the implementation, prompt, or changed files
- Check directly related files for consistency
- Verify test results and invariant checklists
- This is the standard GPT review loop

**Audit gate (milestone close-outs and doctrine changes):**
- Full repo-wide scan for contradictions across all docs
- Check shared terminology, AI/automation role claims, stale milestone references, threshold values, and invariant statements against current implementation truth
- Every doc that references the changed concept must be checked, not just the edited files
- Discovered drift is patched in the same close-out pass

**When the audit gate is mandatory:**
- At every milestone close-out
- After any docs-consolidation pass
- After post-completion insight writeback that changes foundational doctrine (constitution, architecture, wedge)

**When the audit gate is optional:**
- Sub-task close-outs where only implementation files changed and no shared doctrine was modified

**Why this exists:** During M3 close-out, the normal review gate approved a docs consolidation prompt that left 10+ stale contradictions in files outside the edited sections. A full-repo audit caught them. The review gate validates what changed; the audit gate validates what should have changed but didn't.
