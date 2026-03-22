**OVERDUE CASH CONTROL**

Product Constitution

March 2026 --- Definitive Version

> *This is the governing document for Overdue Cash Control. Every
> product decision, feature request, market question, and engineering
> choice must survive this document. If something contradicts the
> constitution, the constitution wins. If something is not addressed
> here, apply the spirit of the principles and the decision filter. This
> document is referenced by the wedge definition, the product
> definition, and the build trajectory. It is the foundation they all
> stand on.*

**Contents**

1\. The constitution in one paragraph

> ***We build a one-person-manageable software business for EU SMBs by
> automating painful, repetitive invoice-to-cash operations inside messy
> existing workflows. The product must be easy to sell, easy to test,
> easy to install, and fast to prove. It must solve a widespread problem
> owners already feel, in a segment with high inertia and weak incumbent
> fit. It must generate strong recurring revenue without requiring heavy
> customization, migration, or service headcount. Everything we build
> must increase commercial force, speed to ROI, and operational leverage
> while staying inside a narrow product boundary: invoice readiness,
> routing, visibility, collections, and exception handling. We do not
> build for prestige, breadth, or technical vanity. We build for fast
> adoption, real relief, and revenue density.***

2\. Foundational purpose

This product exists to create a high-margin, one-person-manageable
software business by selling immediate operational efficiency to
European SMBs through low-friction automation of painful, recurring
invoice-to-cash workflows.

It is not built to be elegant in theory. It is built to remove costly
friction from real businesses quickly enough that owners will pay,
sellers will love to pitch it, and adoption can happen without
organizational drama.

3\. Supreme objective

> ***Build the most commercially efficient possible product for turning
> widespread SMB invoicing and collections pain into repeatable,
> fast-closing, high-retention revenue.***

That is the north star.

Not "best software." Not "most complete platform." Not "most advanced
AI." Not "most scalable architecture in the abstract."

**Commercial efficiency first.**

4\. Beachhead definition

This section defines who the first paying customers are. It is not a
description of the total addressable market. It is a precise targeting
filter that protects the product from being tested on the wrong segment
and drawing wrong conclusions.

4.1 The product is built for volume, not for relationships

A 10-person agency sending 15 invoices a month for €3,000--€25,000 each
already knows exactly who owes them money. A €15,000 late payment does
not slip through the cracks. The relationships are personal and delicate
--- automated reminders carry reputational risk. For that business,
Overdue Cash Control is a minor convenience worth €30--50/month at best.
That violates the pricing principle and the revenue density rule.

The product is structurally designed for volume: action queues, aging
buckets, batch actions, automated import cycles, pre-generated reminders
across dozens of debtors. All of that is overkill for 15 invoices and
perfectly calibrated for 50--200+ open receivables.

4.2 The ideal first customer

The beachhead customer has all of these characteristics:

-   **50+ open invoices at any given time.** Enough volume that things
    genuinely fall through cracks. The person handling collections
    cannot hold it all in their head. This is the hard minimum.

-   **Routine, transactional billing to many different customers.** Not
    5 key accounts. The relationships are commercial, not personal. A
    well-written reminder from finance@company.com is welcome, not
    offensive.

-   **A dedicated or semi-dedicated person handling collections.** A
    bookkeeper, office manager, or finance admin who is currently
    chasing payments manually and drowning in the volume.

-   **The person chasing money is not the person managing the client
    relationship.** This is what makes automated reminders safe and the
    "Bad Cop" positioning work. The human stays the relationship
    manager; the system is the professional finance department.

-   **Invoice values averaging €500--€5,000.** High enough that late
    payment hurts cash flow. Low enough that each individual invoice
    does not get personal CEO attention.

-   **Willingness to pay €100--€200/month.** Because the pain is real,
    the volume is high, and the product saves measurable hours and
    recovers measurable cash.

4.3 Target verticals

These are industries where invoice volume creates real operational
chaos:

-   Wholesalers and distributors.

-   Manufacturing suppliers.

