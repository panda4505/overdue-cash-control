**OVERDUE CASH CONTROL**

Build Trajectory

From product definition to tested, distribution-ready product

Builder: Lorenzo (founder) + Codex in VS Code (code writing) + Claude (architecture, planning, reviews)

March 2026 --- Aligned with actual build as of Milestone 2 start

> *This document defines every step between the completed product
> definition and a tested product ready for distribution. The product
> is built by Lorenzo working with AI engineering partners: Codex
> (OpenAI) in VS Code for code writing and direct file editing, and
> Claude (Anthropic) for architecture, planning, and reviews. Each
> milestone has a clear exit gate. Nothing moves forward until the
> gate is passed.*
>
> *Updated March 2026 to align with actual implementation: Python/FastAPI
> stack (locked), Resend for email (replacing Postmark/Mailgun), OpenAI +
> DeepSeek for LLM (replacing Anthropic API), Railway for hosting (locked),
> build log system established, all M1 exit gates passed.*

**Contents**

1\. The working model

This project is built by Lorenzo (founder) with AI engineering partners: Claude (architecture, prompts, reviews), GPT (senior reviewer), Codex (code writing in VS Code), all coordinated through a structured review loop.

The full collaboration process — roles, review loop, framing rules, feedback format, startup and close-out checklists — is documented in `docs/ai-engineering-workflow.md`. That document is the authority on how sessions work.

`BUILD_LOG.md` is the single source of truth for current project state. It is read at the start of every session.

2\. The trajectory at a glance

The build has ten milestones, grouped into three macro-phases. The
timeline is expressed in working weeks, assuming you spend 15--25 hours
per week on build sessions and testing.

  -------- -------------------- -------------- ----------- -----------------------
  **\#**   **Milestone**        **Duration**   **Phase**   **Exit gate**

  1        Architecture & stack 1 week         **PLAN**    Tech decisions
           lock                                            documented, repo
                                                           initialised, hello
                                                           world deployed

  2        Ingestion engine     1 day          **BUILD**   Upload/email ingestion
                                                           preview works, CSV/XLSX
                                                           parse, parity proven

  3        Reconciliation & AI  1--2 weeks     **BUILD**   Fuzzy matching, diff
           layer                                           engine, anomaly flags
                                                           work

  4        Core UI              3--4 weeks     **BUILD**   Dashboard, action
                                                           queue, invoice/customer
                                                           views live

  5        Action execution     2--3 weeks     **BUILD**   Reminders send, actions
                                                           log, escalation engine
                                                           runs

  6        Retention layer      1 week         **BUILD**   Daily digest email
                                                           arrives, stale-data
                                                           warnings work

  7        Internal testing     2 weeks        **TEST**    All critical flows work
                                                           end-to-end on synthetic
                                                           data

  8        Security & trust     1--2 weeks     **TEST**    Auth, data isolation,
           hardening                                       email security, privacy
                                                           policy done

  9        Pilot with real      4--6 weeks     **TEST**    3--5 real SMBs using it
           users                                           daily, feedback
                                                           incorporated

  10       Launch-ready polish  2 weeks        **TEST**    Pricing live, signup
                                                           works, marketing site
                                                           ready to sell
  -------- -------------------- -------------- ----------- -----------------------

**Total estimated timeline: 19--34 weeks** (roughly 4.5--8 months). This
is faster than the contract-engineer version because there is no hiring,
onboarding, or communication overhead. The bottleneck is your available
hours, not engineering delivery speed.

*Honest note: the build sessions themselves will be fast. What takes
time is the work between sessions --- setting up infrastructure
accounts, configuring email providers, testing with real data,
recruiting pilot users. Do not underestimate that work.*

3\. Milestone 1 --- Architecture & stack lock --- COMPLETE

**Duration:** 1 week (completed 2026-03-19/20)

**Status:** All 8 exit gates passed. See BUILD_LOG.md for details.

3.1 Decisions locked

