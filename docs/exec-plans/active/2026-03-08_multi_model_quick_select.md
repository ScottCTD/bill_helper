Goal: In the agent chat interface, allow the user to quickly select a model from a list of available models.

Available models are defined through the settings page. The server also maintains a list of default available models.

Available model edit:
1. The setting page agent runtime setting should have a field for viewing and editing the available models.
2. The simplest one could be a text input field with \n separated list of models.

In the agent chat interface, to the left of the "Send" button, there should be a dropdown that allows the user to select a model.

The user is allowed to change model mid-conversation. New request would simply send all history so far to the new model.

The setting page should also define a default model (server default is: bedrock/us.anthropic.claude-sonnet-4-6)

The model select dropdown should be ordered the same as the available models list in the settings page.
