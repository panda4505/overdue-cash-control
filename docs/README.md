# Docs Map — Overdue Cash Control

> **Purpose:** Index of all project documentation. Defines doc roles, reading order, update cadence, and precedence rules. Read this when joining the project or starting a new session.

## Document tiers

### Foundational (change rarely — only when product truth changes)

| Document | Role | Update when |
|----------|------|-------------|
| `constitution.md` | Governing principles, decision filter, beachhead, pricing | Core product promise or business model changes |
| `product-definition.md` | Screen-by-screen UX, data model, engine specs | Product scope or major UX changes |
| `architecture.md` | Stack choices, project structure, integration design | Stack or infrastructure changes |
| `wedge-v1.md` | Commercial wedge scope boundary, input layer, AI role | Wedge scope or go-to-market positioning changes |

### Strategic (absorbs learning — updated when meaningful insights emerge)

| Document | Role | Update when |
|----------|------|-------------|
| `opportunities.md` | Product/commercial discoveries not yet committed | Major strategic insight during build |

### Operational (changes often — updated every session or sub-task)

| Document | Role | Update when |
|----------|------|-------------|
| `BUILD_LOG.md` (repo root) | Live operating state, decisions, test evidence, queued items | Every session close-out |
| `ai-engineering-workflow.md` | AI collaboration process, roles, framing rules | Workflow process changes |

### Roadmap (changes when commitments change)

| Document | Role | Update when |
|----------|------|-------------|
| `trajectory.md` | Milestone plan, exit gates, sequencing | Roadmap commitment changes |

## Reading order for fresh sessions

1. `BUILD_LOG.md` — where the project is now
2. `ai-engineering-workflow.md` — how we work
3. `opportunities.md` — strategic context
4. `trajectory.md` — committed roadmap
5. Relevant foundational docs for the current sub-task
6. Relevant source files for the current sub-task

## Precedence rules

- If `BUILD_LOG.md` and any other doc conflict on **current implementation state**, BUILD_LOG wins.
- If `constitution.md` and any other doc conflict on **product principles**, constitution wins.
- If `trajectory.md` and `opportunities.md` conflict on **roadmap commitment**, trajectory wins. Opportunities are not commitments.
- If `architecture.md` and implementation code diverge, treat it as an inconsistency that must be resolved explicitly. `BUILD_LOG.md` owns current implementation truth; `architecture.md` should be updated when the intended architecture changes.
- If `product-definition.md` has literal thresholds or parameters that differ from BUILD_LOG decisions, BUILD_LOG decisions win for current behavior. Product-definition describes intended behavior; BUILD_LOG tracks actual decisions.

## Graduation rule

Items in `opportunities.md` enter `trajectory.md` only when they get explicit milestone ownership. Until then they remain strategic discoveries, not commitments.

## Update decision matrix

When something changes, update the narrowest owner first:

| What changed | Update |
|---|---|
| Current implementation state, test counts, blockers | `BUILD_LOG.md` |
| New invariant or operating rule | `BUILD_LOG.md` (Decisions Made) |
| Strategic / commercial insight not yet committed | `docs/opportunities.md` |
| Roadmap commitment or milestone ownership | `docs/trajectory.md` |
| Workflow or collaboration process | `docs/ai-engineering-workflow.md` |
| Foundational product principle | `docs/constitution.md` |
| Product spec (screens, data model, engines) | `docs/product-definition.md` |
| Technical stack or architecture | `docs/architecture.md` |
| Wedge scope or GTM boundary | `docs/wedge-v1.md` |
| Repo orientation or docs map | `README.md` or `docs/README.md` |
| Post-completion insight (deferred capability, doctrine learning, future opportunity) | Classify by type: operational → `BUILD_LOG.md`, strategic → `docs/opportunities.md`, foundational → `docs/constitution.md` or `docs/architecture.md` or `docs/wedge-v1.md`. Update narrowest owner only. |

**Tie-break rules:**
- Update BUILD_LOG if current state or decisions changed — it always reflects live truth
- Only promote to trajectory when a roadmap commitment exists
- Avoid duplicating the same truth across multiple docs — pick one owner
- Milestone close-outs and post-completion doctrine writebacks require a repo-wide audit gate, not only a review of changed files (see ai-engineering-workflow.md)
