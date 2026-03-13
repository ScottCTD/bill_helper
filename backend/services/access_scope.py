# CALLING SPEC:
# - Purpose: implement focused service logic for `access_scope`.
# - Inputs: callers that import `backend/services/access_scope.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `access_scope`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from sqlalchemy import Select, false, select, true
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal, is_admin_principal
from backend.models_agent import (
    AgentChangeItem,
    AgentMessage,
    AgentMessageAttachment,
    AgentRun,
    AgentThread,
    AgentToolCall,
)
from backend.models_finance import Account, Entity, Entry, EntryGroup, FilterGroup, Tag, Taxonomy, User
from backend.services.crud_policy import PolicyViolation


def owner_user_condition(
    owner_user_id_column,
    *,
    principal_user_id: str | None,
    is_admin: bool,
):
    if is_admin:
        return true()
    if principal_user_id is None:
        return false()
    return owner_user_id_column == principal_user_id


def owner_user_filter(owner_user_id_column, principal: RequestPrincipal):
    return owner_user_condition(
        owner_user_id_column,
        principal_user_id=principal.user_id,
        is_admin=is_admin_principal(principal),
    )


def account_owner_filter(principal: RequestPrincipal):
    return owner_user_filter(Account.owner_user_id, principal)


def entry_owner_filter(principal: RequestPrincipal):
    return owner_user_filter(Entry.owner_user_id, principal)


def group_owner_filter(principal: RequestPrincipal):
    return owner_user_filter(EntryGroup.owner_user_id, principal)


def filter_group_owner_filter(principal: RequestPrincipal):
    return owner_user_filter(FilterGroup.owner_user_id, principal)


def entity_owner_filter(principal: RequestPrincipal):
    return owner_user_filter(Entity.owner_user_id, principal)


def tag_owner_filter(principal: RequestPrincipal):
    return owner_user_filter(Tag.owner_user_id, principal)


def taxonomy_owner_filter(principal: RequestPrincipal):
    return owner_user_filter(Taxonomy.owner_user_id, principal)


def agent_thread_owner_filter(principal: RequestPrincipal):
    return owner_user_filter(AgentThread.owner_user_id, principal)


def get_account_for_principal_or_404(
    db: Session,
    *,
    account_id: str,
    principal: RequestPrincipal,
) -> Account:
    return load_account_for_principal(db, account_id=account_id, principal=principal)


def load_account_for_principal(
    db: Session,
    *,
    account_id: str,
    principal: RequestPrincipal,
) -> Account:
    account = db.scalar(
        select(Account).where(
            Account.id == account_id,
            account_owner_filter(principal),
        )
    )
    if account is None:
        raise PolicyViolation.not_found("Account not found")
    return account


def load_entity_for_principal(
    db: Session,
    *,
    entity_id: str,
    principal: RequestPrincipal,
) -> Entity:
    entity = db.scalar(
        select(Entity).where(
            Entity.id == entity_id,
            entity_owner_filter(principal),
        )
    )
    if entity is None:
        raise PolicyViolation.not_found("Entity not found")
    return entity


def load_tag_for_principal(
    db: Session,
    *,
    tag_id: int,
    principal: RequestPrincipal,
) -> Tag:
    tag = db.scalar(
        select(Tag).where(
            Tag.id == tag_id,
            tag_owner_filter(principal),
        )
    )
    if tag is None:
        raise PolicyViolation.not_found("Tag not found")
    return tag


def get_entry_for_principal_or_404(
    db: Session,
    *,
    entry_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[Entry]] | None = None,
) -> Entry:
    return load_entry_for_principal(
        db,
        entry_id=entry_id,
        principal=principal,
        stmt=stmt,
    )


def load_entry_for_principal(
    db: Session,
    *,
    entry_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[Entry]] | None = None,
) -> Entry:
    query = stmt if stmt is not None else select(Entry)
    entry = db.scalar(
        query.where(
            Entry.id == entry_id,
            Entry.is_deleted.is_(False),
            entry_owner_filter(principal),
        )
    )
    if entry is None:
        raise PolicyViolation.not_found("Entry not found")
    return entry


def get_user_for_principal_or_404(
    db: Session,
    *,
    user_id: str,
    principal: RequestPrincipal,
) -> User:
    return load_user_for_principal(db, user_id=user_id, principal=principal)


