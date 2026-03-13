# Email Ingestion - Bulk Import and Incremental Watch

## Status

* Proposed

## Priority

* High, after Agent Workspace V1

## Depends on

* Agent Workspace V1
* Canonical file metadata and attachment-link model
* Gmail and Outlook account connection support

## Summary

Add automatic email ingestion for connected user inboxes.

This feature has two modes:

* **Bulk import**: scan historical emails in a connected account, classify which emails are financially relevant, and create import candidates
* **Incremental watch**: monitor new emails, classify them, and create import candidates for relevant ones

The system should support:

* Gmail
* Outlook
* multiple email accounts per user

Email payloads and attachments should be stored in the canonical user data area and mounted read-only into the workspace container through `/data`.

## Goals

* Connect one or more email accounts per user
* Scan historical emails
* Watch new emails
* Classify which emails are recordable financial evidence
* Save email evidence and attachments durably
* Create reviewable import candidates
* Support attachment linking to entries
* Keep the design aligned with the backend authority model

## Non-Goals

* No full email client UX
* No sending emails
* No direct automatic final ledger writes in V1
* No agent-side email DB in this task
* No conversation-history exposure in this task

## Core Design

### Canonical authority

The backend remains authoritative for:

* connected email accounts
* provider credentials and sync state
* email metadata records
* deduplication state
* import candidates
* attachment metadata and links
* review state

### Canonical file storage

Email files and attachments are stored in the canonical user data area on the host and exposed to the sandbox through `/data`.

### Workspace access

The agent may inspect saved email files from `/data`, but must not mutate canonical email storage directly.

## Host-Side Storage Layout

Under the per-user canonical data directory, add:

```text
user_files/{user_id}/emails/{email_account}/...
```

The structure inside each `email_account` directory is implementation-specific, but it should be sensible, stable, and agent-readable.

A recommended shape is:

```text
user_files/{user_id}/emails/{email_account}/
├── account.json
├── sync_state.json
├── messages/
│   └── {message_key}/
│       ├── metadata.json
│       ├── body.txt
│       ├── body.html
│       ├── raw.eml
│       ├── attachments/
│       └── parse/
│           ├── classification.json
│           └── extraction.json
└── indexes/
```

### Notes

* `email_account` should be a backend-generated stable identifier, not a raw email address
* `message_key` should be stable and collision-safe
* exact filenames may vary by provider capability
* not every email must have every file
* the structure should remain easy for agents to inspect from the filesystem

## Data Mounted Into the Sandbox

Inside the workspace container, the user should see email data under:

```text
/data/emails/{email_account}/...
```

This mount is read-only.

The agent may:

* read email bodies
* inspect metadata
* inspect attachments
* inspect parse outputs

The agent may not:

* edit saved email files
* delete canonical email files
* alter sync state directly

## Supported Providers

### Gmail

Support:

* account connection
* historical scan
* incremental sync
* attachment retrieval

### Outlook

Support:

* account connection
* historical scan
* incremental sync
* attachment retrieval

## Account Model

Each connected email account should have canonical backend metadata including:

* account id
* user id
* provider (`gmail` or `outlook`)
* provider account identifier
* display address
* display name if available
* enabled state
* connection status
* last sync time
* provider-specific checkpoint state

## Ingestion Flow

## 1. Bulk import

1. user connects an email account
2. backend scans historical emails in batches
3. each email is normalized into a common internal model
4. relevant email payloads and attachments are saved into canonical file storage
5. classifier decides whether the email is financially relevant
6. extractor produces candidate transaction fields
7. backend deduplicates
8. backend creates import candidates for review

## 2. Incremental watch

1. provider change detection finds new emails
2. backend fetches and normalizes the new email
3. save canonical email evidence
4. classify and extract
5. deduplicate
6. create import candidate if relevant

## Normalized Email Model

Each provider email should normalize into a shared shape with fields such as:

