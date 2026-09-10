from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Principal, generate_api_key, get_principal, hash_api_key, require_role
from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import (
    ApiKey,
    AuditEvent,
    BrowserSession,
    Membership,
    Organization,
    Profile,
    UsageEvent,
    User,
    Workspace,
)
from app.schemas import (
    ApiKeyCreate,
    MemberCreate,
    OrganizationCreate,
    OrganizationOut,
    PointerInput,
    ProfileCreate,
    ProfileOut,
    SessionOut,
    TextInput,
    WorkspaceCreate,
    WorkspaceOut,
)
from app.services.audit import record_audit
from app.services.runtime import runtime_manager


def _safe_commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, conflict_message) from exc


def seed() -> None:
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == settings.default_organization_slug))
        if not org:
            org = Organization(
                name=settings.default_organization_name,
                slug=settings.default_organization_slug,
                plan="development",
                concurrency_limit=5,
            )
            db.add(org)
            db.flush()

        user = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email))
        if not user:
            user = User(
                email=settings.bootstrap_admin_email,
                display_name=settings.bootstrap_admin_name,
                is_active=True,
            )
            db.add(user)
            db.flush()

        membership = db.scalar(
            select(Membership).where(
                Membership.organization_id == org.id,
                Membership.user_id == user.id,
            )
        )
        if not membership:
            db.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))

        workspace = db.scalar(
            select(Workspace).where(
                Workspace.organization_id == org.id,
                Workspace.slug == "default",
            )
        )
        if not workspace:
            workspace = Workspace(
                organization_id=org.id,
                name=settings.default_workspace_name,
                slug="default",
            )
            db.add(workspace)
            db.flush()

        if settings.bootstrap_api_key:
            digest = hash_api_key(settings.bootstrap_api_key)
            key = db.scalar(select(ApiKey).where(ApiKey.secret_hash == digest))
            if not key:
                db.add(
                    ApiKey(
                        organization_id=org.id,
                        user_id=user.id,
                        name="bootstrap",
                        key_prefix=settings.bootstrap_api_key[:12],
                        secret_hash=digest,
                    )
                )

        count = db.scalar(
            select(func.count(Profile.id)).where(Profile.organization_id == org.id)
        ) or 0
        if not count:
            db.add_all(
                [
                    Profile(
                        organization_id=org.id,
                        workspace_id=workspace.id,
                        name="Boston Community",
                        platform="TikTok Web",
                        owner="Social Team",
                        start_url="https://www.tiktok.com/",
                    ),
                    Profile(
                        organization_id=org.id,
                        workspace_id=workspace.id,
                        name="Support Desk",
                        platform="Reddit",
                        owner="Support Team",
                        start_url="https://www.reddit.com/",
                    ),
                    Profile(
                        organization_id=org.id,
                        workspace_id=workspace.id,
                        name="Corporate News",
                        platform="X",
                        owner="Comms Team",
                        start_url="https://x.com/",
                    ),
                    Profile(
                        organization_id=org.id,
                        workspace_id=workspace.id,
                        name="Localization QA",
                        platform="Web QA",
                        owner="QA Team",
                        start_url="https://example.com/",
                    ),
                ]
            )

        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    seed()
    await runtime_manager.start()
    yield
    await runtime_manager.close()


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def _profile_for_org(db: Session, profile_id: int, organization_id: int) -> Profile:
    profile = db.scalar(
        select(Profile).where(
            Profile.id == profile_id,
            Profile.organization_id == organization_id,
        )
    )
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return profile


@app.get("/", include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": settings.app_name},
    )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.env,
        "version": "0.2.0",
        "auth_required": settings.auth_required,
    }


@app.get("/api/v1/me")
def me(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    org = db.get(Organization, principal.organization_id)
    user = db.get(User, principal.user_id)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
        },
        "organization": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "plan": org.plan,
            "concurrency_limit": org.concurrency_limit,
        },
        "role": principal.role,
    }


@app.get("/api/v1/organizations", response_model=list[OrganizationOut])
def list_organizations(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(Membership.user_id == principal.user_id)
            .order_by(Organization.name)
        ).all()
    )