| Layer | Choice | Notes |
|-------|--------|-------|
| Backend | Python + FastAPI | Lorenzo's comfort language. Production Dockerfile currently pins `python:3.12-slim`; local dev/test currently runs Python 3.14.3. |
| Database | PostgreSQL 16 (Railway managed) | Relational, async via asyncpg |
| ORM | SQLAlchemy 2.0.48 (async) + Alembic | Upgraded from 2.0.36 for Python 3.14 compatibility |
| Hosting | Railway | Backend, frontend, PostgreSQL. Auto-deploy from GitHub main. |
| Email (inbound + outbound) | Resend | Domain overduecash.com verified. Inbound via tuaentoocl.resend.app. Originally planned Postmark, switched to Resend during M1. |
| LLM — Primary | OpenAI API (gpt-4o-mini) | For column mapping and fuzzy matching. Deterministic matching is primary. |
| LLM — Fallback | DeepSeek API (deepseek-chat) | OpenAI-compatible API, cost-effective fallback. |
| Frontend | Next.js 14 + Tailwind CSS + shadcn/ui | App Router, TypeScript |
| Auth | Simple auth M4, hardening M8 | Email+password with bcrypt + JWT in M4. Auth hardening in M8 (Security & Trust). |
| Domain | overduecash.com | Registered on Cloudflare |
| Code writing | Codex in VS Code (GPT-5.4, agent mode) | Direct file editing, git push |
| Architecture/planning | Claude (Anthropic) | Chat-based, generates Codex prompts |

3.2 What was built

1.  Architecture decision document (`docs/architecture.md`).
2.  Project scaffold: FastAPI backend with health check, database connection, LLM client, Alembic migrations.
3.  Next.js frontend with landing page.
4.  Both deployed to Railway with auto-deploy from GitHub main.
5.  Resend inbound email webhook receiving attachments and downloading them via Attachments API.
6.  Resend outbound email sending from noreply@overduecash.com, confirmed delivered to inbox.
7.  3 synthetic AR export test files with edge case documentation.
8.  Build log system with AI update instructions.
9.  All 7 database models (Account, User, Customer, Invoice, ImportRecord, ImportTemplate, Activity) created and migrated to production.
10. Product constitution and product definition committed to docs/.

3.3 Exit gate --- PASSED

> *Architecture documented. Repo deployed. Health check live. Inbound
> email webhook receives and downloads attachments. Outbound email
> delivers to inbox. 3+ AR export files ready. Build log accurate.*

4\. Milestone 2 --- Ingestion engine --- COMPLETE

**Duration:** 1 day (completed 2026-03-21, sessions 6–9)

**Status:** All repo-level exit gates passed. 169 tests green. Real
customer export validation deferred to pilot (M9). See BUILD_LOG.md
Session 9 for details.

4.1 What was built

1.  CSV/XLSX file parser (`backend/app/services/file_parser.py`):
    encoding detection with chardet + European-first fallback chain
    (UTF-8, Windows-1252, ISO-8859-1, ISO-8859-15, Windows-1250,
    ISO-8859-2) and mojibake rejection guard. Delimiter detection
    (comma, semicolon, tab). Header row detection via scoring heuristic.
    Format-shaped numeric type inference (4 patterns: space+comma,
    dot+comma, comma+dot, plain dot). Date detection (DD.MM.YYYY,
    DD/MM/YYYY, YYYY-MM-DD). Summary footer stripping. XLSX multi-sheet
    support with intelligent sheet selection.

2.  Column mapper (`backend/app/services/column_mapper.py`):
    deterministic 6-language dictionary (FR/IT/EN/CZ/DE/ES, ~150
    aliases across 14 canonical fields), saved template validation with
    always-enrich, async LLM fallback (OpenAI primary, DeepSeek
    fallback) with hallucination protection. All 6 fixtures map fully
    without LLM.

3.  Shared ingestion service (`backend/app/services/ingestion.py`):
    canonical parse → map → package preview pipeline. SHA-256 file hash.
    JSON-serializable sample rows with original headers. `to_dict()` for
    shared serialization across all entry points.

4.  Manual upload endpoint (`backend/app/routers/upload.py`): thin
    wrapper over ingestion service. Accepts CSV/TSV/XLSX multipart
    upload. Returns full preview JSON.

5.  Email webhook wiring (`backend/app/routers/webhooks.py`): thin
    wrapper over the same ingestion service. Downloads attachments from
    Resend API, filters by supported extension, calls `ingest_file()`
    for each, returns ingestion results. Skips unsupported files and
    missing download URLs with reason.

6.  6 synthetic test fixtures: 5 CSV (Czech/Pohoda, English/Fakturoid,
    Czech/messy generic, French, Italian) + 1 XLSX (German). Covering
    5 languages, 4 delimiter/encoding combinations, and all 4 number
    format patterns.

