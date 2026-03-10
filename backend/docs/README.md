# Backend Topic Map

Use this directory when the top-level backend index is still too broad.

## Files

- `runtime-and-config.md`: startup paths, environment settings, DB factories, and runtime settings behavior.
- `domain-and-http.md`: finance-domain models, schemas, services, routers, and ownership conventions.
- `agent-subsystem.md`: agent runtime, tool handlers, review/apply flow, and thread detail behavior.
- `operations.md`: migrations, tests, operational impact, and known backend constraints.

## Fastest Path By Question

- "How does the backend boot and resolve settings?" -> `runtime-and-config.md`
- "Where should this business rule live?" -> `domain-and-http.md`
- "How does the agent run/review pipeline work?" -> `agent-subsystem.md`
- "What do I need to run or verify after a backend change?" -> `operations.md`
