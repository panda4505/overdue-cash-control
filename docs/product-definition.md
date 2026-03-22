**OVERDUE CASH CONTROL**

Product Definition Document

Screen-by-screen UX • Data model • Engine specs • Build reference

March 2026 --- Aligned with actual build as of Milestone 2 start

> *This document defines what Overdue Cash Control is: who uses it, what
> they see, what data exists, and how the engines work. It is the build
> reference. It incorporates all corrections: upload-first ingestion,
> preview-before-commit, import-delta rollback, scope classification,
> deterministic-first AI, pre-generated actions, money-recovered
> counter, smart defaults, "Bad Cop" positioning, single-user accounts,
> wow moment protection, and honest metrics. The constitution governs;
> this document specifies.*
>
> *Updated March 2026 to align with actual implementation decisions:
> OpenAI/DeepSeek LLM (replacing Anthropic), Resend email (replacing
> Postmark), expanded data model fields for data lineage, recovery
> tracking, cost tracking, and activation signals. Entities not yet
> built (ReminderTemplate, EscalationRules, EventLog) are marked as
> deferred to their respective milestones. The BUILD_LOG.md tracks
> live implementation state; this document is the stable reference
> for what the product is and how it works.*

**Contents**

1\. Primary user and context

1.1 Who sits down and opens this product

The primary user works at a company matching the beachhead profile: 50+
open invoices at any time, routine transactional billing to many
customers, invoice values averaging €500--€5,000. The user is one of
three profiles:

-   **The bookkeeper / finance admin.** Handles AR day-to-day. Exports
    reports, sends reminders, logs calls, tracks promises. This is the
    person drowning in the manual work. Most common primary user.

-   **The office manager.** In smaller companies, handles collections
    alongside procurement, HR, and everything else. Collections is one
    of ten jobs they do badly because there is no time.

-   **The owner / founder.** Directly feels late payment pain. May not
    do daily chasing but checks the picture, approves escalations, and
    cares about cash flow. Often the economic buyer rather than the
    daily user.

All three share the same reality: they know roughly who owes them money,
they chase inconsistently, they forget follow-ups, and they lose track
of promises. The product must work for any of these without requiring a
different UX for each.

1.2 What triggers them to open the product

-   **The daily digest email.** Arrives every morning listing today's
    action items: invoices overdue, promises expiring, disputes needing
    follow-up, money recovered. This is the primary hook that drives
    daily return.

-   **A morning habit.** The user opens the product at the start of the
    day to work through the action queue, like checking email or a task
    list.

**Critical:** The product must never require the user to remember that
data needs updating. By the time they open it, the data should already
be current from the latest import.

1.3 What they accomplish in a session

A typical session is 10--30 minutes. The user expects to:

1.  See the current overdue picture at a glance.

2.  Know exactly which invoices need action today and why.

3.  Review pre-generated actions (reminders, follow-ups, escalations)
    and approve them with minimal editing.

4.  Feel confident that nothing is falling through the cracks.

5.  Close the product and move on to other work.

2\. Screen-by-screen UX flow

Nine screens, in the order the user encounters them. The emotional
sequence matters: the user must experience the wow moment (screen 5)
before encountering any sending or domain configuration.

2.1 Onboarding: connect your receivables

**Purpose:** Get from signup to first import in under 5 minutes.

**When seen:** First login only (or when no import template exists).

A clean single-column page with two equal-weight paths presented as
cards:

**Path A --- Automatic email ingestion.** Displays the account's unique
inbox address (Resend-managed .resend.app domain in v1, e.g.,
anything@tuaentoocl.resend.app; custom subdomain in future versions).
Clear instructions: "In your accounting tool, set up a scheduled email
report of your open invoices. Send it to this address." Visual checklist
of common accounting tools with setup hints. A "Waiting for first
email..." status indicator.

**Path B --- Manual upload.** A file drop zone accepting CSV and XLSX.
Labelled: "Or upload your open invoices file directly."

**Both paths are first-class.** Neither is labelled as "primary" or
"fallback." The copy says: "Choose whichever suits your workflow --- or
use both." Both paths feed the identical processing pipeline.

*No mention of sending domains, DNS records, or reminder configuration
appears on this screen. The only goal is getting data in.*

2.2 Column mapping confirmation

**Purpose:** Confirm that the system correctly identified the data
structure. One-time per import template.

**When seen:** After first import arrives (email or upload).

Two-column view:

-   **Left side:** Preview of imported data --- first 5--10 rows as a
    table with original column headers.