7.  169 tests: 86 parser, 48 mapper, 15 ingestion, 11 upload, 10
    webhook (including 3 upload-vs-email parity tests across all CSV
    fixtures, and 4 inline encoding fallback tests).

**Scope note:** This milestone delivered the upload-first ingestion
pipeline through to preview. Database ingestion (creating Invoice and
Customer records, ImportRecord creation, computed fields) was originally
scoped for M2 but is now sequenced into M3 (Reconciliation & AI Layer)
where it naturally belongs alongside the diff engine and fuzzy matching.

4.2 Exit gate --- PASSED

> *CSV and XLSX files parse correctly across 6 fixtures in 5 languages.
> Encoding fallback chain handles Windows-1250, ISO-8859-1, ISO-8859-15,
> ISO-8859-2 without mojibake. Column mapping works deterministically
> for all fixtures; LLM fallback tested with mocked provider. Both
> upload and email paths route through the same canonical ingestion
> service and produce identical results for the same CSV input. Manual
> upload returns full preview. Real customer export validation deferred
> to pilot (M9).*

5\. Milestone 3 --- Reconciliation & AI layer

**Duration:** 1--2 weeks

**Your role:** Validate reconciliation accuracy. Create sequential test
imports and verify every diff result.

**AI role:** Codex builds the diff engine, fuzzy matching, and anomaly
detection.

5.1 What gets built

Intelligent diff engine

1.  **Match invoices** by invoice_number. Categorise each as: new,
    updated (balance or details changed), unchanged, or disappeared.

2.  **For updated invoices:** Log changes as Activity records.

3.  **For disappeared invoices:** Flag as "possibly paid." Do not
    auto-close. Present for user confirmation.

4.  **For new invoices:** Create normally.

Fuzzy customer matching

1.  Normalise company names: strip legal suffixes (s.r.o., GmbH, SAS,
    Ltd), normalise case, trim whitespace.

2.  Compare using string similarity (Jaro-Winkler or similar) and VAT ID
    matching.

3.  High-confidence matches (\>90% or matching VAT ID): auto-merge, log
    the variant.

4.  Medium-confidence (70--90%): present to user for confirmation.

5.  Low-confidence: create as new customer.

6.  Store confirmed merge decisions for future auto-merging.

Anomaly detection

-   Balance increased from previous import.

-   Due date changed.

-   Invoice reappeared after being closed.

-   Customer has sudden spike in overdue invoices.

-   Multiple invoices from same customer all overdue (cluster risk).

5.2 Session plan

3--4 working sessions:

1.  **Session 1:** Build the diff engine. Test with a pair of sequential
    synthetic imports.

2.  **Session 2:** Build fuzzy customer matching. Test with
    intentionally messy name variants.

3.  **Session 3:** Build anomaly detection. Create test cases for each
    anomaly type.

4.  **Session 4:** Integration testing. Run a sequence of 4--5 imports
    through the full pipeline and verify every result.

5.3 Exit gate

> *A second import to the same account correctly identifies new,
> updated, unchanged, and disappeared invoices. Fuzzy matching merges
> obvious name variants and asks for confirmation on ambiguous ones.
> Anomalies are flagged. No data lost or duplicated.*

6\. Milestone 4 --- Core UI

**Duration:** 3--4 weeks

**Your role:** Daily UX review. Open each screen, try every interaction,
report what feels wrong or slow.

**AI role:** Codex builds all 9 screens defined in the product definition
document. Frontend and API endpoints.

6.1 Build order

1.  **Onboarding screen.** Shows ingestion email address, setup
    instructions, manual upload fallback.

2.  **Column mapping confirmation.** AI-detected mapping, user confirms
    or overrides, saves template.

3.  **Import preview.** The trust screen. Shows exactly what will change before anything touches live data. User confirms or cancels.

4.  **Dashboard.** Summary cards, aging breakdown, activity feed,
    last-import indicator.

5.  **Action queue.** Filterable, sortable list with priority flags and
    inline quick actions.

6.  **Invoice detail.** Two-panel: facts + activity timeline.

7.  **Customer profile.** Aggregated debtor view with all invoices and
    consolidated timeline.

8.  **Settings.** Company profile, import templates, escalation rules,
    notifications, team members.

