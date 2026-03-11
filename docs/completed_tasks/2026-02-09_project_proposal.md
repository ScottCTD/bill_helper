# Project Proposal

## Overview

The goal of this application is to have an all-in-one place to view and analyze personal finances. It's basically a personal financial tool.

It's a central tool to manage all bank accounts in all currencies. The balance for each account should be always up-to-date with what bank apps tell us.

**MVP focus:** Managing daily expenses and incomes. More personal financial management comes later.

---

## Data Model

### Graph Structure

The representation of each expense entry / income entry is general. Each entry can have arbitrary relationships with other entries, forming overall a graph structure.

Some common structures:

- **Recurring bills:** A linked list where each node is a bill in the recurring chain
- **Split bills:** A parent expense linked to few income entries representing the action of "pay the bill but split to few friends"
- **Bundle:** An expense maybe paid by two separate entries due to credit limits or so on
- ... (more as needed, because the graph core is general)

### Entry

An entry is basically like a markdown page with properties.

- **Properties:** date, name, amount, from (the source account/person), to, owner, currency, tags, status (AI pending, confirmed, ...)
- **Optional markdown body:** Support any writeup and image embed

### EntryGroup

Each entry is by itself an entry group. Connected entries are in one entry group. So we probably need each entry having a "group" property.

### Other Models

Account, Currency, Users, Tags, ...

---

## Input (MVP)

- Support manual input of expense and income entries
- Include creating relationships (links) between entries

---

## Backend

- Responsible for structuring the data and handling all use cases and logic

---

## Frontend

- User friendly and informative, modern
- Following exactly Notion / macOS style
- Each entry should be a page with properties (like Notion's database page)
  - **Feature:** Each entry page should display a graph view representing the entry group
- Support multiple views (similar to a Notion database)
  - **MVP:** Default view is the list view where entries are displayed in a list
  - Calendar view
  - ...
- **AI Native feature:** Will be added later but there should be a sidebar allowing interacting with the agent
- **Statistics:** The dashboard should display monthly expenses, daily expenses, and ... (with system constructed, stats and visualizations are easy)

---

## Feature: Personal Billing Agent

- The agent should be responsible for handling input bills:

  1. **Extraction:** Given an image/natural language, the agent extracts necessary expense/income (if any) and inputs to the system. Images might be invoices or any image that may or may not contain any expense info.

  2. **Deduplication:** The agent needs also to determine if an inputting entry is already in the system.
     - One caveat: for "bundle" case, that's not duplicate bills but are valid duplications (same date, same amount, same card, same store). In that case we need human-in-the-loop.

  3. **Bulk import:** Given tons of images/emails/texts, extract all expenses information and validate them with respect to the bank statements/tables and add all to the system.

  4. **Anomaly detection:** Conduct deep research into the bank statement and the current system entries to find "pending" entries that are in the bank statement but not in the system. Find reasons why the balance of the system doesn't match the bank.

- Each agent-added/removed entry should be reviewed by the user, similar to the code review functionality of coding agents.

- We don't do the MCP-server way that provides an interface to the agent. The agent is deeply tied to the system and this application should be AI-native. The agent will have low-level operating permissions instead of generic MCP interfaces. All parts of the application are tied to AI operations.