-   **Right side:** Detected mapping displayed as a vertical list of
    product fields, each showing which source column was matched, a
    confidence indicator, and a dropdown to override.

**Mapping approach:** Deterministic matching first (header dictionary
across languages + saved templates). LLM fallback only for genuinely
ambiguous files. The user sees the result, not the method.

**Scope type selector:** After confirming the mapping, the user selects
the import scope: full snapshot, partial/filtered, or unknown. A brief
explanation: "Does this file contain ALL your open invoices, or only a
filtered subset?" This choice is saved with the template.

**Actions:** "Confirm mapping" saves the template with scope type.
"Re-upload" returns to onboarding. The user can name the template (e.g.,
"Pohoda monthly AR").

2.3 Import preview (the trust screen)

**Purpose:** Show the user exactly what will change before anything
touches live data. This is the most important trust-building screen in
the product.

**When seen:** After every import --- both first and subsequent. For
email imports, queued with a notification.

The preview shows:

-   File recognised and template applied (or new mapping needed).

-   Scope type (full snapshot / partial / unknown).

-   Total rows found.

-   Invoices to create (new).

-   Invoices to update (balance or details changed, with a summary of
    what changed).

-   Invoices flagged as possibly paid/closed (disappeared from
    full-snapshot import).

-   Invoices flagged for recovery tracking (disappeared + had active
    chasing).

-   Anomalies detected (balance increased, due date changed, reappeared
    after close).

-   Duplicate warning if this file was already imported.

-   Customer matches: new customers to create, fuzzy matches to confirm.

**Actions:** "Confirm import" commits the changes. "Cancel" discards.
"Re-map" returns to column mapping. For disappeared invoices, the user
confirms whether each is "paid," "credited," or "unknown." For invoices
flagged for recovery tracking, the user confirms "recovered" status.

**For email imports:** the preview is queued. The user sees a
notification ("New import received --- review and confirm") on the
dashboard and optionally via email. Email imports never auto-commit.

2.4 Dashboard (with first-import wow moment)

**Purpose:** 10-second read on the overdue cash position. This is the
landing page after onboarding.

**When seen:** Every time the user opens the product.

First-import wow moment

After the very first confirmed import, the dashboard leads with a
high-impact summary designed as a deliberate conversion moment:

> *You have €47,230 overdue across 34 invoices. Your biggest exposure is
> ACME s.r.o. with €12,000 across 6 invoices, oldest 45 days overdue. 3
> invoices need action today.*

This should make the user think "I didn't even know it was this bad" or
"finally I can see the full picture." This moment converts trials.

Ongoing dashboard layout

Top section --- summary cards:

-   **Total overdue** (amount and count).

-   **Overdue today** (new as of today).

-   **Actions due today** (count of queue items).

-   **Promises expiring** (count).

-   **Disputes open** (count).

-   **Money recovered** (running total with period breakdowns: this
    week, this month, all time). This is a primary retention metric for
    the economic buyer.

Middle section --- aging breakdown. Horizontal bar or table: current
(not yet due), 1--7 days, 8--30 days, 31--60 days, 60+ days. Each bucket
clickable, filters the action queue.

Bottom section --- recent activity feed. Last 10--15 actions (reminders
sent, promises logged, payments detected) with timestamps.

**Last import indicator:** Always visible. "Last import: today 06:14 AM"
or "Last import: 3 days ago --- data may be stale" with warning colour
if overdue.

**Pending import notification:** If an email import is waiting for
review, a prominent banner: "New import received --- review and
confirm."

2.5 Action queue: today's work

**Purpose:** The operational core. A prioritised list of invoices
needing attention, each with a pre-generated action ready to execute.

**When seen:** Primary navigation. This is where the user spends most of
their time.

Layout

A filterable, sortable table with columns:

  --------------- -------------------------------------------------------
  **Column**      **Description**

  Priority        Visual: red (urgent/high-value), amber (action due),
                  grey (scheduled).

  Customer        Debtor name. Clickable to customer profile.

  Invoice \#      Invoice number. Clickable to invoice detail.

  Amount due      Outstanding balance with currency.

  Days overdue    Numeric. Negative = not yet due. Colour-coded by aging
                  bucket.

  Last action     "Reminder sent 3 days ago", "Call logged yesterday",
                  "No action yet."

  Pre-generated   The complete recommended next action, ready to execute.
  action          See below.

  Quick actions   Inline buttons: Review & send, Log call, Promise,
                  Pause, Escalate.
  --------------- -------------------------------------------------------

Pre-generated actions (key differentiator)

**Every queue item arrives with a pre-built, ready-to-execute
decision.** The user's job is to review and confirm, not to compose or
decide from scratch.