-   Logistics and transport companies.

-   Construction subcontractors.

-   B2B service companies with recurring billing across many clients.

-   IT service providers with many maintenance contracts.

-   Staffing and temporary employment agencies.

-   Commercial cleaning companies.

-   Packaging suppliers.

-   Industrial equipment rental and leasing.

4.4 Who this product is not for in v1

-   Boutique creative agencies with fewer than 20 invoices per month.

-   Consulting firms with 5 key accounts.

-   Any business where each invoice represents a high-touch personal
    relationship.

-   Any business where automated communication carries significant
    reputational risk.

-   Businesses with invoice volumes below 50 open at any time.

*These businesses may become a future expansion tier --- especially with
the "Bad Cop" positioning and API integrations --- but they should not
shape the v1 product, the pilot, or the pricing.*

4.5 The "Bad Cop" positioning

Even in the right segment, the person sending reminders often does not
want to be the one chasing money from a customer their sales team just
signed. The product solves this by being the professional,
depersonalized finance department.

Reminders come from finance@company.com, not from a person's name. The
tone is professional and polite. The default language uses "Our records
indicate..." and "The finance department would like to bring to your
attention..." --- not "I noticed you haven't paid."

**The human stays the relationship manager. The system is the
collections function.**

This positioning should be reflected in all product copy, onboarding
messaging, reminder template defaults, and marketing: "Let Overdue Cash
Control be your finance department, so you never have to be the one
asking for money."

5\. Non-negotiable principles

5.1 One-person business first

Every major product decision must preserve the possibility that this
business can be run, supported, sold, and evolved by one highly capable
founder/operator for as long as possible.

This means: low implementation burden, low support burden, low
customization burden, low legal/compliance burden relative to value. No
dependence on large service teams. No business model that requires
enterprise account management armies.

**If a feature increases revenue potential but makes the product
operationally dependent on headcount, it is suspect.**

*Engineer translation: Build systems, onboarding, defaults, and support
flows that reduce human intervention. Prefer repeatable configuration
over bespoke delivery. Avoid feature ideas that create endless edge-case
servicing.*

5.2 Revenue density over product breadth

The product must maximize revenue per unit of founder attention.

Prioritize: painful workflows, high willingness to pay, recurring usage,
easy-to-demonstrate ROI, short time-to-value, features that make sales
easier.

Do not prioritize: completeness, nice-to-have polish, speculative future
optionality, broad category expansion.

*Engineer translation: Do not ask "would this be useful?" Ask: "Does
this help close deals faster, retain accounts longer, or raise ARPU
without proportionally raising complexity?"*

5.3 Sell pain, not software

The customer is not buying a tool. They are buying relief from: invoice
mistakes, payment delays, admin fatigue, compliance anxiety, collections
inconsistency, inbox chaos, and the awkwardness of personally chasing
money from their own customers.

The product must always be shaped around painful outcomes, not feature
vanity.

*Engineer translation: Every feature should map to a sentence a seller
can use with an owner: "this stops invoices from being rejected," "this
reduces late payments," "this removes manual chasing," "this lets the
system be the bad cop so you don't have to be." If the seller cannot
explain it in one breath, it is probably too abstract.*

5.4 Plug into reality, do not replace reality

This product wins because SMBs do not want transformation projects. The
product must sit on top of existing workflows, tolerate ugly data, work
with imperfect processes, connect lightly to old tools, and create value
before full integration exists.

*Engineer translation: Design for CSV import/export, inbox-based
workflows, partial integrations, rule-based configuration, progressive
setup. Do not assume clean APIs, perfect master data, or process
maturity. Manual upload is the guaranteed path. Email forwarding is the
convenience path. Both feed the same engine.*

5.5 Fast proof, fast install, fast adoption

The product must be easy to test, easy to implement, and able to show
visible ROI quickly. The ideal path: owner sees the pain immediately,
one workflow is activated quickly, a measurable improvement appears in
days or weeks, then expansion happens.