9.  **Import status.** Log of recent imports with processing stats and
    errors.

6.2 Session plan

This is the longest milestone. Expect 8--12 working sessions:

1.  **Sessions 1--2:** Onboarding, column mapping, and import preview screens. Includes auth setup and login flow.

2.  **Sessions 3--5:** Dashboard and action queue. These are the most
    complex screens. Iterate on layout, filtering, and sorting.

3.  **Sessions 6--7:** Invoice detail and customer profile. Wire up the
    activity timelines.

4.  **Sessions 8--9:** Settings and import status screens.

5.  **Sessions 10--12:** Polish, responsive design, loading states,
    error handling, navigation. Make it feel solid.

6.3 Design principles

-   **Speed over beauty.** Use shadcn/ui components. Do not
    custom-design anything. Ship fast, polish later.

-   **Dense information.** Finance users are comfortable with tables.
    Show maximum data without scrolling.

-   **One-click actions.** Every action reachable from the row, not
    buried in sub-menus.

-   **Desktop-first.** Primary use is a morning laptop session. Mobile
    should work but is not the focus.

6.4 Exit gate

> *All 9 screens are functional with real imported data. Navigation is
> instant. All screens load in under 2 seconds. The dashboard shows
> accurate summary numbers. The action queue correctly filters and
> sorts. You can click into any invoice or customer and see the full
> picture.*

7\. Milestone 5 --- Action execution

**Duration:** 2--3 weeks

**Your role:** Test email sending (send to yourself, check formatting,
check spam scoring). Test every action type.

**AI role:** Codex builds the reminder composer, email sending, action
logging, and escalation engine.

7.1 What gets built

Reminder composer and email sending

-   Pre-populated email composer with templates.

-   Tone selector (friendly, firm, final notice).

-   Multi-invoice reminders for single customer.

-   Language selection based on debtor preference.

-   Send via outbound email provider. Log in activity timeline.

-   Schedule next recommended action after sending.

Action logging

-   Log phone call with notes.

-   Record promise with date.

-   Open and resolve disputes.

-   Pause and resume chasing (invoice and customer level).

-   Escalate invoices.

-   Add free-text notes.

Escalation engine

-   Rules-based engine runs daily and after every import.

-   Calculates next_action_date and next_action_type for each open
    invoice.

-   Respects promises, disputes, and pauses as interrupts.

-   Flags overdue invoices that are behind their expected escalation
    stage.

7.2 Session plan

5--7 working sessions:

1.  **Sessions 1--2:** Build reminder composer UI and email sending
    backend. Send test reminders to yourself.

2.  **Sessions 3--4:** Build all action types (call logging, promises,
    disputes, pause/resume, escalate, notes). Wire up activity logging.

3.  **Session 5:** Build the escalation engine. Test with various
    scenarios (fresh overdue, promise expired, paused then resumed,
    disputed).

4.  **Sessions 6--7:** Integration testing. Walk through the complete
    collection workflow start to finish. Fix edge cases.

7.3 Critical testing

Send real reminder emails to multiple test inboxes (Gmail, Outlook,
Apple Mail, corporate Exchange). Check that they do not land in spam,
that formatting is correct, and that links back to the product work.
This is non-negotiable. Bad emails kill the product's credibility.

7.4 Exit gate

> *Full collection workflow works: send reminders, log calls, record
> promises, mark disputes, pause, resume, escalate. Every action appears
> in timelines. Escalation engine calculates correct next actions.
> Reminder emails arrive in primary inbox with correct formatting.*

8\. Milestone 6 --- Retention layer

**Duration:** 1 week

**Your role:** Review the digest email content. Sign up with multiple
test accounts and verify the digest is accurate and well-timed.

**AI role:** Codex builds the digest email, stale-data warnings, and
notification system.

8.1 What gets built

-   **Daily digest email.** Sent at user's configured time. Subject:
    "\[Company\]: €47,230 overdue --- 12 actions today." Body: total
    overdue, change since yesterday, top 5 priorities, promises expiring
    today, data freshness. Functional HTML that renders in Outlook,
    Gmail, Apple Mail.

-   **Stale data warnings.** Dashboard warning if last import \>24 hours
    old. Warning in digest email. Visual timeline on import status
    screen.

-   **In-app notifications.** Promise expirations, anomaly alerts,
    import errors.