-   **Reminder due:** "Send this reminder to ACME --- €5,000, 14 days
    overdue." Click "Review" to see the complete pre-written email.
    Click "Send" (Model A) or "Copy to send" (Model B). One click.

-   **Promise follow-up:** "Jana at ACME promised €5,000 by March 1.
    It's March 4. Here's a follow-up email." Pre-written, one click.

-   **Escalation:** "Invoice #1234 has had 3 reminders over 30 days with
    no response. Escalate now?" One click.

-   **Call suggestion:** "Call Jana at ACME --- €12,000 across 6
    invoices. Here are the talking points."

-   **Anomaly review:** "Invoice #5678 balance increased from €3,200 to
    €5,000. Review."

The user can always edit, override, or skip. But the default is a
finished decision.

**Filters:** Aging bucket, customer, amount range, action type. Filters
persist across sessions.

**Batch actions:** Select multiple invoices for the same customer and
execute one action (e.g., send a multi-invoice reminder).

2.6 Invoice detail

**Purpose:** Everything known about a single receivable and its
collection history.

Two-panel view:

**Left panel --- invoice facts.** Invoice number, customer, issue date,
due date, original amount, outstanding amount, currency, days overdue,
aging bucket, status (open/promised/disputed/paused/escalated/closed),
debtor contact, salesperson, internal entity. Recovery flag and
conditions if applicable.

**Right panel --- activity timeline.** Chronological log of every event:

-   **System events:** "First imported on 12 Jan." "Balance updated from
    €5,000 to €3,200 on 28 Jan." "Marked as possibly paid on 15 Feb."
    "Recovery confirmed: €5,000."

-   **User actions:** "Reminder email sent on 15 Jan." "Phone call
    logged on 20 Jan --- note: spoke with Jana, promised by 31 Jan."
    "Escalated on 5 Feb."

-   **Anomaly flags:** "Balance increased from previous import."

-   **Import events:** "Updated by import #47 on 20 Jan." "Import #52
    rolled back on 25 Jan."

**Actions available:** Same as queue quick actions, plus: add free-text
note, change status manually, edit debtor contact, view customer
profile.

2.7 Customer profile (shallow)

**Purpose:** Aggregated debtor view. Answers: "How much does this
customer owe total?"

**Header:** Customer name (canonical + variants), total outstanding,
number of open invoices, average days overdue, last action date, billing
contact, preferred language.

**Invoice list:** All invoices for this customer in a compact table ---
essentially a filtered action queue.

**Consolidated timeline:** All actions across all invoices for this
debtor, merged chronologically.

