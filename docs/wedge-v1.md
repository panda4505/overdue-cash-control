**OVERDUE CASH CONTROL**

Updated Wedge Definition --- v1

March 2026 --- Aligned with actual build as of Milestone 2 start

> *Updated March 2026 to align with actual implementation. The wedge
> definition is provider-agnostic (it does not name specific LLM or email
> providers). The only change from the original is the ingestion email
> example, which now references Resend's .resend.app domain instead of a
> hypothetical ingest.product.com address. The constitution governs; the
> product definition specifies; this document defines the wedge scope.*

Canonical wedge statement

> *Overdue Cash Control ingests a company's open receivables data
> automatically, turns overdue invoices into a daily action queue, and
> gives SMBs a simple workflow to chase, track, pause, dispute, and
> escalate unpaid invoices until cash arrives or the case exits normal
> recovery.*

What changed from the previous version

The previous wedge definition relied on **manual CSV upload as the daily
input ritual**. That created a discipline dependency: the user had to
remember to export from their accounting tool, navigate to the product,
and upload the file regularly. For the exact type of overloaded SMB
owner this product targets, that ritual is fragile. If they skip a week,
the data goes stale, the action queue stops being useful, and the
product feels dead.

This updated version adds **automatic email-based ingestion** as an
equal first-class input path alongside manual upload, uses **AI for
friction compression** inside the ingestion layer, and ensures both
paths feed the identical processing pipeline. The core workflow, action
queue, and product boundary are unchanged.

Exact scope boundary

The product begins when:

-   An invoice is issued in the customer's accounting reality

-   It appears in the receivables data (via any supported input channel)

-   It is still open

The product ends when the invoice is:

-   Paid

-   Promised by a specific date

-   Disputed

-   Paused

-   Escalated outside the normal workflow

V1 input layer

This is the single most important architectural change from the previous
version. The input layer now has **two equal first-class paths**, both
feeding the same ingestion engine.

Path A: scheduled email ingestion

Most SMB accounting tools can schedule automatic email exports: a daily
or weekly AR aging report, open invoice list, or customer balance
summary sent to a designated email address. The product exploits this
existing capability.

Setup flow:

1.  **Step 1.** The user is given a unique product inbox address
    (Resend-managed .resend.app domain in v1, e.g.,
    receivables@abc123.resend.app; custom subdomain in future versions).

2.  **Step 2.** The user configures their accounting tool to email the
    AR aging or open invoices report to that address on a daily or
    weekly schedule. Most tools support this natively: scheduled report
    → email recipient.

3.  **Step 3.** On first received email, the AI ingestion engine
    auto-detects the file format (CSV, XLSX), identifies column
    mappings, and presents a confirmation screen: "We detected these
    columns --- does this look right?"

4.  **Step 4.** The user confirms once. The mapping is saved as a
    reusable import template.

5.  **Step 5.** From this point forward, every scheduled email is
    received and queued for preview. The user confirms each import
    before it touches live data (preview-before-commit).

This creates the **"plug and play, click a button and it works"**
experience without requiring a single API integration. The accounting
tool does the exporting. The product does the smart receiving.

Path B: manual CSV/XLSX upload

For users whose accounting tools cannot schedule email exports, or who
prefer manual control, the product supports direct file upload through
the web interface. The same AI-powered column detection and mapping
engine applies. The user experience is identical after the file arrives.
Neither path is treated as degraded or secondary.

Future input (not v1): API connectors

Native API integrations with specific accounting tools (e.g., Pohoda,
Money S3, Fakturoid, Exact, Sevdesk, Fortnox) are explicitly deferred to
v1.2 or later. They will only be built once real paying customers reveal
which three or four tools matter most. This preserves the one-person
manageability principle and prevents premature integration maintenance
burden.

Where AI earns its place in v1

The constitution states: "AI is subordinate, not central. Use AI where
it compresses labor or improves workflow decisions. Do not introduce AI
where deterministic rules are enough."

In this wedge, AI is used exclusively inside the ingestion and
reconciliation layer to compress friction that would otherwise fall on
the user. It is never customer-facing and never marketed as "AI." The
product is sold as faster, simpler, and lower effort.

AI-powered ingestion tasks