8.2 Session plan

2--3 sessions. This is a quick milestone because most of the backend
infrastructure exists from milestone 5:

1.  **Session 1:** Build the digest email generator. Create the HTML
    template. Set up the scheduled job.

2.  **Session 2:** Build stale-data warnings and in-app notifications.
    Wire up to the dashboard.

3.  **Session 3:** Test across email clients. Tune content. Fix
    rendering issues.

8.3 Exit gate

> *Daily digest arrives reliably every morning with accurate content.
> Stale-data warnings appear when imports are overdue. Promise
> expirations trigger visible notifications.*

9\. Milestone 7 --- Internal testing

**Duration:** 2 weeks

**Your role:** Primary. You are the test user. Every day for two weeks.

**AI role:** Codex fixes bugs you find. Write automated tests. Harden edge
cases.

9.1 What you do

Create 3--5 synthetic companies

Each with different export formats, different invoice volumes (10, 50,
200 invoices), different customer mixes, and different problem patterns.

Simulate daily operations for 2 weeks

1.  Set up ingestion emails for each company.

2.  Send daily export emails (prepare a sequence of evolving AR
    snapshots in advance).

3.  Open the product every morning. Work the action queue.

4.  Send test reminders. Log calls. Record promises. Escalate.

5.  Check the daily digest. Is it useful? Accurate?

6.  Introduce edge cases: empty exports, malformed files, duplicate
    imports, very large files.

7.  Track every bug, UX friction, or confusing element in a list.

Stress the ingestion layer

-   Files with weird encodings (UTF-8, Windows-1250, ISO-8859-2).

-   Emails from different providers (Gmail, Outlook, corporate SMTP).

-   Files with merged cells, hidden rows, multiple sheets.

-   Files with no header row, or headers on row 3.

-   Column mapping with headers in a different language than the
    template.

9.2 Bug fixing sessions

During these two weeks, schedule 3--4 sessions with Codex/Claude to work
through the bug list. Prioritise: critical (blocks usage), major
(degrades experience), minor (cosmetic or edge case). Fix all critical
and major bugs. Document minor bugs for later.

9.3 Exit gate

> *You have used the product daily for 2 weeks across multiple accounts.
> All critical and major bugs are fixed. The experience feels reliable.
> You would show it to a real business owner without embarrassment.*

10\. Milestone 8 --- Security & trust hardening

**Duration:** 1--2 weeks

**Your role:** Create the legal documents (privacy policy, terms).
Verify data isolation. Test email deliverability.

**AI role:** Codex implements auth hardening, data isolation
verification, email security configuration, and draft the legal
documents for your review.

10.1 What gets built

-   **Auth hardening.** Email verification, password reset, secure
    sessions, rate limiting on login.

-   **Data isolation verification.** Automated test confirming no user
    can access another account's data. Server-side role enforcement.

-   **Data security.** HTTPS everywhere, database encryption at rest,
    imported files encrypted, no sensitive data in logs, automated
    backups.

-   **Email security.** SPF, DKIM, DMARC configured. Reminder emails
    pass spam checks.

-   **Legal documents.** Privacy policy, terms of service, GDPR data
    processing agreement template, cookie policy. Codex drafts them;
    you review and adapt for Czech/EU law. Consider a brief legal review
    if budget allows.

-   **Security page.** A public page explaining how data is handled.
    This is a sales asset.

10.2 Session plan

3--4 sessions:

1.  **Session 1:** Auth hardening and data isolation tests.

2.  **Session 2:** Email security setup (you configure DNS, Codex
    writes the verification tests).

3.  **Session 3:** Legal document drafts. Security page content.

4.  **Session 4:** Final verification pass. Test everything.

10.3 Exit gate

> *Auth is solid. Data isolation is verified. Emails pass deliverability
> checks. Privacy policy and terms are published. Security page is live.
> You can credibly answer: "Why should I trust you with my invoice
> data?"*

11\. Milestone 9 --- Pilot with real users

**Duration:** 4--6 weeks

**Your role:** Primary. You recruit, onboard, support, and learn. This
is the most important milestone.

**AI role:** Codex fixes issues as they surface. Build quick patches. Help
you analyse feedback.

The goal is not revenue. The goal is to answer three questions:

1.  **Does the ingestion actually work** with accounting tools you did
    not design for?

