from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
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
    Approval,
    Artifact,
    AuditEvent,
    BrowserSession,
    Membership,
    Organization,
    Profile,
    RuntimeLease,
    RuntimeTask,
    RuntimeWorker,
    UsageEvent,
    User,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStepRun,
    Workspace,
)
from app.schemas import (
    ApiKeyCreate,
    ApprovalDecision,
    MemberCreate,
    OrganizationCreate,
    OrganizationOut,
    PointerInput,
    ProfileCreate,
    ProfileOut,
    SessionOut,
    TextInput,
    WorkflowDefinitionCreate,
    WorkflowRunCreate,
    WorkspaceCreate,
    WorkspaceOut,
)
from app.services.artifacts import artifact_store
from app.services.audit import record_audit
from app.services.orchestrator import runtime_orchestrator
from app.services.runtime import runtime_manager
from app.services.workflows import canonical_json, workflow_engine


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
        workflow_engine.ensure_builtin_definition(db, org.id, user.id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    seed()
    with SessionLocal() as db:
        runtime_orchestrator.recover_expired_leases(db)
        worker = runtime_orchestrator.ensure_local_worker(db)
        runtime_orchestrator.heartbeat(db, worker)
    await runtime_manager.start()
    yield
    await runtime_manager.close()


app = FastAPI(title=settings.app_name, version="0.4.0", lifespan=lifespan)
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
        "version": "0.4.0",
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
    workflow_engine.ensure_builtin_definition(db, org.id, principal.user_id)
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
        "queued_runtime_tasks": db.scalar(
            select(func.count(RuntimeTask.id)).where(
                RuntimeTask.organization_id == org_id,
                RuntimeTask.status.in_(("queued", "running")),
            )
        ) or 0,
        "active_runtime_leases": db.scalar(
            select(func.count(RuntimeLease.id)).where(
                RuntimeLease.organization_id == org_id,
                RuntimeLease.status == "active",
            )
        ) or 0,
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
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    profile = _profile_for_org(db, profile_id, principal.organization_id)

    existing_active = db.scalar(
        select(BrowserSession)
        .where(
            BrowserSession.organization_id == principal.organization_id,
            BrowserSession.profile_id == profile_id,
            BrowserSession.status.in_(("queued", "provisioning", "running")),
        )
        .order_by(BrowserSession.id.desc())
    )
    if existing_active and not idempotency_key:
        return existing_active

    existing_idempotent = runtime_orchestrator.find_idempotent_session(
        db,
        principal.organization_id,
        idempotency_key,
    )
    if existing_idempotent:
        return existing_idempotent

    org = db.get(Organization, principal.organization_id)
    if runtime_orchestrator.active_session_count(db, principal.organization_id) >= org.concurrency_limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Organization concurrency limit reached ({org.concurrency_limit})",
        )

    session, task, created = runtime_orchestrator.enqueue_start(
        db,
        profile,
        idempotency_key,
    )
    if not created:
        return session

    runtime_orchestrator.acquire_local_lease(db, session, task)

    try:
        runtime = await runtime_manager.launch(
            profile_id=profile_id,
            start_url=profile.start_url,
            locale=profile.locale,
            timezone=profile.timezone,
        )
        runtime_orchestrator.complete_start(
            db,
            session,
            task,
            current_url=runtime.page.url,
            current_title=await runtime.page.title(),
        )
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
            detail=f"session={session.id};worker={session.worker_id}",
        )
        return session
    except Exception as exc:
        runtime_orchestrator.fail_start(db, session, task, str(exc))
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
    session = db.scalar(
        select(BrowserSession)
        .where(
            BrowserSession.organization_id == principal.organization_id,
            BrowserSession.profile_id == profile_id,
            BrowserSession.status.in_(("queued", "provisioning", "running")),
        )
        .order_by(BrowserSession.id.desc())
    )
    if not session:
        profile.status = "ready"
        db.commit()
        return {"ok": True, "status": "already_stopped"}

    task = runtime_orchestrator.enqueue_stop(db, session)
    runtime_orchestrator.mark_stop_running(db, task)

    try:
        await runtime_manager.stop(profile_id)

        now = datetime.now(timezone.utc)
        started = session.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        runtime_seconds = max(0, int((now - started).total_seconds()))

        runtime_orchestrator.complete_stop(db, session, task)
        profile.status = "ready"
        db.add(
            UsageEvent(
                organization_id=principal.organization_id,
                session_id=session.id,
                metric="runtime_seconds",
                quantity=runtime_seconds,
                unit="second",
            )
        )
        db.commit()
        record_audit(
            db,
            organization_id=principal.organization_id,
            actor=principal.actor,
            action="session.stopped",
            resource_type="profile",
            resource_id=profile_id,
            detail=f"session={session.id};runtime_seconds={runtime_seconds}",
        )
        return {"ok": True, "status": "stopped"}
    except Exception as exc:
        runtime_orchestrator.fail_stop(db, task, str(exc))
        record_audit(
            db,
            organization_id=principal.organization_id,
            actor=principal.actor,
            action="session.stop_failed",
            resource_type="profile",
            resource_id=profile_id,
            detail=str(exc)[:4000],
        )
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Runtime stop failed") from exc

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