**Zero configuration to start.** Every setting comes pre-configured with
opinionated defaults that work for 80% of EU SMBs. The user uploads
their first file and immediately has a working collections system.
Settings exist for tuning later, not for getting started.

**The first-import wow moment must be protected.** The emotional
sequence matters: the user must feel "this product understands my
receivables and shows me what I didn't know" before encountering any
configuration related to sending reminders, setting up domains, or
managing templates. Domain setup, DNS records, and email infrastructure
must never appear in the path between signup and the first dashboard
view.

*Engineer translation: Prefer features that can be activated without
data migration, work on one entity or one team first, produce visible
output immediately, and do not require retraining anyone. Pre-generate
every action so the user's job is to approve, not to construct.*

5.6 Compete only where incumbents are weak

This product must live in neglected, ugly, operational gaps where
incumbents are clumsy, expensive, overbuilt, or not focused.

We do not go where: enterprise incumbents dominate, legal complexity
explodes, implementation becomes consulting-heavy, or category
expectations force us to become a full ERP / AP suite / tax engine.

*Engineer translation: Do not drift toward full accounting platform,
full ERP, full tax logic engine, enterprise document automation, heavy
compliance rail ownership, or regulated debt collection services. Stay
in the operational layer.*

5.7 Owner-closeable economics

The ideal buyer is a founder, owner, GM, finance manager, or operator
who can feel the pain directly and say yes without committee theater.

The product should not depend on: long procurement cycles, IT-led
strategic transformation, architecture committees, or multi-quarter
enterprise selling.

*Engineer translation: Build for demos and onboarding that make sense to
an owner-operated business, not to a Fortune 500 architecture team.
Single-user accounts in v1. No multi-user complexity until real
customers request it.*

5.8 Friction is the opportunity

We do not fear ugly niches. We target them. This product should prefer
markets where workflows are repetitive, old systems are common, manual
labor is still everywhere, owners are tired, switching costs are high,
competitors underserve the segment, and pain is tolerated because no one
has fixed it well yet. That is the hunting ground.

*Engineer translation: Optimize for annoying reality, not ideal
workflows. Tolerate messy data. Parse ugly files. Handle inconsistent
customer names. The less polished the customer's world is, the more
valuable the product becomes.*

5.9 Trust-calibrated automation

The product seeks maximum trustworthy automation. AI is one tool among
many — deterministic rules, heuristic scoring, and saved templates are
equally valid automation paths. The goal is not "AI" or "no AI" — it is
the fastest reliable path to a correct result with the smallest manual
surface.

**Governing rules:**

1.  **Deterministic where sufficient.** When rules, templates, or exact
    matching can produce a reliable result, use them. Do not add AI
    where deterministic methods work.

2.  **AI where it compresses ambiguity.** When deterministic methods
    cannot resolve ambiguity (unknown column headers, ambiguous schema
    interpretation on first-time files), use AI wherever it materially
    improves extraction, triage, or decision compression and is reliable
    enough for the task.

3.  **Expose uncertainty, never hide it.** When automation confidence is
    low — whether from deterministic scoring or AI — the product must
    surface the uncertainty explicitly. Quarantine ambiguous results
    rather than silently committing them.

4.  **Smallest pre-digested fallback.** When full automation is not
    trustworthy enough, the manual fallback must be the narrowest
    possible review surface: exact rows, exact fields, exact candidates,
    with a recommended action. The user confirms or corrects — they do
    not investigate from scratch.

5.  **Never sell "AI."** The product is sold as faster, simpler, lower
    effort, more reliable, less manual. The automation method is an
    implementation detail, not a marketing claim.

*Engineer translation: Use the strongest trustworthy automation
available — deterministic, heuristic, or AI. When confidence is high,
automate fully. When confidence drops, narrow to the smallest guided
intervention. Never bluff certainty. The product should be cheaper, more
predictable, and easier to debug because automation is calibrated to
trust, not to hype.*

5.10 Every layer must compound revenue

