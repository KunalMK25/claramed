"""Write AuditEvent rows. Never put patient references in `metadata`."""
from sqlalchemy.orm import Session

from backend.models.audit import AuditEvent


def record_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: str,
    client_id=None,
    client_name: str | None = None,
    request_id: str | None = None,
    error: str | None = None,
    metadata: dict | None = None,
    commit: bool = True,
) -> None:
    """
    Add one audit event. `outcome` is success, failure or denied. Commits by default; pass commit=False
    when the caller commits right afterwards, so the event lands atomically with the state change.
    """
    db.add(AuditEvent(
        request_id=request_id or "system",
        requesting_client_id=client_id,
        requesting_client_name=client_name,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        error_message=error[:500] if error else None,
        event_metadata=metadata,
    ))
    db.commit() if commit else db.flush()
