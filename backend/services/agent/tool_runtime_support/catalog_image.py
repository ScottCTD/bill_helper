# CALLING SPEC:
# - Purpose: define image-related tool definitions for the model-visible runtime catalog.
# - Inputs: callers that import `catalog_image.py`.
# - Outputs: image-related `AgentToolDefinition` records.
# - Side effects: module-local registry construction only.
from __future__ import annotations

from backend.services.agent.read_image import run_read_image
from backend.services.agent.tool_args.read_image import ReadImageArgs
from backend.services.agent.tool_runtime_support.definitions import AgentToolDefinition


IMAGE_TOOLS: dict[str, AgentToolDefinition] = {
    "read_image": AgentToolDefinition(
        name="read_image",
        description=(
            "Load one or more image files that already exist inside the current user's workspace "
            "container and append them for visual inspection. Use this when an attachment note "
            "lists related image paths or when you discover relevant image files under /workspace."
        ),
        args_model=ReadImageArgs,
        handler=run_read_image,
    ),
}