-   **Auto-detect file format and structure.** Whether the attachment is
    CSV or XLSX, the engine identifies the tabular data and extracts it
    without the user specifying the format. (PDF table parsing deferred
    to post-v1.)

-   **Auto-detect column mapping.** The engine identifies which columns
    correspond to invoice number, customer name, due date, outstanding
    amount, currency, and contact information. It presents a
    confidence-ranked mapping for one-click confirmation on first
    import, and applies the saved mapping silently on subsequent
    imports.

-   **Fuzzy customer matching across imports.** SMB exports are messy.
    The same customer may appear as "ACME s.r.o.", "Acme SRO", or "ACME
    Czech" across different exports. The engine uses fuzzy matching to
    consolidate these into a single debtor profile, with the user able
    to confirm or override.

-   **Intelligent diff on refresh.** When a new export arrives, the
    engine compares it to the previous state and infers: which invoices
    are new, which balances changed, which invoices disappeared (likely
    paid or credited), and which customer details updated. This replaces
    what would otherwise be a manual reconciliation task.

-   **Smart exception flagging.** The engine flags anomalies that
    deserve human attention: an invoice that reappeared after being
    marked paid, a balance that increased instead of decreased, a
    customer with a sudden spike in overdue invoices, or a due date that
    appears to have been modified.

What AI does not do in v1

-   It does not auto-send collection emails without user confirmation.

-   It does not predict payment likelihood or score customer risk.

-   It does not draft legal communications.

-   It does not replace deterministic rules for aging buckets,
    escalation triggers, or reminder scheduling.

These boundaries keep AI in its constitutional role: a labor-compression
tool, not a decision-maker the user has to trust blindly.

Data requirements

Required fields

  ---------------------- ------------------------------------------------
  **Field**              **Purpose**

  Invoice number         Unique identifier for deduplication and tracking

  Customer name          Debtor identification and grouping

  Invoice issue date     Timeline context

  Due date               Aging bucket calculation and action triggers

  Gross amount           Invoice value for prioritisation

  Currency               Multi-currency support

  Outstanding amount     Current balance owed

  Billing email /        Follow-up execution target
  contact                
  ---------------------- ------------------------------------------------

Optional fields

Customer ID, VAT ID, salesperson/account owner, notes, phone number,
preferred language, internal legal entity, reminder stage if tracked
externally. These enrich the workflow but are not required for the
product to function.

V1 source of truth

> *In v1, the source of truth is the customer's imported open-invoice or
> AR-aging data, received via scheduled email or manual upload. If an
> invoice is present in the most recent import, it is considered live
> and collectible.*

Operational rules

-   If the invoice is in the imported data, it is "in play."

-   The product does not attempt to prove historical sending or
    delivery.

-   The product assumes the business only provides invoices that are
    already live receivables.

-   "Sent" is a business-asserted operational state derived from the
    data export, not from SMTP tracking, Peppol delivery, ERP send logs,
    or customer open/view confirmation.

The core product loop

1\. First-time setup

Two equal first-class paths. Path A: the user receives a unique Resend
ingestion email address and configures their accounting tool to send the
AR report to it. Path B: the user uploads a file manually through the
web interface. Both paths feed the identical processing pipeline.

On first file arrival (via either path), the AI engine detects the
format and column mapping. The user confirms the mapping once and selects
the import scope type (full snapshot / partial / unknown). The mapping is
saved as a reusable import template. The user then reviews the import
preview and confirms before data touches live state. Setup is complete.

2\. Automatic refresh

Each time a new export arrives (daily, weekly, or on-demand), the system
parses it and queues a preview showing what will change. The user reviews
and confirms. On confirmation, the system updates existing invoices,
marks missing invoices as possibly paid or closed (full-snapshot imports
only), flags new overdue invoices, updates changed balances, and
preserves all activity history already logged in the product.

The user now has a current receivables universe with minimal effort.

3\. Action queue generation

The product generates a prioritised daily work queue:

-   Overdue today

-   Overdue 1--7 days

-   Overdue 8--30 days

-   Overdue 30+ days

-   High-value overdue invoices

-   Customers with multiple open invoices

-   Promises due today

-   Disputes needing follow-up

4\. Follow-up execution