* provider
* account id
* provider message id
* provider thread id if available
* internet message id if available
* subject
* from
* to
* cc
* sent at
* received at
* snippet
* plain text body
* html body
* attachment metadata
* folder or label info if useful

This model is backend-side and does not require a separate local DB in the workspace.

## Classification

Each email should be classified for financial relevance.

### Relevant examples

* receipts
* invoices
* bills
* payment confirmations
* subscription renewals with amount charged
* booking confirmations with payment evidence
* insurance payment notices
* rent-related payment confirmations
* account statements worth retaining as evidence

### Irrelevant examples

* newsletters
* generic promotions
* shipping updates without transaction value
* unrelated conversational mail
* spam

### Classifier output

At minimum:

* `is_relevant`
* `category`
* `confidence`
* short explanation
* extracted merchant or counterparty if available
* extracted amount and currency if available
* extracted date if available

## Import Candidates

Relevant emails should create **import candidates**, not finalized ledger entries.

An import candidate should contain:

* source email reference
* proposed entry fields
* confidence
* classification explanation
* linked attachments
* dedup status
* review status

This keeps the feature aligned with the existing review-first architecture.

## Deduplication

Deduplication is required.

Signals may include:

* provider message id
* internet message id
* attachment hash
* normalized merchant + amount + date
* similarity to existing candidates
* similarity to existing entry evidence

The system should avoid:

* duplicate import candidates from the same email
* duplicate attachment storage when the same file appears multiple times

## Attachment Model Requirements

This feature depends on the attachment model supporting:

* one entry linked to many attachments
* one attachment linked to many entries
* deduplicated stored file payloads
* group attachments derived from member entries

### Email evidence types

An email may contribute:

#### 1. File attachments

Examples:

* PDF invoice
* receipt image
* statement PDF

#### 2. The email itself

Even without a file attachment, the email body may be evidence and should be linkable.

The backend should support both.

## Frontend Requirements

### Entry details

Show linked attachments below notes.

### Email-derived evidence

The frontend should allow the user to inspect:

* source email summary
* sender
* subject
* received date
* snippet
* linked files
* extracted candidate data

### Review surface

The user should be able to review email-derived import candidates before approval.

No full mailbox UI is required.

## Agent Capabilities

The agent should be able to:

* inspect saved email evidence from `/data/emails/...`
* inspect email attachments
* create or refine entry proposals using email evidence
* link relevant files as attachments through backend-controlled flows

The agent should not directly modify canonical email files.

## Sync and Reliability

The backend should maintain provider sync state for:

* historical scan progress
* incremental watch checkpoints
* retry state where needed

Requirements:

* resumable scans
* safe retries
* rate-limit handling
* failure isolation so one bad message does not block the whole account

## Acceptance Criteria

### Connections

* user can connect multiple Gmail and Outlook accounts

### Storage

* email payloads are stored under `user_files/{user_id}/emails/{email_account}/...`
* saved email files are visible read-only inside the sandbox through `/data/emails/{email_account}/...`

### Bulk import

* historical emails can be scanned
* relevant emails create import candidates
* irrelevant emails are skipped

### Incremental watch

* new emails can be processed incrementally
* duplicates are not repeatedly imported

### Attachments

* email attachments are durably stored
* email evidence can link to entries through the canonical attachment model

### Review flow

* email ingestion produces reviewable candidates, not direct final ledger writes

## Recommended Implementation Order

1. add canonical email file storage under `user_files/{user_id}/emails/{email_account}/`
2. add backend account model and sync state
3. implement Gmail bulk import
4. implement Outlook bulk import
5. implement import candidate creation and review surface
6. implement Gmail incremental watch
7. implement Outlook incremental watch
8. improve extraction and deduplication

## Final Design Rule

For V1, email ingestion should be treated as an **evidence ingestion pipeline**:

* save the email
* save the attachments
* classify relevance
* extract structured candidate data
* deduplicate
* create reviewable import candidates
* link durable evidence through the canonical attachment model
