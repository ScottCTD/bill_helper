This feature is to make the agent interactions more natural to the user.

The agent now will call tools in a loop until the final assistant message is produced.

However, the thinking process might be long for complex tasks. Therefore, we want it to display some intermediate thoughts to the user.

Add a tool for the agent to send some intermediate thoughts/updates (like I'm updating this ...)
This tool should be called when the agent is calling some tools, between distinct tool calls.
Like lots of propose tool calls should only have one call on this send update tool, basically not spamming.

Of the frontend, we should interleave the updates provided and other tool calls.
before the final message, I expect the assistant message bubble to be something like
- Let me first explore the current entries and tags ...
- 4 tool calls
  - tool call 1
  - tool call 2
  - ...
- I'm updating the entries and tags ...
- 100 tool calls
  - tool call 1
  - ...

Then, as the final message is coming out, the reasoning process should be collapsed as 
- {total} tool calls
FINAL MESSAGE ...
