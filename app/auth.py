from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import ApiKey, Membership, Organization, User


ROLE_RANK = {
    "viewer": 10,
    "reviewer": 20,
    "operator": 30,
    "manager": 40,
    "admin": 50,
    "owner": 60,
}


@dataclass(frozen=True)
class Principal:
    user_id: int
    organization_id: int
    role: str
    email: str

    @property
    def actor(self) -> str:
        return self.email


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return "sg_" + secrets.token_urlsafe(32)


def _membership_for(db: Session, user_id: int, organization_id: int) -> Membership | None:
    return db.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
        )
    )


def _principal_from_api_key(db: Session, raw_key: str, requested_org: int | None) -> Principal:
    digest = hash_api_key(raw_key)
    key = db.scalar(select(ApiKey).where(ApiKey.secret_hash == digest))
    now = datetime.now(timezone.utc)

    if not key or key.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    if key.expires_at is not None and key.expires_at <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key expired")
    if requested_org is not None and requested_org != key.organization_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API key is scoped to another organization")

    user = db.get(User, key.user_id)
    membership = _membership_for(db, key.user_id, key.organization_id)
    if not user or not user.is_active or not membership:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key principal is inactive")

    key.last_used_at = now
    db.commit()
    return Principal(
        user_id=user.id,
        organization_id=key.organization_id,
        role=membership.role,
        email=user.email,
    )


def _dev_principal(db: Session, requested_org: int | None) -> Principal:
    user = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email))
    if not user:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Bootstrap user is unavailable")

    if requested_org is None:
        org = db.scalar(select(Organization).where(Organization.slug == settings.default_organization_slug))
        if not org:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Bootstrap organization is unavailable")
        organization_id = org.id
    else:
        organization_id = requested_org

    membership = _membership_for(db, user.id, organization_id)
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User is not a member of this organization")

    return Principal(
        user_id=user.id,
        organization_id=organization_id,
        role=membership.role,
        email=user.email,
    )


def get_principal(
    db: Session = Depends(get_db),
    x_sessiongrid_api_key: str | None = Header(default=None, alias="X-SessionGrid-API-Key"),
    x_sessiongrid_organization_id: int | None = Header(default=None, alias="X-SessionGrid-Organization-ID"),
) -> Principal:
    if x_sessiongrid_api_key:
        return _principal_from_api_key(db, x_sessiongrid_api_key, x_sessiongrid_organization_id)

    if settings.auth_required:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required. Supply X-SessionGrid-API-Key.",
        )

    return _dev_principal(db, x_sessiongrid_organization_id)


def require_role(minimum_role: str):
    if minimum_role not in ROLE_RANK:
        raise ValueError(f"Unknown role: {minimum_role}")

    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if ROLE_RANK.get(principal.role, 0) < ROLE_RANK[minimum_role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return principal

    return dependency
