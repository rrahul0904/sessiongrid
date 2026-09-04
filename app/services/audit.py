from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_audit(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str | int,
    detail: str | None = None,
    actor: str = "local-operator",
) -> AuditEvent:
    event = AuditEvent(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        detail=detail,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