2.  **Does the daily workflow stick?** Do users come back every morning?

3.  **Is the value felt?** Would they pay for this?

11.1 Pilot recruitment

**Start recruiting during milestone 5, not after milestone 7.** You need
lead time. Finding 3--5 willing companies takes weeks of conversations.

Target profile: 5--50 person Czech company, 50+ open invoices, chases
payments manually, uses an accounting tool that can export to CSV/XLSX,
has a finance person as daily user, and an owner who will give honest
feedback.

**Where:** Your personal and professional network first. Former
colleagues, friends who run businesses, accountants who serve multiple
clients, Czech entrepreneur communities. Frame it as: "I built a tool
for chasing overdue invoices. Can you try it free for a month and tell
me if it's useful?"

11.2 Pilot onboarding

1.  **Personal setup call (30 minutes).** Screen-share. Walk through
    onboarding. Help them configure their first export or upload.
    Confirm mapping together.

2.  **First-week daily check-in.** Message them daily: "Did the import
    work? Did you use the action queue?" This is product research.

3.  **Weeks 2--4: observe.** Let them use it independently. Monitor
    login frequency and action counts. Fix bugs as they appear.

4.  **Exit interview (30 minutes).** What was useful? What was
    confusing? What's missing? Would you pay? How much?

11.3 What you watch for

  ------------------ -------------------------- --------------------------
  **Signal**         **Good sign**              **Warning sign**

  Login frequency    Daily or near-daily        Used twice, then stopped

  Action queue usage Works through actions      Looks at dashboard but
                     regularly                  never acts

  Reminder sending   Sends reminders from the   Still uses their email
                     product                    client

  Ingestion          Imports work automatically Frequent errors,
  reliability                                   re-uploads often

  Digest email       Opens most mornings        Ignores or unsubscribes

  Willingness to pay "Yes, this saves me time"  "Nice but I wouldn't pay"
  ------------------ -------------------------- --------------------------

11.4 Bug fixing during pilot

Schedule 2--3 sessions per week with Codex/Claude during the pilot to fix
issues as they surface. Prioritise anything that breaks ingestion or the
daily workflow. Defer cosmetic issues unless they erode trust.

11.5 Exit gate

> *At least 3 real companies have used the product daily for 3+ weeks.
> Ingestion works with their real exports. They use the action queue and
> send reminders. At least 2 say they would pay. Critical bugs from
> pilot are fixed. You have a written top-10 feedback list.*

12\. Milestone 10 --- Launch-ready polish

**Duration:** 2 weeks

**Your role:** Final product decisions: pricing, marketing copy, trial
length. Create Stripe account.

**AI role:** Codex implements billing integration, build the marketing
landing page, polish onboarding, fix remaining bugs.

12.1 What gets done

Pricing and billing

-   Lock pricing based on pilot feedback and the constitutional
    principle: price tracks pain and operational value.

-   Implement billing via Stripe. Monthly subscription. Annual option
    with discount.

-   Free trial (14 or 30 days --- decide based on pilot time-to-value).

-   Pricing page on the marketing site.

Marketing site

-   Single-page landing site: what it does, who it's for, how it works,
    what it costs.

-   The pitch: "We remove the admin friction between sending an invoice
    and getting the cash."

-   Signup flow leading to onboarding.

-   Security page, privacy policy, terms linked from footer.

-   Pilot testimonials if users agree.

-   Your name and face: "Built by Lorenzo" is more trustworthy than a
    faceless brand.

Onboarding polish

-   Refine based on pilot learnings. Fix every confusion point.

-   Add contextual help text and tooltips.

-   First-time experience under 10 minutes from signup to seeing
    imported invoices.

Final fixes

-   Remaining must-fix bugs from pilot.

-   Performance check: all screens under 2 seconds.

-   Email deliverability recheck.

-   Cross-browser: Chrome, Firefox, Safari, Edge.

12.2 Session plan

4--6 sessions:

1.  **Sessions 1--2:** Stripe integration. Billing logic. Trial setup.

2.  **Sessions 3--4:** Marketing landing page. Signup flow.

3.  **Sessions 5--6:** Onboarding polish. Final bug fixes. Cross-browser
    testing.

12.3 Exit gate

> *A stranger can visit the site, understand the product, sign up,
> configure their first import, and start using it without any help from
> you. Billing works. Emails deliver. It feels professional. You are
> ready to sell.*

