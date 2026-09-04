from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import AuditEvent, BrowserSession, Profile
from app.schemas import PointerInput, ProfileCreate, ProfileOut, SessionOut, TextInput
from app.services.audit import record_audit
from app.services.runtime import runtime_manager


def seed() -> None:
    with SessionLocal() as db:
        count = db.scalar(select(func.count(Profile.id))) or 0
        if count:
            return
        db.add_all(
            [
                Profile(name="Boston Community", platform="TikTok Web", owner="Social Team", start_url="https://www.tiktok.com/"),
                Profile(name="Support Desk", platform="Reddit", owner="Support Team", start_url="https://www.reddit.com/"),
                Profile(name="Corporate News", platform="X", owner="Comms Team", start_url="https://x.com/"),
                Profile(name="Localization QA", platform="Web QA", owner="QA Team", start_url="https://example.com/"),
            ]
        )
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed()
    await runtime_manager.start()
    yield
    await runtime_manager.close()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.app_name})


@app.get("/api/health")
def health():
    return {"status": "ok", "service": settings.app_name, "environment": settings.env}


@app.get("/api/overview")
def overview(db: Session = Depends(get_db)):
    profiles = db.scalar(select(func.count(Profile.id))) or 0
    active = db.scalar(
        select(func.count(BrowserSession.id)).where(BrowserSession.status == "running")
    ) or 0
    events = db.scalar(select(func.count(AuditEvent.id))) or 0
    screenshots = db.scalar(select(func.coalesce(func.sum(BrowserSession.screenshots), 0))) or 0
    return {
        "profiles": profiles,
        "active_sessions": active,
        "audit_events": events,
        "screenshots": screenshots,
        "runtime_mode": "local-playwright",
    }


@app.get("/api/profiles", response_model=list[ProfileOut])
def list_profiles(db: Session = Depends(get_db)):
    return list(db.scalars(select(Profile).order_by(Profile.id)).all())


@app.post("/api/profiles", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)):
    profile = Profile(
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
    record_audit(db, action="profile.created", resource_type="profile", resource_id=profile.id, detail=profile.name)
    return profile


@app.get("/api/sessions", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db)):
    return list(db.scalars(select(BrowserSession).order_by(BrowserSession.id.desc()).limit(100)).all())


@app.post("/api/profiles/{profile_id}/start", response_model=SessionOut)
async def start_session(profile_id: int, db: Session = Depends(get_db)):
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")

    running = db.scalar(
        select(BrowserSession).where(
            BrowserSession.profile_id == profile_id,
            BrowserSession.status == "running",
        )
    )
    if running:
        return running

    session = BrowserSession(profile_id=profile_id, status="starting")
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
        db.commit()
        db.refresh(session)
        record_audit(db, action="session.started", resource_type="profile", resource_id=profile_id)
        return session
    except Exception as exc:
        session.status = "error"
        session.error = str(exc)[:4000]
        profile.status = "error"
        db.commit()
        db.refresh(session)
        record_audit(db, action="session.start_failed", resource_type="profile", resource_id=profile_id, detail=session.error)
        return session


@app.post("/api/profiles/{profile_id}/stop")
async def stop_session(profile_id: int, db: Session = Depends(get_db)):
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")

    await runtime_manager.stop(profile_id)
    session = db.scalar(
        select(BrowserSession)
        .where(BrowserSession.profile_id == profile_id, BrowserSession.status == "running")
        .order_by(BrowserSession.id.desc())
    )
    if session:
        session.status = "stopped"
        session.stopped_at = datetime.now(timezone.utc)
    profile.status = "ready"
    db.commit()
    record_audit(db, action="session.stopped", resource_type="profile", resource_id=profile_id)
    return {"ok": True}


@app.get("/api/profiles/{profile_id}/frame")
async def frame(profile_id: int, db: Session = Depends(get_db)):
    try:
        image = await runtime_manager.screenshot(profile_id)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc

    session = db.scalar(
        select(BrowserSession)
        .where(BrowserSession.profile_id == profile_id, BrowserSession.status == "running")
        .order_by(BrowserSession.id.desc())
    )
    if session:
        session.screenshots += 1
        url, title = await runtime_manager.state(profile_id)
        session.current_url = url
        session.current_title = title
        db.commit()
    return Response(content=image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/profiles/{profile_id}/input/pointer")
async def pointer(profile_id: int, payload: PointerInput):
    try:
        await runtime_manager.pointer(profile_id, payload.x, payload.y)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True}


@app.post("/api/profiles/{profile_id}/input/text")
async def text_input(profile_id: int, payload: TextInput):
    try:
        await runtime_manager.text(profile_id, payload.text)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True}


@app.get("/api/audit")
def audit(db: Session = Depends(get_db)):
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(100)).all()
    return [
        {
            "id": e.id,
            "actor": e.actor,
            "action": e.action,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "detail": e.detail,
            "created_at": e.created_at,
        }
        for e in events
    ]