**Customer-level actions:** Send a multi-invoice reminder listing all
overdue invoices. Set a customer-level note (e.g., "Always pays late but
reliable. Do not escalate before 45 days."). Pause all chasing for this
customer.

*Keep this screen shallow. If invoice detail already shows customer
context, the profile's job is grouping and customer-level actions, not
deep analytics.*

2.8 Import history and status

**Purpose:** Visibility into data flow. Critical for trust and
diagnostics.

Log of all imports showing:

-   Timestamp.

-   Source (email or manual upload).

-   File name.

-   Template used and scope type.

-   Records: total rows, new invoices, updated, flagged as closed,
    skipped/errors.

-   Commit status: confirmed, cancelled, rolled back.

-   Duplicate detection result.

-   **Rollback button** with confirmation prompt. Available for any
    committed import.

-   Link to view the original file.

-   Link to review errors/warnings for skipped records.

2.9 Settings (minimal)

Configuration the user sets once and rarely revisits. All settings come
pre-configured with smart defaults.

-   **Company profile.** Company name, default currency, default
    language, timezone.

-   **Import templates.** View, edit, delete saved column mappings. Edit
    scope type. Manage the ingestion email address.

-   **Escalation rules.** Edit the default escalation sequence. Pre-set:
    1st reminder at 7 days (friendly), 2nd at 14 (firm), final at 28,
    escalation suggestion at 35. Editable per-customer overrides
    available from the customer profile.

-   **Reminder templates.** Edit default email templates for each stage
    and tone. Pre-written in English, Czech, German, French, and Spanish
    with "finance department" framing. "Our records indicate..." not "I
    noticed you haven't paid."

-   **Sending domain.** Status of custom domain configuration (Model A).
    Setup wizard: add SPF/DKIM records, verify. Not required for the
    product to function --- Model B always available.

-   **Digest preferences.** Daily digest: on/off, time. Weekly owner
    digest: on/off, day and time.

3\. Data model

Core entities, relationships, and key fields. The engineer chooses the
database implementation. This defines what must exist conceptually.

3.1 Account

Top-level tenant. One per paying customer. Single-user in v1.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| company_name | string(255) | Display name |
| currency | string(3) | ISO 4217, default "CZK" |
| language | string(5) | For reminder templates and digest, default "en" |
| timezone | string(50) | IANA timezone, default "Europe/Prague" |
| resend_inbound_address | string(255) | Unique Resend inbound address (nullable) |
| sending_domain_status | string(20) | not_configured / pending / verified |
| first_import_at | timestamp | Activation signal: when first import was confirmed (nullable) |
| last_import_at | timestamp | Retention signal: most recent import (nullable). Stale if >7 days. |
| total_recovered_amount | decimal(14,2) | Running aggregate for money-recovered counter |
| created_at | timestamp | Auto-set |
| updated_at | timestamp | Auto-updated |

*Implementation note: digest timing fields (daily_time, weekly_day, weekly_time) deferred to M7 (retention layer). Will be added via Alembic migration.*

3.2 User

Single user per account in v1. Email + password auth. Separated from Account to avoid painful migration when multi-user arrives post-launch.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| account_id | UUID | FK to Account |
| email | string(255) | Login identifier, unique |
| hashed_password | string(255) | bcrypt hashed |
| full_name | string(255) | Display name (nullable) |
| is_active | boolean | Default true |
| created_at | timestamp | Auto-set |
| updated_at | timestamp | Auto-updated |

3.3 Import template

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| account_id | UUID | FK to Account, indexed |
| name | string(255) | User-given name |
| scope_type | string(20) | full_snapshot / partial / unknown. Hard rule: only full_snapshot drives disappearance logic. |
| column_mapping | JSONB | Maps source columns to product fields |
| delimiter | string(5) | Detected delimiter: , or ; (nullable) |
| date_format | string(30) | DD.MM.YYYY, YYYY-MM-DD, etc. (nullable) |
| number_format | string(20) | czech (space thousands, comma decimal) or standard (nullable) |
| encoding | string(30) | utf-8, windows-1250, iso-8859-2 (nullable) |
| times_used | integer | Usage counter, default 0 |
| created_at | timestamp | Auto-set |
| updated_at | timestamp | Auto-updated |

*Implementation note: mapping_method moved to ImportRecord (per-import, not per-template).*

3.4 Import record

Complete audit record of every import event. Never deleted, even after rollback.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| account_id | UUID | FK to Account, indexed |
| method | string(20) | upload / email |
| original_filename | string(500) | Original file name |
| file_hash | string(64) | SHA-256 for duplicate detection |
| original_file_path | string(500) | Path to stored original (nullable) |
| email_sender | string(255) | Sender address for method=email (nullable) |
| email_received_at | timestamp | When email was received (nullable) |
| resend_email_id | string(100) | Resend email ID for method=email (nullable) |
| template_id | UUID | FK to ImportTemplate (nullable) |
| scope_type | string(20) | full_snapshot / partial / unknown |
| rows_found | integer | Total rows in file |
| invoices_created | integer | New invoices created |
| invoices_updated | integer | Invoices with changed data |
| invoices_disappeared | integer | Missing from full-snapshot import |
| invoices_unchanged | integer | Present but no changes |
| errors | integer | Rows with errors |
| warnings_text | text | Warning details (nullable) |
| status | string(20) | pending_preview / confirmed / rolled_back / cancelled / failed |
| change_set | JSONB | Structured delta for rollback (nullable). Structure: created, updated, disappeared, customers_created, customers_merged arrays with before/after snapshots. |
| parse_duration_ms | integer | Parsing time for performance monitoring (nullable) |
| mapping_method | string(20) | deterministic / template / llm (nullable) |
| mapping_confidence | float | 0-1 confidence score (nullable) |
| llm_tokens_used | integer | LLM cost tracking (nullable) |
| created_at | timestamp | When file was received |
| confirmed_at | timestamp | When user confirmed (nullable) |
| rolled_back_at | timestamp | When rolled back (nullable) |

Indexes: (account_id, status), (account_id, file_hash).

3.5 Customer (debtor)

Created automatically from import data. Deduplicated by fuzzy matching. Soft-deleted (never hard-deleted).

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| account_id | UUID | FK to Account, indexed |
| name | string(255) | Canonical name |
| normalized_name | string(255) | Stripped of legal suffixes, normalised case, indexed |
| vat_id | string(50) | Optional. Strong deduplication key, indexed |
| company_id | string(50) | IČO in Czech context (nullable) |
| email | string(255) | Primary contact for reminders (nullable) |
| phone | string(50) | Optional |
| preferred_language | string(5) | For reminder language (nullable) |
| total_outstanding | decimal(14,2) | Cached aggregate, updated on import |
| invoice_count | integer | Cached count, updated on import |
| first_seen_at | timestamp | When this customer first appeared (nullable). For anomaly detection. |
| last_invoice_date | date | Most recent invoice date (nullable). Stale customer signal. |
| merge_history | JSONB | Auditable log of merged name variants with timestamps (nullable) |
| notes | text | Free-text notes (nullable) |
| is_paused | boolean | Customer-level chasing pause, default false |
| deleted_at | timestamp | Soft delete (nullable) |
| created_at | timestamp | Auto-set |
| updated_at | timestamp | Auto-updated |

*Implementation note: escalation_override (per-customer rules) deferred to M6.*

3.6 Invoice

Core record. Soft-deleted (never hard-deleted).

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| account_id | UUID | FK to Account |
| customer_id | UUID | FK to Customer (nullable) |
| invoice_number | string(100) | From source data |
| normalized_invoice_number | string(100) | Trimmed, case-normalised, separators stripped. Used for matching. |
| issue_date | date | When issued (nullable) |
| due_date | date | Payment due date |
| first_overdue_at | date | First date invoice became overdue (nullable). Captures real aging even for late imports. |
| gross_amount | decimal(14,2) | Original total |
| outstanding_amount | decimal(14,2) | Current balance owed |
| currency | string(3) | ISO 4217, default "CZK" |
| status | string(20) | open / promised / disputed / paused / escalated / possibly_paid / recovered / closed |
| days_overdue | integer | Calculated, default 0 |
| last_action_date | timestamp | Most recent action (nullable) |
| next_action_date | date | When next action is due (nullable) |
| next_action_type | string(50) | Recommended next step (nullable) |
| action_count | integer | Total actions taken, default 0. Recovery logic needs "at least one action existed." |
| first_seen_import_id | UUID | FK to ImportRecord — which import created this invoice (nullable) |
| last_updated_import_id | UUID | FK to ImportRecord — which import last touched it (nullable) |
| recovery_confirmed_at | timestamp | When user confirmed recovery (nullable) |
| recovery_import_id | UUID | FK to ImportRecord — which import triggered disappearance (nullable) |
| notes | text | Free-text (nullable) |
| deleted_at | timestamp | Soft delete (nullable) |
| created_at | timestamp | Auto-set |
| updated_at | timestamp | Auto-updated |

Indexes: (account_id, status), (account_id, due_date), (account_id, normalized_invoice_number), (account_id, next_action_date).

*Implementation note: fields deferred to M5/M6 (will be added via Alembic migration): pre_generated_action (JSONB), promise_date, current_reminder_stage, close_reason, aging_bucket (computed), salesperson, internal_entity, recovery_conditions (JSONB), recovery_amount.*

3.7 Activity

Every event on an invoice or customer. Account-level operational history, not individual attribution. Flexible JSONB details field for action-specific data.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| account_id | UUID | FK to Account |
| invoice_id | UUID | FK to Invoice (nullable — some activities are customer-level or account-level) |
| customer_id | UUID | FK to Customer (nullable) |
| import_id | UUID | FK to ImportRecord (nullable — for import-generated events, enables rollback tracking) |
| action_type | string(50) | See types below |
| details | JSONB | Type-specific payload (nullable). Examples: {"from_status": "open", "to_status": "promised"}, {"reminder_type": "first", "send_method": "model_a"}, {"merged_variant": "ACME SRO"} |
| performed_by | string(50) | "system" for automated actions, "user" for manual. Future: user_id for multi-user. (nullable) |
| created_at | timestamp | Auto-set |

Indexes: (account_id, created_at), (invoice_id, created_at), (customer_id, created_at), (account_id, action_type).

**Activity types:** import_committed, import_rolled_back, invoice_created, invoice_updated, invoice_disappeared, invoice_recovered, reminder_sent, reminder_drafted (Model B), call_logged, promise_recorded, promise_expired, dispute_opened, dispute_resolved, status_changed, paused, resumed, escalated, note_added, customer_created, customer_merged, balance_updated, anomaly_flagged.

3.8 Reminder template

*Deferred to Milestone 5 (Action Execution & Reminders). Will be created as a database table via Alembic migration when the reminder system is built. The spec below is the target design.*

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| account_id | UUID | FK to Account |
| stage | integer | 1 = first reminder, 2 = second, 3 = final |
| tone | string | friendly / firm / final |
| language | string | Template language |
| subject_template | string | Subject with placeholders |
| body_template | text | Body with placeholders. "Bad Cop" framing: "Our records indicate..." |

3.9 Escalation rules

*Deferred to Milestone 5 (Action Execution & Reminders). Will be created as a database table via Alembic migration. The spec below is the target design.*

| Field | Type | Notes |
|-------|------|-------|
| account_id | UUID | FK to Account |
| stages | JSONB | Ordered escalation steps |

Each stage: days_overdue_trigger, action_type (send_reminder /
suggest_call / escalate), reminder_stage, tone, interval_days. Smart
defaults pre-loaded: day 7 friendly, day 14 firm, day 21 suggest call,
day 28 final notice, day 35 escalate.

3.10 Event log (instrumentation)

*Deferred — to be built only if Activity and ImportRecord signals prove insufficient. Evaluate need during M7 (Internal Testing). Many instrumentation signals are already derivable from the Activity table and ImportRecord cost-tracking fields (parse_duration_ms, mapping_method, llm_tokens_used). The spec below is the target design if a dedicated table is warranted.*

Internal analytics events. Not visible to users. Used for pilot
validation and constitutional assumption testing.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| account_id | UUID | FK to Account |
| event_type | string | signup, first_import, import_success, import_failure, queue_opened, reminder_sent, reminder_drafted, promise_logged, recovery_confirmed, digest_sent, etc. |
| metadata | JSONB | Event-specific data |
| created_at | timestamp | Auto-set |

3.11 Entity relationships

**Built (M1-M2):**
-   Account has many Users (one in v1), Customers, Invoices, ImportRecords, ImportTemplates, Activities.
-   User belongs to Account.
-   Customer belongs to Account. Has many Invoices and Activities. Soft-deletable.
-   Invoice belongs to Account and Customer. Has many Activities. Links to ImportRecords via first_seen_import_id, last_updated_import_id, recovery_import_id. Soft-deletable.
-   Activity belongs to Account, optionally to Invoice, Customer, and/or ImportRecord.
-   ImportRecord belongs to Account and optionally to ImportTemplate. Contains change_set JSONB for rollback.
-   ImportTemplate belongs to Account. Has many ImportRecords.

**Deferred:**
-   ReminderTemplate belongs to Account. (M5)
-   EscalationRules belongs to Account. (M5)
-   EventLog belongs to Account. (If needed — evaluate M7)

4\. Ingestion engine

The automation backend that makes data input effortless. Five
responsibilities, feeding a single pipeline regardless of input method.

> *File arrives by upload or email → parse → map → preview → user
> confirms → commit → reconcile. The pipeline is identical for both
> paths.*

4.1 Email receiving

Resend handles inbound email. Each account has a unique receiving address
(Resend-managed .resend.app domain in v1). When an email arrives, Resend
sends a webhook POST to the backend with email metadata. The backend
calls the Resend Attachments API to get download URLs, downloads
CSV/XLSX attachments, and feeds them into the parsing engine. Email
metadata (sender, timestamp, Resend email ID) is logged on the
ImportRecord. Irrelevant emails (no attachments) are ignored. Multiple
attachments are processed individually.

4.2 Format detection and parsing

Parse CSV with configurable delimiters and encoding detection (UTF-8,
Windows-1250, ISO-8859-2). Parse XLSX including multi-sheet workbooks.
Detect and skip title rows, blank rows, summary footers. Output a
normalised table.

4.3 Column mapping (deterministic-first)

1.  **First pass: deterministic matching.** Compare headers against a
    dictionary of known column names across languages (Czech, German,
    French, English, Spanish). Match by exact string, normalised string,
    and common synonyms.

2.  **Second pass: saved template matching.** If the file structure
    matches a saved Import Template, apply it automatically.

3.  **Third pass (fallback): LLM mapping.** If deterministic confidence
    is low, send headers + sample rows to the OpenAI API (primary) or
    DeepSeek API (fallback). Receive confidence-scored mapping.

4.  Present final mapping for user confirmation. Save as Import Template
    with scope type.

4.4 Duplicate detection

Compute file hash (SHA-256). Compare against previous imports for this
account. If duplicate detected, warn: "This file appears identical to an
import from \[timestamp\]. Skip or import anyway?"

4.5 Preview generation

After parsing and mapping, generate the preview data structure showing
everything that will change (new, updated, disappeared, anomalies,
customer matches). Hand off to the preview screen. Nothing touches live
data until user confirms.

5\. Import safety layer

5.1 Preview-before-commit

Every import presents a preview. The user reviews and clicks "Confirm
import" before anything touches live state. For email imports, the
preview is queued and the user is notified.

5.2 Scope-safe disappearance logic

Only full-snapshot imports can infer that missing invoices were paid.
Partial imports can add and update but never close or imply
disappearance. Enforced in commit logic.

5.3 Change set recording

At commit time, record a structured change set in the import record:
affected invoice IDs, previous and new state snapshots for each,
operation types (create/update/flag/close), affected customer changes,
and generated activity record IDs.

5.4 Rollback (import-delta reversal)

Rollback reverses exactly one import's recorded change set: removes
created entities, restores previous values for updated entities,
reverses import-generated activities. The import record is marked
"rolled back," never deleted. Available from import history with
confirmation.

5.5 Recovery tracking

When a full-snapshot import shows an invoice as disappeared and that
invoice had at least one action taken in the product, the preview flags
it for recovery confirmation. The user confirms. The system stores the
conditions (scope, disappearance, actions existed, user confirmed) in
the invoice's recovery_conditions field. The amount is added to the
money-recovered counter. This is an honest ROI proxy, not causal proof.

6\. Reconciliation engine

6.1 Invoice matching

**Primary: normalised invoice_number** within the account. Before
comparison: trim whitespace, normalise case, strip common separators.
Matching logic is modular so a fallback matcher (customer + amount + due
date) can be added later without rewriting the engine.

Categorise each invoice as: new, updated (balance or details changed),
unchanged, or disappeared (present before, absent now).

6.2 Fuzzy customer matching

-   Normalise company names: strip legal suffixes (s.r.o., GmbH, SAS,
    SRL, Ltd, and dotless variants), normalise case, trim whitespace.

-   Resolution follows a deterministic-first chain. In priority order:
    exact normalized name, previously confirmed alias (merge_history),
    exact VAT/tax ID, then name similarity scoring with diacritic folding.

-   High confidence exact or known-alias matches reuse the existing
    customer without creating duplicate alias memory. High confidence
    first-time non-exact matches (e.g., exact VAT/tax ID match or
    obvious typo-like variant) are recorded in merge_history so future
    imports resolve deterministically.

-   Medium confidence (ambiguous similarity): present for user
    confirmation in import preview. Conservative — qualifier-based
    near-collisions (country, branch, division variants) always require
    user review.

-   Low confidence: create as new customer.

-   Store confirmed merge decisions in merge_history for future
    auto-merging. Each confirmation makes the system permanently smarter
    for that account.

-   Same-entity resolution only. Relationship intelligence
    (parent/subsidiary, group membership) is architecturally separate
    and deferred. See BUILD_LOG decisions #23, #26.

Exact thresholds and implementation details are tracked in BUILD_LOG
decisions and in the code (`services/customer_matching.py`).

6.3 Anomaly detection

-   Balance increased from previous import.

-   Due date changed.

-   Invoice reappeared after being closed.

-   Customer has sudden spike in overdue invoices.

-   Multiple invoices from same customer all overdue (cluster risk).

Anomalies appear in the import preview and in the action queue.

7\. Escalation engine

Rules-based (not AI). Runs daily and after every confirmed import.

1.  For each open invoice, compare days_overdue to the account's
    escalation rules.

2.  Determine which stage the invoice should be at.

3.  If behind expected stage, flag as priority.

4.  Set next_action_date and next_action_type.

5.  Pre-generate the appropriate action (complete reminder email, call
    suggestion, escalation recommendation) and store in the invoice's
    pre_generated_action field.

6.  Handle interrupts: promises pause the clock, disputes stop
    escalation, pauses are respected.

7.  Expired promises reset the clock and flag for follow-up with a
    pre-generated follow-up email.

8\. Reminder system

8.1 Pre-generated reminders

The escalation engine pre-generates a complete, personalised email for
every invoice due for a reminder: correct tone for the stage, correct
language for the debtor, all invoice details filled, subject line
written, "finance department" framing. Stored in the invoice's
pre_generated_action field and displayed in the action queue.

Multi-invoice reminders: when a customer has multiple overdue invoices,
generate a single email listing all of them.

8.2 Sending paths

**Model A (custom domain):** Send via product email infrastructure from
the customer's verified domain. Log as reminder_sent activity. Schedule
next action.

**Model B (draft-and-send):** Display the complete email for copying.
User sends from their own client. Log as reminder_drafted activity.
Schedule next action.

Both paths are permanently first-class. No business logic depends on
which is used.

8.3 Template defaults ("Bad Cop" framing)

Pre-written in English, Czech, German, French, and Spanish.
Professional, depersonalized tone:

-   "Our records indicate that invoice #\[number\] for \[amount\] was
    due on \[date\] and remains unpaid."

-   "The finance department would like to bring to your attention..."

-   Never "I noticed you haven't paid" or "We're writing to you
    about..."

The human stays the relationship manager. The system is the professional
finance department.

9\. Digest emails

9.1 Daily digest (for the operator)

-   Sent at configured time (default 7 AM local).

-   Subject: "\[Company\]: €47,230 overdue --- 12 actions today."

-   Body: total overdue, change since yesterday, money recovered this
    week, top 5 priorities with pre-generated actions and links,
    promises expiring today, pending import notification if applicable,
    data freshness indicator.

-   Functional HTML. Renders in Outlook, Gmail, Apple Mail.

9.2 Weekly owner digest (for the buyer)

-   Sent Monday morning (default 8 AM local).

-   Subject: "\[Company\] weekly: €8,200 recovered, €47,230 still
    overdue."

-   Body: total overdue trend (up/down vs last week), money recovered
    this week (headline number), actions taken, biggest risks,
    unresolved disputes, data freshness.

-   Designed for the person who pays the bill but may not log in daily.
    The money-recovered number is the retention hook.

9.3 Stale data warnings

-   Dashboard: warning if last import \>24 hours old.

-   In digest: "Your data has not been updated in 3 days."

-   Import status: visual timeline showing frequency and gaps.

10\. Product instrumentation

Internal analytics for validating constitutional assumptions. Not
visible to users.

-   **Activation:** Time from signup to first confirmed import.
    Percentage completing first import.

-   **Ingestion:** Upload vs email split. Success rate. Mapping
    acceptance vs override. Imports per account per week.

-   **Daily loop:** Percentage opening action queue daily. Actions per
    session. Session duration.

-   **Collections:** Reminders sent (Model A) vs drafted (Model B).
    Promises logged. Disputes. Escalations.

-   **Retention:** Digest open rates. Stale accounts (no import in 7+
    days). Money-recovered events.

-   **Trust:** Rollbacks performed. Import cancellations after preview.
    Duplicate warnings triggered.

11\. V1 success criteria

The product is ready for first paying customers when:

1.  A user matching the beachhead profile can go from signup to seeing
    their overdue picture in under 10 minutes.

2.  Both ingestion paths (upload and email) work reliably with
    real-world export files.

3.  Preview-before-commit catches problems before they touch live data.
    Rollback works cleanly.

4.  The action queue correctly prioritises invoices and every item has a
    pre-generated, ready-to-execute action.

5.  Reminders can be sent (Model A) or drafted (Model B) with one click
    after review.

6.  The money-recovered counter grows as invoices are paid and correctly
    attributes recovery conditions.

7.  Daily and weekly digests arrive reliably with accurate, actionable
    content.

8.  Import handles messy real-world data without crashing or producing
    garbage.

9.  A user session (review queue + approve actions) takes under 15
    minutes for 50--200 open invoices.

10. The product feels like a collections engine that does the thinking,
    not a tool that requires the user to think.

12\. What v1 explicitly does not do

-   No API integrations with accounting tools.

-   No PDF table parsing (CSV and XLSX sufficient).

-   No mobile app (responsive web sufficient).

-   No multi-language product UI (English only; reminder templates
    multi-language).

-   No multi-user accounts (single login per account).

-   No automated sending without user confirmation.

-   No payment processing or bank integration.

-   No customer self-service portal.

-   No advanced reporting beyond dashboard and digests.

-   No optimization for low-volume accounts (\<50 invoices).

13\. Companion documents

1.  **Product Constitution** (`docs/constitution.md`). Governing principles, beachhead
    definition, decision filter, explicit exclusions. If this document
    contradicts the constitution, the constitution wins.

2.  **Wedge Definition.** Canonical wedge statement, scope boundary,
    input mechanisms, source-of-truth statement.

3.  **Build Trajectory** (`docs/trajectory.md`). Ten milestones from
    architecture to launch, session plans, exit gates, risk register.
    AI collaboration workflow is documented separately in
    `docs/ai-engineering-workflow.md`.

4.  **Architecture Decision Record** (`docs/architecture.md`). Stack choices,
    project structure, Railway architecture, LLM integration design,
    email architecture.

5.  **Build Log** (`BUILD_LOG.md`). Live session-by-session record of what
    exists, what works, what's broken, and what's next. The single source
    of truth for current implementation state.
