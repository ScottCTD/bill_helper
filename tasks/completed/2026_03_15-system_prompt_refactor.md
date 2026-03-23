after a thorought read and refactor of the current system prompt, there are several questionable points:
1.
```
- Snapshots are bank balance checkpoints on a specific date.
- Reconciliation is interval-based:
  - each pair of consecutive snapshots defines one closed interval
  - closed intervals compare tracked entry change against bank balance change between the two checkpoints
  - the latest snapshot also defines one open interval from that checkpoint to today, which shows tracked activity only
- Entries on a snapshot date belong to the interval ending at that snapshot.
- Use snapshot proposals when the user gives a bank balance checkpoint for an existing account.
- Before proposing snapshot deletion, inspect the account's existing checkpoints.
- Use reconciliation reads to explain interval deltas, identify mismatched periods, and help the user find untracked transactions.
```
Does the current cli support snapshots (create and delete) proposals?
2. "If selector ambiguity is reported, ask the user for clarification before proposing a mutation."

Do we still have the selector stuff? I guess we don't need it anymore because we use ID exclusively right?
If so, prune relevant code paths for selector-based operations.

3. "- Do not assume pending proposals are directly editable through `bh`.
  If the user wants a different end state, inspect existing proposals first and then create the next appropriate resource-scoped proposal."

  I don't understand this - this is somehow redundant as bh is already review gated?
