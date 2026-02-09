The goal of this application is to have a all-in-one place to view and analyze personal finances. It's basically a personal financial tool.

It's a central tool to manage all bank accounts in all concurrencies. The balance for each account should be always update-to-date with what banks app tell us.
The MVP should focus on managing daily expenses and incomes. More personal financial management comes later.

The representation of each expense entry/income entry is general. Each entry can have arbitrary relationship with other entries, forming overall a graph structure.
Some common structures:

- Recurring bills: a linked list of each node an bill in the recurring chain
- Split bills: a parent expense linked to few income entries representing the action of "pay the bill but split to few friends"
- Bundle: an expense maybe paid by two separate entries due to credit limits or so on
- ... (more as needed, because the graph core is general)

Input:

- The MVP should support manual input expense and income entries, including creating relationships (links) between entries.

An entry: Basically like a markdown page with properties.

- Properties: date, name, amount, from (the source account/person), to, owner, currency, tags, status (AI pending, confirmed, ...)
- Optional markdown body: support any writeup and image embed

EntryGroup: Each entry is by itself an entry group. Connected entries are in one entry group. So we probably need each entry having a "group" property.

Other models: Account, Currency, Users, Tags, ...

Backend:

- Responsible for structuring the data and handle all use cases and logics.

Frontend:

- The frontend should be user friendly and informative, modern.
- Following exactly Notion/macos's style.
- Each entry should be a page with properties (like Notion's database page).
  - Feature: Each entry page should display a graph view representing the entry group.
- Should support multiple views (similar to a Notion database).
  - MVP: default view is the list view where entries are displayed in a list.
  - Calendar view
  - ...
- AI Native feature: Will be added later but there should be a side bar allowing interacting with the agent.
- Statistics: The Dashboard should display monthly expenses, daily expenses, and ... (with system constructed, stats and visualizations are easy)

Feature: Personal Billing Agent

- The agent should be responsible for handling input bills:
  - Given an image/natural language, the agent extract necessary expense/income (if any) and input to the system. Images might be invoices or any image that may or may not contain any expense info.
- The agent needs also to determine if an inputing entry is already in the system.
  - One caveat is that for "bundle" case, that's not duplicate bills but are valid duplications (same date same amount same card same store). In that case we need human-in-the-loop.
- Given tons of images/emails/texts, extract all expenses information and validate them with respect to the bank statements/tables and add all to the system.
- Anomalies detection: conduct deep research into the bank statement and the current system entries to find "pending" entries that are in the bank statement but not in the system. Find reasons why the balance of the system doesn't match the bank.
- Note that each agent added/removed entry should be reviewed by the user, similar to the code review functionality of coding agents.
- We don't do the MCP-server way that provides an interface to the agent. The agent is deeply tied to the system and this application should be AI-native. The agent will have low-level operating permissions instead of generic MCP interfaces. All parts of the application are tied to AI operations.