13\. Addressing the trust problem

You identified this clearly: you are a solo founder asking SMBs to
connect their financial data. Trust must be earned through visible
competence.

13.1 Trust signals to build in

1.  **Security page.** Specific, honest explanation of how data is
    handled. Not vague corporate language.

2.  **Visible data freshness.** The "last import" indicator proves the
    product is alive and working.

3.  **Transparent processing.** Import logs showing exactly what
    happened ("47 records processed, 3 new, 2 possibly paid") builds
    confidence.

4.  **Professional emails.** If reminders look cheap or land in spam,
    trust is destroyed. Invest in deliverability.

5.  **Pilot testimonials.** Even 2--3 quotes ("Saved me 3 hours a week")
    dramatically increase credibility.

6.  **Personal founder presence.** "Built by Lorenzo, a financial
    operations specialist in Czech Republic" is more trustworthy than
    stock photos.

14\. Risk register

  ------------------ ---------------- ---------------------------------------
  **Risk**           **Likelihood**   **Mitigation**

  Ingestion engine   **High**         Collect real export files before
  takes longer than                   starting. Test AI mapping in isolation
  expected                            first. Budget 3 weeks not 2.

  Session continuity **High**         Maintain the build log religiously.
  loss                                Store all code in Git. Never rely on
                                      AI remembering the previous
                                      session. Paste BUILD_LOG.md at the
                                      start of every session.

  Pilot recruitment  **Medium**       Start recruiting during milestone 5.
  harder than                         Personal network first. Offer it free.
  expected                            You need lead time.

  Pilot users don't  **Medium**       The daily digest is the retention hook.
  stick after week 1                  If users stop returning, the digest is
                                      failing --- fix the digest, not the
                                      dashboard.

  Email              **Medium**       Set up SPF/DKIM/DMARC early. Test with
  deliverability                      multiple providers. Warm up the sending
  problems                            domain. Use a reputable provider
                                      (Resend).

  Scope creep from   **High**         Every request must pass the
  pilot feedback                      constitutional decision filter. If it
                                      fails any of the 7 questions, reject or
                                      defer.

  Infrastructure     **Medium**       Use a PaaS (Railway/Render), not raw
  complexity                          cloud. Managed database. Managed email.
  surprises                           Minimise infrastructure you have to
                                      maintain.

  SMBs struggle to   **Medium**       Create step-by-step guides for top 5
  set up scheduled                    accounting tools. Offer manual upload
  email exports                       as equal alternative. Pilot will reveal
                                      severity.

  Code quality drift **Low**          Keep the codebase modular. Each
  over long build                     milestone's code should be
                                      self-contained. Use the build log to
                                      maintain architectural consistency
                                      across sessions.
  ------------------ ---------------- ---------------------------------------

15\. What is explicitly not in this trajectory

-   **No API integrations** with accounting tools. Deferred until real
    customers reveal which tools matter.

-   **No PDF invoice parsing.** CSV and XLSX are sufficient for launch.

-   **No mobile app.** Responsive web is enough.

-   **No multi-language UI.** English only. Reminder templates can be
    multi-language.

-   **No advanced analytics.** Dashboard and digest are sufficient.

-   **No automated sending.** All reminders require user confirmation in
    v1.

-   **No distribution activities.** This trajectory ends when the
    product is ready to sell.

16\. The trajectory in one paragraph

> *Lock the architecture in 1 week. Build the ingestion engine in 2--3
> weeks. Add reconciliation and AI in 1--2 weeks. Build the core UI in
> 3--4 weeks. Add action execution in 2--3 weeks. Wire up retention in 1
> week. Test internally for 2 weeks. Harden security for 1--2 weeks.
> Pilot with 3--5 real SMBs for 4--6 weeks. Polish and launch-prep in 2
> weeks. You do this with Codex and Claude as your AI engineers through
> focused working sessions, maintaining BUILD_LOG.md as the continuity
> backbone. At the end, you have a tested product and the only remaining
> question is distribution.*

17\. How to start

See `docs/ai-engineering-workflow.md` for the full startup checklist and collaboration process. The short version:

1. Open a new Claude chat. Upload `BUILD_LOG.md` and `docs/ai-engineering-workflow.md`.
2. State the current milestone and sub-task.
3. Run the framing pass before any implementation.