def load_user_for_principal(
    db: Session,
    *,
    user_id: str,
    principal: RequestPrincipal,
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise PolicyViolation.not_found("User not found")
    if not is_admin_principal(principal) and user.id != principal.user_id:
        raise PolicyViolation.not_found("User not found")
    return user


def get_group_for_principal_or_404(
    db: Session,
    *,
    group_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[EntryGroup]] | None = None,
) -> EntryGroup:
    return load_group_for_principal(
        db,
        group_id=group_id,
        principal=principal,
        stmt=stmt,
    )


def load_group_for_principal(
    db: Session,
    *,
    group_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[EntryGroup]] | None = None,
) -> EntryGroup:
    query = stmt if stmt is not None else select(EntryGroup)
    group = db.scalar(
        query.where(
            EntryGroup.id == group_id,
            group_owner_filter(principal),
        )
    )
    if group is None:
        raise PolicyViolation.not_found("Group not found")
    return group


def load_filter_group_for_principal(
    db: Session,
    *,
    filter_group_id: str,
    principal: RequestPrincipal,
) -> FilterGroup:
    filter_group = db.scalar(
        select(FilterGroup).where(
            FilterGroup.id == filter_group_id,
            filter_group_owner_filter(principal),
        )
    )
    if filter_group is None:
        raise PolicyViolation.not_found("Filter group not found")
    return filter_group


def load_taxonomy_for_principal(
    db: Session,
    *,
    taxonomy_id: str,
    principal: RequestPrincipal,
) -> Taxonomy:
    taxonomy = db.scalar(
        select(Taxonomy).where(
            Taxonomy.id == taxonomy_id,
            taxonomy_owner_filter(principal),
        )
    )
    if taxonomy is None:
        raise PolicyViolation.not_found("Taxonomy not found")
    return taxonomy


def load_agent_thread_for_principal(
    db: Session,
    *,
    thread_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[AgentThread]] | None = None,
) -> AgentThread:
    query = stmt if stmt is not None else select(AgentThread)
    thread = db.scalar(
        query.where(
            AgentThread.id == thread_id,
            agent_thread_owner_filter(principal),
        )
    )
    if thread is None:
        raise PolicyViolation.not_found("Thread not found")
    return thread


def load_agent_run_for_principal(
    db: Session,
    *,
    run_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[AgentRun]] | None = None,
) -> AgentRun:
    query = stmt if stmt is not None else select(AgentRun)
    run = db.scalar(
        query.join(AgentThread, AgentThread.id == AgentRun.thread_id).where(
            AgentRun.id == run_id,
            agent_thread_owner_filter(principal),
        )
    )
    if run is None:
        raise PolicyViolation.not_found("Run not found")
    return run


def load_change_item_for_principal(
    db: Session,
    *,
    item_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[AgentChangeItem]] | None = None,
) -> AgentChangeItem:
    query = stmt if stmt is not None else select(AgentChangeItem)
    item = db.scalar(
        query.join(AgentRun, AgentRun.id == AgentChangeItem.run_id)
        .join(AgentThread, AgentThread.id == AgentRun.thread_id)
        .where(
            AgentChangeItem.id == item_id,
            agent_thread_owner_filter(principal),
        )
    )
    if item is None:
        raise PolicyViolation.not_found("Change item not found")
    return item


def load_attachment_for_principal(
    db: Session,
    *,
    attachment_id: str,
    principal: RequestPrincipal,
) -> AgentMessageAttachment:
    attachment = db.scalar(
        select(AgentMessageAttachment)
        .join(AgentMessage, AgentMessage.id == AgentMessageAttachment.message_id)
        .join(AgentThread, AgentThread.id == AgentMessage.thread_id)
        .where(
            AgentMessageAttachment.id == attachment_id,
            agent_thread_owner_filter(principal),
        )
    )
    if attachment is None:
        raise PolicyViolation.not_found("Attachment not found")
    return attachment


def load_tool_call_for_principal(
    db: Session,
    *,
    tool_call_id: str,
    principal: RequestPrincipal,
) -> AgentToolCall:
    tool_call = db.scalar(
        select(AgentToolCall)
        .join(AgentRun, AgentRun.id == AgentToolCall.run_id)
        .join(AgentThread, AgentThread.id == AgentRun.thread_id)
        .where(
            AgentToolCall.id == tool_call_id,
            agent_thread_owner_filter(principal),
        )
    )
    if tool_call is None:
        raise PolicyViolation.not_found("Tool call not found")
    return tool_call


def ensure_principal_can_assign_user(
    principal: RequestPrincipal,
    *,
    user_id: str,
) -> None:
    if is_admin_principal(principal) or user_id == principal.user_id:
        return
    raise PolicyViolation.forbidden(
        "Cannot assign resources to a different user.",
    )
