# CALLING SPEC:
# - Purpose: implement focused service logic for `attachments`.
# - Inputs: callers that import `backend/services/agent/attachments.py` and pass module-defined arguments or framework events.
# - Outputs: helpers that bind canonical `user_files` rows to agent message attachment rows.
# - Side effects: DB row creation for message attachments.
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models_agent import AgentMessageAttachment
from backend.models_files import UserFile


def create_message_attachment(
    db: Session,
    *,
    message_id: str,
    user_file: UserFile,
) -> AgentMessageAttachment:
    attachment = AgentMessageAttachment(
        message_id=message_id,
        user_file_id=user_file.id,
    )
    db.add(attachment)
    db.flush()
    return attachment