From the action queue, the user can send a reminder email, log a phone
call, mark "customer promised to pay by X," mark a dispute, pause
chasing, or escalate. The product records the action and calculates the
next expected step.

5\. Next refresh cycle

On the next import, the system compares fresh data to the previous
state. If an invoice disappeared or balance went to zero, it suggests:
paid, credit note/closure, or external change. The user confirms if
needed. The cycle repeats.

Constitutional alignment check

Every design decision in this wedge is tested against the product
constitution:

  ------------------------- ---------------------------------------------
  **Principle**             **How this wedge complies**

  One-person business first Email ingestion + AI parsing eliminates
                            integration maintenance. No API connectors to
                            build or babysit in v1.

  Revenue density over      Single painful workflow. No feature spread.
  breadth                   Every element serves collections.

  Sell pain, not software   Seller says: "This stops you from forgetting
                            overdue invoices and removes manual chasing."

  Plug into reality         Works with any accounting tool that can email
                            a report. No migration. No clean API
                            required.

  Fast proof, fast install  Setup is one email configuration + one
                            confirmation. Value visible on first refresh.

  Compete where incumbents  No ERP vendor focuses on making collections
  are weak                  easy for 10-person companies.

  Owner-closeable economics An owner can test this in 15 minutes without
                            IT involvement.

  AI is subordinate         AI only compresses ingestion friction. Not
                            marketed. Not customer-facing.
  ------------------------- ---------------------------------------------

What v1 explicitly does not do

To protect scope and preserve constitutional discipline:

-   No native API integrations with accounting tools (deferred to v1.2+)

-   No PDF table parsing (CSV and XLSX sufficient for v1)

-   No SMTP mailbox tracking for send confirmation

-   No Peppol delivery confirmation

-   No invoice PDF generation or issuance

-   No full ledger or accounting functionality

-   No tax determination

-   No bank/payment rail ownership

-   No legal enforcement or regulated debt collection

-   No payment likelihood prediction or customer risk scoring

-   No auto-sending of collection emails without user confirmation

Natural expansion path after v1

**v1.1 --- Shared inbox connection.** Reply capture, reminder history,
automatic linking of payment promises or disputes from email responses.

**v1.2 --- Native import connectors.** API integrations for the 3--4
accounting tools most used by actual paying customers. Built only after
real usage data reveals which tools matter.

**v1.3 --- Light send-state enrichment.** Invoice email forwarding
confirmation, invoice copy attachment, basic send confirmation metadata.

**v1.4 --- Invoice readiness and routing.** Expanding the corridor
leftward into pre-send validation and delivery, once the collections
wedge is proven and generating revenue.

*None of these should block v1 launch.*

Engineer-facing rules

V1 sent-state rule

> *An invoice is considered active and sent for collection purposes if
> it appears in the customer's imported open-invoices or AR-aging
> dataset and is not flagged as paid, cancelled, or draft. The system
> does not attempt to verify issuance or delivery in v1. It treats the
> customer's receivables export as the operational truth source.*

V1 input-layer rule

> *Two first-class input paths feed the same processing pipeline:
> (1) automatic ingestion of emailed AR exports sent by the customer's
> accounting tool to a dedicated Resend-managed inbox, and (2) manual
> CSV/XLSX upload via the web interface. The AI engine handles format
> detection, column mapping, fuzzy customer matching, and intelligent
> diff. Both paths produce identical results. All imports go through
> preview-before-commit. No native API connectors are built in v1.*

V1 AI-use rule

> *AI is used only in the ingestion and reconciliation layer to compress
> user effort: format detection, column mapping, customer name matching,
> change inference, and anomaly flagging. AI does not auto-send
> communications, does not make collection decisions, and is not
> marketed to the customer.*

Companion documents

This wedge definition is one of five documents that govern the product:

1.  **Product Constitution** (`docs/constitution.md`) — governing principles, decision filter, beachhead definition.
2.  **Product Definition** (`docs/product-definition.md`) — screen-by-screen UX, data model, engine specs.
3.  **Build Trajectory** (`docs/trajectory.md`) — 12 milestones, session plans, exit gates.
4.  **Architecture Decision Record** (`docs/architecture.md`) — actual stack and design choices.
5.  **Build Log** (`BUILD_LOG.md`) — live implementation state, session history.