The product must be built so that each successful account can expand
naturally through: higher usage, more workflows, more countries, more
entities, premium automation modules, and stronger collections features.

*Engineer translation: Architect for modular expansion. The first wedge
is narrow, but the account should have natural paths to higher spend.*

6\. Data trust principles

The product handles financial operational data. Trust is not optional.
One bad experience with data integrity will lose a customer permanently.
These principles are non-negotiable engineering constraints.

6.1 Source of truth

> *In v1, the source of truth is the customer's imported open-invoice /
> AR-aging dataset. The system does not attempt to verify invoice
> issuance or delivery. If an invoice is present in the most recent
> confirmed import, it is considered live and collectible.*

This protects the build from drifting toward invoice transport
verification, send-status infrastructure, or full invoicing compliance
logic.

6.2 Preview before commit

Every import goes through a preview screen before anything touches live
data. The user sees: what will be created, updated, flagged, or closed.
They confirm before the commit happens. For email-ingested imports, the
preview is queued and the user is notified. Email imports never
auto-commit.

**One bad import that silently overwrites live data would destroy trust
instantly.**

6.3 Import scope classification

Every import template declares its scope type: full snapshot,
partial/filtered, or unknown.

**Hard rule:** Only full-snapshot imports can drive disappearance logic
(inferring that missing invoices were paid). Partial imports can add and
update but never close or imply disappearance. This is enforced in the
commit logic, not just the UI.

6.4 Audit trail

For every import: the original file is retained, the method of arrival
is logged, the template and scope type are recorded, the parsed summary
and commit result are stored, and all errors and warnings are preserved.
Import records are never deleted, even after rollback.

6.5 Rollback as import-delta reversal

Rollback is not a global undo. It is a precise reversal of one import's
recorded change set. Each commit stores: affected invoice IDs, previous
and new state snapshots for each, operation types, and generated
activity records. Rollback reverses exactly that delta. The import
record is marked as "rolled back," never deleted.

6.6 Duplicate protection

File hashing detects when the same file is submitted twice (via upload
or email). The user is warned and can skip or proceed. This prevents
double-counting from users who forward the same report twice or upload
after emailing.

6.7 Honest metrics

The money-recovered counter is a strong ROI proxy, not perfect causal
proof. It represents "recovered after active chasing in the product" ---
not "recovered because of the product." The system stores the conditions
that triggered recovery (full snapshot, invoice disappeared, action
existed, user confirmed) so the metric is auditable. No logic should
treat this number as airtight causal attribution.

6.8 Account-level activity history

In v1 with single-user accounts, the activity timeline is operational
history of the account, not precise individual attribution. Activity
records store who was logged in, but no UI or logic depends on
person-level attribution being accurate. Multi-user attribution can be
layered on later.

7\. Product boundary

The product exists in this corridor:

> ***Invoice readiness → routing → status visibility → collections
> orchestration → exception handling***

V1 focuses on status visibility, collections orchestration, and light
exception handling only. Invoice readiness and routing are future
expansion.

The product can touch: inboxes, customer billing profiles, reminders,
invoice metadata, routing rules, payment status, dispute handling.

The product should not own: the full ledger, full tax determination for
all of Europe, the bank/payment rails, legal enforcement, or deep ERP
replacement logic.

8\. Explicit exclusions

**A constitution needs things it forbids.** These exclusions are
permanent, not just "not now." If we drift into any of these, we lose
the one-person advantage and enter bad competition.

This product is not:

-   A general accounting suite.

-   A full accounts payable platform.

-   A full document-AI platform.

-   A generic ERP overlay for every back-office process.

-   A debt-collection agency.

-   A law-heavy recovery tool.

-   A "digital transformation" consultancy.

-   A heavily bespoke systems integrator.

-   A feature factory for edge cases.

-   A product optimised for low-volume, high-touch relationship
    businesses (boutique agencies, consulting firms with 5 key
    accounts).

If we drift into those, we lose.

9\. Decision filter for all future product work

Before any feature is built, it must survive all seven of these
questions:

