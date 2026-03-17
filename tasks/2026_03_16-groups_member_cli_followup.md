the `bh groups add-member` and `bh groups remove-member` commands are still JSON-only. We should give them a dedicated CLI UX cleanup instead of folding them into the flat create-command work.

the follow-up should replace brittle nested JSON entrypoints with a clearer interface, likely by either:
- designing structured flags/subcommands for entry-member vs child-group-member flows, or
- keeping JSON input but documenting the payload contract much more explicitly if a good flag-based interface is not clean enough.

the task should cover:
- exact command UX for `bh groups add-member` and `bh groups remove-member`
- precise required/optional argument rules
- how existing ids vs proposal-id references are expressed
- how the help text explains the discriminated payload shape
- updating the canonical `bh` reference and generated prompt/docs once the interface is finalized

important constraints:
- `remove-member` only supports existing ids, not proposal-id references
- the payload shape is nested and discriminated by target type (`entry` vs `child_group`)
- the design should stay consistent with the simpler flag-based `bh * create` commands that already landed