@app.post("/api/profiles/{profile_id}/capture", status_code=status.HTTP_201_CREATED)
async def capture_evidence(
    profile_id: int,
    principal: Principal = Depends(require_role("reviewer")),
    db: Session = Depends(get_db),
):
    _profile_for_org(db, profile_id, principal.organization_id)
    session = db.scalar(
        select(BrowserSession)
        .where(
            BrowserSession.organization_id == principal.organization_id,
            BrowserSession.profile_id == profile_id,
            BrowserSession.status == "running",
        )
        .order_by(BrowserSession.id.desc())
    )
    if not session:
        raise HTTPException(status.HTTP_409_CONFLICT, "Profile has no running session")

    try:
        image = await runtime_manager.screenshot(profile_id)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    stored = artifact_store.put(
        organization_id=principal.organization_id,
        profile_id=profile_id,
        session_id=session.id,
        kind="screenshot",
        content=image,
        content_type="image/jpeg",
        extension="jpg",
    )
    artifact = Artifact(
        organization_id=principal.organization_id,
        profile_id=profile_id,
        session_id=session.id,
        kind="screenshot",
        storage_key=stored.storage_key,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    record_audit(
        db,
        organization_id=principal.organization_id,
        actor=principal.actor,
        action="artifact.captured",
        resource_type="artifact",
        resource_id=artifact.id,
        detail=f"profile={profile_id};sha256={artifact.sha256}",
    )
    return {
        "id": artifact.id,
        "profile_id": artifact.profile_id,
        "session_id": artifact.session_id,
        "kind": artifact.kind,
        "content_type": artifact.content_type,
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
        "created_at": artifact.created_at,
    }


@app.get("/api/v1/artifacts")
def list_artifacts(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    artifacts = db.scalars(
        select(Artifact)
        .where(Artifact.organization_id == principal.organization_id)
        .order_by(Artifact.id.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": item.id,
            "profile_id": item.profile_id,
            "session_id": item.session_id,
            "kind": item.kind,
            "content_type": item.content_type,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
            "created_at": item.created_at,
        }
        for item in artifacts
    ]


@app.get("/api/v1/artifacts/{artifact_id}/content")
def artifact_content(
    artifact_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    artifact = db.scalar(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.organization_id == principal.organization_id,
        )
    )
    if not artifact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact not found")
    try:
        content = artifact_store.get(artifact.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_410_GONE, "Artifact content is unavailable") from exc
    return Response(
        content=content,
        media_type=artifact.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-SHA256": artifact.sha256,
        },
    )


@app.get("/api/v1/runtime/workers")
def runtime_workers(
    principal: Principal = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    workers = db.scalars(
        select(RuntimeWorker)
        .join(RuntimeLease, RuntimeLease.worker_id == RuntimeWorker.id)
        .where(RuntimeLease.organization_id == principal.organization_id)
        .distinct()
        .order_by(RuntimeWorker.worker_key)
    ).all()
    return [
        {
            "id": worker.id,
            "worker_key": worker.worker_key,
            "region": worker.region,
            "status": worker.status,
            "capacity": worker.capacity,
            "capabilities": worker.capabilities,
            "last_heartbeat_at": worker.last_heartbeat_at,
        }
        for worker in workers
    ]


@app.get("/api/v1/runtime/tasks")
def runtime_tasks(
    principal: Principal = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    tasks = db.scalars(
        select(RuntimeTask)
        .where(RuntimeTask.organization_id == principal.organization_id)
        .order_by(RuntimeTask.id.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": task.id,
            "session_id": task.session_id,
            "profile_id": task.profile_id,
            "task_type": task.task_type,
            "status": task.status,
            "attempt_count": task.attempt_count,
            "max_attempts": task.max_attempts,
            "locked_by": task.locked_by,
            "error": task.error,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
        for task in tasks
    ]


@app.get("/api/v1/runtime/leases")
def runtime_leases(
    principal: Principal = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    leases = db.scalars(
        select(RuntimeLease)
        .where(RuntimeLease.organization_id == principal.organization_id)
        .order_by(RuntimeLease.id.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": lease.id,
            "session_id": lease.session_id,
            "profile_id": lease.profile_id,
            "worker_id": lease.worker_id,
            "status": lease.status,
            "acquired_at": lease.acquired_at,
            "expires_at": lease.expires_at,
            "released_at": lease.released_at,
        }
        for lease in leases
    ]




def _workflow_run_detail(db: Session, run: WorkflowRun) -> dict:
    steps = db.scalars(
        select(WorkflowStepRun)
        .where(WorkflowStepRun.run_id == run.id)
        .order_by(WorkflowStepRun.step_index)
    ).all()
    approvals = db.scalars(
        select(Approval)
        .where(Approval.run_id == run.id)
        .order_by(Approval.id)
    ).all()
    return {
        "id": run.id,
        "definition_id": run.definition_id,
        "profile_id": run.profile_id,
        "status": run.status,
        "current_step_index": run.current_step_index,
        "input": run.input,
        "output": run.output,
        "error": run.error,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "steps": [
            {
                "id": step.id,
                "step_index": step.step_index,
                "step_key": step.step_key,
                "step_type": step.step_type,
                "status": step.status,
                "input": step.input,
                "output": step.output,
                "error": step.error,
                "started_at": step.started_at,
                "completed_at": step.completed_at,
            }
            for step in steps
        ],
        "approvals": [
            {
                "id": approval.id,
                "step_run_id": approval.step_run_id,
                "status": approval.status,
                "prompt": approval.prompt,
                "requested_by": approval.requested_by,
                "decided_by": approval.decided_by,
                "reason": approval.reason,
                "requested_at": approval.requested_at,
                "decided_at": approval.decided_at,
            }
            for approval in approvals
        ],
    }


@app.get("/api/v1/workflows/definitions")
def list_workflow_definitions(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    definitions = db.scalars(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.organization_id == principal.organization_id)
        .order_by(WorkflowDefinition.slug, WorkflowDefinition.version.desc())
    ).all()
    return [
        {
            "id": definition.id,
            "name": definition.name,
            "slug": definition.slug,
            "version": definition.version,
            "is_active": definition.is_active,
            "definition": definition.definition,
            "created_at": definition.created_at,
        }
        for definition in definitions
    ]


@app.post("/api/v1/workflows/definitions", status_code=status.HTTP_201_CREATED)
def create_workflow_definition(
    payload: WorkflowDefinitionCreate,
    principal: Principal = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    normalized_steps = workflow_engine.validate_definition(payload.definition)
    definition_payload = {"steps": normalized_steps}
    definition = WorkflowDefinition(
        organization_id=principal.organization_id,
        name=payload.name,
        slug=payload.slug,
        version=payload.version,
        is_active=True,
        definition=canonical_json(definition_payload),
        created_by_user_id=principal.user_id,
    )
    db.add(definition)
    _safe_commit(db, "Workflow slug/version already exists")
    db.refresh(definition)
    record_audit(
        db,
        organization_id=principal.organization_id,
        actor=principal.actor,
        action="workflow.definition_created",
        resource_type="workflow_definition",
        resource_id=definition.id,
        detail=f"{definition.slug}:v{definition.version}",
    )
    return {
        "id": definition.id,
        "name": definition.name,
        "slug": definition.slug,
        "version": definition.version,
        "is_active": definition.is_active,
        "definition": definition.definition,
    }


@app.post("/api/v1/workflows/definitions/{definition_id}/runs", status_code=status.HTTP_201_CREATED)
def start_workflow_run(
    definition_id: int,
    payload: WorkflowRunCreate,
    principal: Principal = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    definition = db.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.id == definition_id,
            WorkflowDefinition.organization_id == principal.organization_id,
        )
    )
    if not definition:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow definition not found")

    run = workflow_engine.start_run(
        db,
        definition=definition,
        profile_id=payload.profile_id,
        input_payload=payload.input,
        user_id=principal.user_id,
        actor=principal.actor,
    )
    record_audit(
        db,
        organization_id=principal.organization_id,
        actor=principal.actor,
        action="workflow.run_started",
        resource_type="workflow_run",
        resource_id=run.id,
        detail=f"definition={definition.id};status={run.status}",
    )
    return _workflow_run_detail(db, run)


@app.get("/api/v1/workflows/runs")
def list_workflow_runs(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    runs = db.scalars(
        select(WorkflowRun)
        .where(WorkflowRun.organization_id == principal.organization_id)
        .order_by(WorkflowRun.id.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": run.id,
            "definition_id": run.definition_id,
            "profile_id": run.profile_id,
            "status": run.status,
            "current_step_index": run.current_step_index,
            "error": run.error,
            "created_at": run.created_at,
            "completed_at": run.completed_at,
        }
        for run in runs
    ]


@app.get("/api/v1/workflows/runs/{run_id}")
def get_workflow_run(
    run_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    run = db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.organization_id == principal.organization_id,
        )
    )
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow run not found")
    return _workflow_run_detail(db, run)


@app.get("/api/v1/approvals")
def list_approvals(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    approvals = db.scalars(
        select(Approval)
        .where(Approval.organization_id == principal.organization_id)
        .order_by(Approval.id.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": approval.id,
            "run_id": approval.run_id,
            "step_run_id": approval.step_run_id,
            "status": approval.status,
            "prompt": approval.prompt,
            "requested_by": approval.requested_by,
            "decided_by": approval.decided_by,
            "reason": approval.reason,
            "requested_at": approval.requested_at,
            "decided_at": approval.decided_at,
        }
        for approval in approvals
    ]


@app.post("/api/v1/approvals/{approval_id}/decision")
def decide_approval(
    approval_id: int,
    payload: ApprovalDecision,
    principal: Principal = Depends(require_role("reviewer")),
    db: Session = Depends(get_db),
):
    approval = db.scalar(
        select(Approval).where(
            Approval.id == approval_id,
            Approval.organization_id == principal.organization_id,
        )
    )
    if not approval:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval not found")

    run = workflow_engine.decide(
        db,
        approval=approval,
        decision=payload.decision,
        reason=payload.reason,
        actor=principal.actor,
    )
    record_audit(
        db,
        organization_id=principal.organization_id,
        actor=principal.actor,
        action=f"approval.{payload.decision}",
        resource_type="approval",
        resource_id=approval.id,
        detail=f"workflow_run={run.id};reason={payload.reason or ''}",
    )
    return _workflow_run_detail(db, run)


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