1.  **Does this solve a painful, repetitive SMB problem** tied to
    invoice-to-cash operations?

2.  **Can the value be understood by an owner** in under 60 seconds?

3.  **Can it be implemented** without heavy migration or consulting?

4.  **Can it help close deals, retain customers, or expand revenue**
    materially?

5.  **Does it preserve** the one-person-operable model?

6.  **Does it avoid** putting us in direct competition with stronger
    incumbents?

7.  **Does it make adoption or ROI** faster, not slower?

**If the answer to any question is not clearly yes, the feature should
be rejected or deferred.**

This filter applies to feature requests from pilot users, ideas from
competitors, tempting market adjacencies, and your own ambition. The
constitution does not bend for excitement.

10\. Reminder sender model

The product supports two permanent, first-class sending paths. This is
an operator-level choice, not an in-app workflow decision. The product
does not detect, prompt, or manage transitions between them.

10.1 Model A: custom sending domain

Reminders sent through the product's email infrastructure from the
customer's own domain (e.g., finance@clientcompany.com). The customer
adds SPF/DKIM DNS records. Setup available in Settings at any time.
Stronger for deliverability and trust. Reinforces the "Bad Cop" /
finance department positioning.

10.2 Model B: draft-and-send

The product generates the complete, ready-to-send email with all details
filled in. The user copies it to their own email client and sends from
their own address. Always available, always fully functional, never
treated as a degraded experience.

10.3 Critical rule

**No business-critical path depends on custom-domain success.** The
product delivers full value --- import, analysis, action queue,
pre-generated reminders, money-recovered tracking --- regardless of
whether Model A is configured. Domain setup is optional and never gates
the value experience.

11\. Pricing principle

**Price must track pain and operational value, not cheap-software
psychology.** If the product affects collections and admin burden, it
should not be priced like a toy.

The beachhead customer has 50+ open invoices and is willing to pay
€100--€200/month because the product saves measurable hours, recovers
measurable cash, and the money-recovered counter proves it. The product
pays for itself many times over every month.

The preferred pricing model:

-   Paid onboarding/setup if needed (or free with trial).

-   Recurring monthly SaaS fee (with annual discount).

-   Modular upsells as the product expands.

-   Minimal custom work. Custom work exists only if it helps close and
    templatize future business.

**Never let services become the real product.**

12\. Refusal principle

You have explicit permission to reject feature requests, market
opportunities, and customer segments that violate this constitution.
Saying no is not a failure. It is the constitution working.

When a pilot user requests a feature, run it through the decision
filter. When a potential customer wants customization, check whether it
violates the one-person principle. When a competitor launches something
impressive, check whether it pulls you outside the product boundary.

**The purpose of the refusal principle is to prevent ambition from
destroying focus.**

13\. Support principle

A one-person product dies if support becomes artisanal. Onboarding,
diagnostics, exception handling, and customer guidance must be designed
for low support load from the start.

This means:

-   **Smart defaults.** Zero configuration to start. The product works
    immediately after first import.

-   **Self-diagnosing.** Import status, error logs, stale-data warnings,
    and anomaly flags give the user visibility into what's happening
    without contacting support.

-   **Preview before commit.** The user catches problems before they
    become support tickets.

-   **Rollback.** The user fixes their own data mistakes without founder
    intervention.

-   **Pre-generated actions.** The user does not need to figure out what
    to do. The product tells them.

-   **Daily digest.** Re-engages users without manual outreach from the
    founder.

-   **Instrumentation.** The founder can see usage patterns and identify
    struggling accounts without waiting for support emails.

If a feature would generate support tickets proportional to its
adoption, it is suspect under this principle.

14\. Engineer-facing intent

*This is the version to read at the start of every build session.*

> ***Build a product that behaves like an operational profit lever for
> high-volume EU SMBs. It must fit into messy real businesses with
> minimal disruption, automate the most painful invoice-to-cash tasks
> first, and create visible financial or labor-saving value fast enough
> that an owner would willingly pay for it after a simple trial.***

