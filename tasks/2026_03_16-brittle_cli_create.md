the current cli create commands need JSON payloads which are brittle and error-prone. We should improve them by allowing specifying each field of the resource as arguments and in the help text of for example, `bh entries create` show exactly the fields needed/optional and what format/examples are expected.

we should also then update the bh cheat sheet/reference to reflect the new CLI for create commands.

the error messages are also not helpful, including those pydantic links and stuff. We should improve them by showing a more presentable error message, tailored to each resource.