@app.post("/api/v1/organizations", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    org = Organization(name=payload.name, slug=payload.slug, plan="development", concurrency_limit=5)
    db.add(org)
    try:
        db.flush()
        db.add(Membership(organization_id=org.id, user_id=principal.user_id, role="owner"))
        db.add(Workspace(organization_id=org.id, name="Default Workspace", slug="default"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Organization slug already exists") from exc

    db.refresh(org)
    record_audit(
        db,
        organization_id=org.id,
        actor=principal.actor,
        action="organization.created",
        resource_type="organization",
        resource_id=org.id,
        detail=org.name,
    )
    return org


@app.get("/api/v1/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(Workspace)
            .where(Workspace.organization_id == principal.organization_id)
            .order_by(Workspace.name)
        ).all()
    )


@app.post("/api/v1/workspaces", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    principal: Principal = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    workspace = Workspace(
        organization_id=principal.organization_id,
        name=payload.name,
        slug=payload.slug,
    )
    db.add(workspace)
    _safe_commit(db, "Workspace slug already exists in this organization")
    db.refresh(workspace)
    record_audit(
        db,
        organization_id=principal.organization_id,
        actor=principal.actor,
        action="workspace.created",
        resource_type="workspace",
        resource_id=workspace.id,
        detail=workspace.name,
    )
    return workspace


@app.get("/api/v1/members")
def list_members(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == principal.organization_id)
        .order_by(User.email)
    ).all()
    return [
        {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": membership.role,
            "active": user.is_active,
        }
        for membership, user in rows
    ]


@app.post("/api/v1/members", status_code=status.HTTP_201_CREATED)
def add_member(
    payload: MemberCreate,
    principal: Principal = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email, display_name=payload.display_name, is_active=True)
        db.add(user)
        db.flush()

    existing = db.scalar(
        select(Membership).where(
            Membership.organization_id == principal.organization_id,
            Membership.user_id == user.id,
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member")

    membership = Membership(
        organization_id=principal.organization_id,
        user_id=user.id,
        role=payload.role,
    )
    db.add(membership)
    db.commit()
    record_audit(
        db,
        organization_id=principal.organization_id,
        actor=principal.actor,
        action="member.added",
        resource_type="user",
        resource_id=user.id,
        detail=f"{user.email}:{payload.role}",
    )
    return {
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": membership.role,
    }


@app.post("/api/v1/api-keys", status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    principal: Principal = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    raw = generate_api_key()
    key = ApiKey(
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        name=payload.name,
        key_prefix=raw[:12],
        secret_hash=hash_api_key(raw),
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    record_audit(
        db,
        organization_id=principal.organization_id,
        actor=principal.actor,
        action="api_key.created",
        resource_type="api_key",
        resource_id=key.id,
        detail=key.name,
    )
    return {
        "id": key.id,
        "name": key.name,
        "key_prefix": key.key_prefix,
        "api_key": raw,
        "warning": "This secret is returned once. Store it securely.",
    }


@app.delete("/api/v1/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    key = db.scalar(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.organization_id == principal.organization_id,
        )
    )
    if not key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    if key.user_id != principal.user_id and principal.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot revoke another user's API key")
    key.revoked_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        organization_id=principal.organization_id,
        actor=principal.actor,
        action="api_key.revoked",
        resource_type="api_key",
        resource_id=key.id,
        detail=key.name,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/overview")
def overview(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    org_id = principal.organization_id
    profiles = db.scalar(
        select(func.count(Profile.id)).where(Profile.organization_id == org_id)
    ) or 0
    active = db.scalar(
        select(func.count(BrowserSession.id)).where(
            BrowserSession.organization_id == org_id,
            BrowserSession.status == "running",
        )
    ) or 0
    events = db.scalar(
        select(func.count(AuditEvent.id)).where(AuditEvent.organization_id == org_id)
    ) or 0
    screenshots = db.scalar(
        select(func.coalesce(func.sum(BrowserSession.screenshots), 0)).where(
            BrowserSession.organization_id == org_id
        )
    ) or 0
    org = db.get(Organization, org_id)
    return {
        "profiles": profiles,
        "active_sessions": active,
        "audit_events": events,
        "screenshots": screenshots,
        "runtime_mode": "local-playwright",
        "concurrency_limit": org.concurrency_limit,
        "organization_id": org_id,
    }


@app.get("/api/profiles", response_model=list[ProfileOut])
def list_profiles(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(Profile)
            .where(Profile.organization_id == principal.organization_id)
            .order_by(Profile.id)
        ).all()
    )


@app.post("/api/profiles", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ProfileCreate,
    principal: Principal = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    workspace_id = payload.workspace_id
    if workspace_id is None:
        default_workspace = db.scalar(
            select(Workspace).where(
                Workspace.organization_id == principal.organization_id,
                Workspace.slug == "default",
            )
        )
        workspace_id = default_workspace.id if default_workspace else None
    else:
        workspace = db.scalar(
            select(Workspace).where(
                Workspace.id == workspace_id,
                Workspace.organization_id == principal.organization_id,
            )
        )
        if not workspace:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Workspace does not belong to this organization")

    profile = Profile(
        organization_id=principal.organization_id,
        workspace_id=workspace_id,
        name=payload.name,
        platform=payload.platform,
        owner=payload.owner,
        locale=payload.locale,
        timezone=payload.timezone,
        start_url=str(payload.start_url),
        network_label=payload.network_label,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    record_audit(
        db,
        organization_id=principal.organization_id,
        actor=principal.actor,
        action="profile.created",
        resource_type="profile",
        resource_id=profile.id,
        detail=profile.name,
    )
    return profile


@app.get("/api/sessions", response_model=list[SessionOut])
def list_sessions(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(BrowserSession)
            .where(BrowserSession.organization_id == principal.organization_id)
            .order_by(BrowserSession.id.desc())
            .limit(100)
        ).all()
    )


@app.post("/api/profiles/{profile_id}/start", response_model=SessionOut)
async def start_session(
    profile_id: int,
    principal: Principal = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    profile = _profile_for_org(db, profile_id, principal.organization_id)

    running = db.scalar(
        select(BrowserSession).where(
            BrowserSession.organization_id == principal.organization_id,
            BrowserSession.profile_id == profile_id,
            BrowserSession.status == "running",
        )
    )
    if running:
        return running

    org = db.get(Organization, principal.organization_id)
    active_count = db.scalar(
        select(func.count(BrowserSession.id)).where(
            BrowserSession.organization_id == principal.organization_id,
            BrowserSession.status == "running",
        )
    ) or 0
    if active_count >= org.concurrency_limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Organization concurrency limit reached ({org.concurrency_limit})",
        )

    session = BrowserSession(
        organization_id=principal.organization_id,
        profile_id=profile_id,
        status="starting",
        runtime_type="browser",
        worker_id="local",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    try:
        runtime = await runtime_manager.launch(
            profile_id=profile_id,
            start_url=profile.start_url,
            locale=profile.locale,
            timezone=profile.timezone,
        )
        session.status = "running"
        session.current_url = runtime.page.url
        session.current_title = await runtime.page.title()
        profile.status = "online"
        db.add(
            UsageEvent(
                organization_id=principal.organization_id,
                session_id=session.id,
                metric="session_start",
                quantity=1,
                unit="event",
            )
        )
        db.commit()
        db.refresh(session)
        record_audit(
            db,
            organization_id=principal.organization_id,
            actor=principal.actor,
            action="session.started",
            resource_type="profile",
            resource_id=profile_id,
        )
        return session
    except Exception as exc:
        session.status = "error"
        session.error = str(exc)[:4000]
        profile.status = "error"
        db.commit()
        db.refresh(session)
        record_audit(
            db,
            organization_id=principal.organization_id,
            actor=principal.actor,
            action="session.start_failed",
            resource_type="profile",
            resource_id=profile_id,
            detail=session.error,
        )
        return session


@app.post("/api/profiles/{profile_id}/stop")
async def stop_session(
    profile_id: int,
    principal: Principal = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    profile = _profile_for_org(db, profile_id, principal.organization_id)
    await runtime_manager.stop(profile_id)

    session = db.scalar(
        select(BrowserSession)
        .where(
            BrowserSession.organization_id == principal.organization_id,
            BrowserSession.profile_id == profile_id,
            BrowserSession.status == "running",
        )
        .order_by(BrowserSession.id.desc())
    )
    if session:
        now = datetime.now(timezone.utc)
        started = session.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        runtime_seconds = max(0, int((now - started).total_seconds()))
        session.status = "stopped"
        session.stopped_at = now
        db.add(
            UsageEvent(
                organization_id=principal.organization_id,
                session_id=session.id,
                metric="runtime_seconds",
                quantity=runtime_seconds,
                unit="second",
            )
        )

    profile.status = "ready"
    db.commit()
    record_audit(
        db,
        organization_id=principal.organization_id,
        actor=principal.actor,
        action="session.stopped",
        resource_type="profile",
        resource_id=profile_id,
    )
    return {"ok": True}


@app.get("/api/profiles/{profile_id}/frame")
async def frame(
    profile_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    _profile_for_org(db, profile_id, principal.organization_id)
    try:
        image = await runtime_manager.screenshot(profile_id)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    session = db.scalar(
        select(BrowserSession)
        .where(
            BrowserSession.organization_id == principal.organization_id,
            BrowserSession.profile_id == profile_id,
            BrowserSession.status == "running",
        )
        .order_by(BrowserSession.id.desc())
    )
    if session:
        session.screenshots += 1
        url, title = await runtime_manager.state(profile_id)
        session.current_url = url
        session.current_title = title
        db.commit()

    return Response(
        content=image,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/profiles/{profile_id}/input/pointer")
async def pointer(
    profile_id: int,
    payload: PointerInput,
    principal: Principal = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    _profile_for_org(db, profile_id, principal.organization_id)
    try:
        await runtime_manager.pointer(profile_id, payload.x, payload.y)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return {"ok": True}


@app.post("/api/profiles/{profile_id}/input/text")
async def text_input(
    profile_id: int,
    payload: TextInput,
    principal: Principal = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    _profile_for_org(db, profile_id, principal.organization_id)
    try:
        await runtime_manager.text(profile_id, payload.text)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return {"ok": True}


@app.get("/api/v1/usage")
def usage(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(UsageEvent.metric, UsageEvent.unit, func.sum(UsageEvent.quantity))
        .where(UsageEvent.organization_id == principal.organization_id)
        .group_by(UsageEvent.metric, UsageEvent.unit)
        .order_by(UsageEvent.metric)
    ).all()
    return [
        {"metric": metric, "unit": unit, "quantity": int(quantity or 0)}
        for metric, unit, quantity in rows
    ]


@app.get("/api/audit")
def audit(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.organization_id == principal.organization_id)
        .order_by(AuditEvent.id.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": event.id,
            "actor": event.actor,
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "detail": event.detail,
            "created_at": event.created_at,
        }
        for event in events
    ]