When choosing between elegance and commercial force, choose commercial
force.

When choosing between broad capability and fast adoption, choose fast
adoption.

When choosing between sophisticated infrastructure and one-person
manageability, choose one-person manageability.

When choosing between platform ambition and a sharp painful wedge,
choose the wedge.

When choosing between the user constructing actions and the product
pre-generating them, pre-generate them.

When choosing between requiring configuration and shipping smart
defaults, ship smart defaults.

When choosing between perfect causal attribution and an honest useful
proxy, build the honest proxy.

The goal is not to impress software people. The goal is to become a busy
owner's obvious decision.

14.1 Engineering principles

1.  **Upload-first.** Manual upload is the guaranteed ingestion path.
    Email is a convenience wrapper over the same engine.

2.  **Preview before commit.** Nothing touches live data without user
    confirmation.

3.  **Import-delta rollback.** Each import records a structured change
    set. Rollback reverses exactly that delta.

4.  **Scope-safe disappearance.** Only full-snapshot imports can infer
    that missing invoices were paid.

5.  **Deterministic first.** Saved templates and rule-based matching
    before LLM. AI is the fallback for ambiguity, not the foundation.

6.  **Extensible matching.** Invoice number matching first, but modular
    so fallback matchers can be added later.

7.  **Duplicate protection.** File hashing prevents double-counting.

8.  **Account-level history.** Activity records are operational history,
    not individual attribution.

9.  **Pre-generated actions.** Every queue item arrives with a
    ready-to-execute decision.

10. **Zero-config defaults.** Escalation rules, reminder templates,
    digest preferences all pre-set at account creation.

11. **Sender model independence.** No business-critical path depends on
    custom domain setup.

12. **Honest metrics.** Money recovered is a proxy, not causal proof.
    Store the conditions, keep it auditable.

13. **Instrumentation from day one.** Track the metrics that validate or
    invalidate constitutional assumptions.

15\. Business model intent

> *Revenue must come from repeatable software value, not from endless
> service labor.*

The preferred model:

-   Paid onboarding/setup (optional).

-   Recurring SaaS fee (€100--€200/month for the beachhead segment).

-   Optional usage-based pricing by invoice volume or location count.

-   Modular upsells (multi-site benchmarking, premium automation,
    advanced reporting).

-   Minimal custom work.

Custom work can exist only if it helps close and templatize future
business. Never let services become the real product.

16\. Value proposition

16.1 The standard proposition

> *We help EU SMBs plug modern invoice and collections automation into
> their existing workflows, so they make fewer invoicing mistakes, chase
> less manually, and get paid faster --- without changing their
> accounting system.*

16.2 The aggressive sales version

> ***We remove the admin friction between sending an invoice and getting
> the cash.***

16.3 The "Bad Cop" version

> *We are your finance department. We chase the money professionally and
> politely so you never have to be the one asking.*

16.4 The ROI version

> *Our users recovered €XXX,XXX in overdue payments. The product pays
> for itself before the end of the first month.*

17\. Companion documents

This constitution is the foundation. Five companion documents build on
it:

1.  **Wedge Definition.** Defines the specific v1 wedge (Overdue Cash
    Control), its scope boundary, input mechanisms, AI role, and
    canonical statements.

2.  **Product Definition.** Screen-by-screen UX flow, data model,
    ingestion engine spec, escalation engine, build spec, and success
    criteria.

3.  **Build Trajectory.** Ten milestones from architecture to launch,
    with session plans, exit gates, risk register, and the working model
    for building with Claude as the AI engineer.

4.  **Architecture Decision Record** (`docs/architecture.md`). Stack
    choices, project structure, Railway architecture, LLM integration
    design, email architecture, security model.

5.  **Build Log** (`BUILD_LOG.md`). Live session-by-session record of
    what exists, what works, what's broken, and what's next. The single
    source of truth for current implementation state.

All five reference this constitution. If any specification in those
documents contradicts a principle here, this document wins.
