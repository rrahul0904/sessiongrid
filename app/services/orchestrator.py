from datetime import datetime, timedelta, timezone
import json

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BrowserSession, Profile, RuntimeLease, RuntimeTask, RuntimeWorker


ACTIVE_SESSION_STATES = ("queued", "provisioning", "running")


class RuntimeOrchestrator:
    """Durable control-plane state for runtime work.

    Execution is still local in this phase, but session intent, worker
    assignment and leases are persisted so a remote worker pool can replace
    the local executor without changing the public lifecycle contract.
    """

    def ensure_local_worker(self, db: Session) -> RuntimeWorker:
        worker = db.scalar(
            select(RuntimeWorker).where(RuntimeWorker.worker_key == settings.local_worker_key)
        )
        now = datetime.now(timezone.utc)
        if not worker:
            worker = RuntimeWorker(
                worker_key=settings.local_worker_key,
                region=settings.local_worker_region,
                status="online",
                capacity=settings.local_worker_capacity,
                capabilities=json.dumps(["browser", "screenshot", "input"]),
                last_heartbeat_at=now,
            )
            db.add(worker)
        else:
            worker.status = "online"
            worker.capacity = settings.local_worker_capacity
            worker.region = settings.local_worker_region
            worker.last_heartbeat_at = now
        db.commit()
        db.refresh(worker)
        return worker

    def heartbeat(self, db: Session, worker: RuntimeWorker) -> None:
        now = datetime.now(timezone.utc)
        worker.last_heartbeat_at = now
        worker.status = "online"
        leases = db.scalars(
            select(RuntimeLease).where(
                RuntimeLease.worker_id == worker.id,
                RuntimeLease.status == "active",
            )
        ).all()
        for lease in leases:
            lease.expires_at = now + timedelta(seconds=settings.lease_ttl_seconds)
        db.commit()

    def recover_expired_leases(self, db: Session) -> int:
        """Fail orphaned sessions whose worker lease has expired.

        The current API process invokes this on startup. A distributed
        deployment should run the same reconciliation periodically.
        """
        now = datetime.now(timezone.utc)
        expired = db.scalars(
            select(RuntimeLease).where(
                RuntimeLease.status == "active",
                RuntimeLease.expires_at <= now,
            )
        ).all()
        recovered = 0
        for lease in expired:
            lease.status = "expired"
            lease.released_at = now
            session = db.get(BrowserSession, lease.session_id)
            if session and session.status in ACTIVE_SESSION_STATES:
                session.status = "error"
                session.error = "Runtime lease expired before clean shutdown"
                task = db.scalar(
                    select(RuntimeTask)
                    .where(
                        RuntimeTask.session_id == session.id,
                        RuntimeTask.status == "running",
                    )
                    .order_by(RuntimeTask.id.desc())
                )
                if task:
                    task.status = "failed"
                    task.error = "Worker lease expired"
                    task.updated_at = now
                recovered += 1
        if expired:
            db.commit()
        return recovered

    def active_session_count(self, db: Session, organization_id: int) -> int:
        return int(
            db.scalar(
                select(func.count(BrowserSession.id)).where(
                    BrowserSession.organization_id == organization_id,
                    BrowserSession.status.in_(ACTIVE_SESSION_STATES),
                )
            )
            or 0
        )

    def find_idempotent_session(
        self,
        db: Session,
        organization_id: int,
        idempotency_key: str | None,
    ) -> BrowserSession | None:
        if not idempotency_key:
            return None
        stored_key = f"{organization_id}:{idempotency_key}"
        return db.scalar(
            select(BrowserSession).where(
                BrowserSession.organization_id == organization_id,
                BrowserSession.idempotency_key == stored_key,
            )
        )

    def enqueue_start(
        self,
        db: Session,
        profile: Profile,
        idempotency_key: str | None,
    ) -> tuple[BrowserSession, RuntimeTask, bool]:
        existing = self.find_idempotent_session(
            db,
            profile.organization_id,
            idempotency_key,
        )
        if existing:
            task = db.scalar(
                select(RuntimeTask)
                .where(
                    RuntimeTask.session_id == existing.id,
                    RuntimeTask.task_type == "start",
                )
                .order_by(RuntimeTask.id.desc())
            )
            return existing, task, False

        stored_key = (
            f"{profile.organization_id}:{idempotency_key}"
            if idempotency_key
            else None
        )
        session = BrowserSession(
            organization_id=profile.organization_id,
            profile_id=profile.id,
            status="queued",
            runtime_type="browser",
            idempotency_key=stored_key,
        )
        db.add(session)
        db.flush()

        task = RuntimeTask(
            organization_id=profile.organization_id,
            profile_id=profile.id,
            session_id=session.id,
            task_type="start",
            status="queued",
            payload=json.dumps(
                {
                    "start_url": profile.start_url,
                    "locale": profile.locale,
                    "timezone": profile.timezone,
                }
            ),
        )
        db.add(task)
        db.commit()
        db.refresh(session)
        db.refresh(task)
        return session, task, True

    def acquire_local_lease(
        self,
        db: Session,
        session: BrowserSession,
        task: RuntimeTask,
    ) -> tuple[RuntimeWorker, RuntimeLease]:
        worker = self.ensure_local_worker(db)
        active_leases = int(
            db.scalar(
                select(func.count(RuntimeLease.id)).where(
                    RuntimeLease.worker_id == worker.id,
                    RuntimeLease.status == "active",
                )
            )
            or 0
        )
        if active_leases >= worker.capacity:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Runtime worker capacity is exhausted",
            )

        now = datetime.now(timezone.utc)
        lease = RuntimeLease(
            organization_id=session.organization_id,
            profile_id=session.profile_id,
            session_id=session.id,
            worker_id=worker.id,
            status="active",
            acquired_at=now,
            expires_at=now + timedelta(seconds=settings.lease_ttl_seconds),
        )
        db.add(lease)
        session.status = "provisioning"
        session.worker_id = worker.worker_key
        task.status = "running"
        task.locked_by = worker.worker_key
        task.locked_at = now
        task.attempt_count += 1
        task.updated_at = now
        db.commit()
        db.refresh(lease)
        return worker, lease

    def complete_start(
        self,
        db: Session,
        session: BrowserSession,
        task: RuntimeTask,
        current_url: str,
        current_title: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        session.status = "running"
        session.current_url = current_url
        session.current_title = current_title
        task.status = "succeeded"
        task.updated_at = now
        task.error = None
        db.commit()

    def fail_start(
        self,
        db: Session,
        session: BrowserSession,
        task: RuntimeTask,
        error: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        session.status = "error"
        session.error = error[:4000]
        task.status = "failed"
        task.error = error[:4000]
        task.updated_at = now
        lease = db.scalar(select(RuntimeLease).where(RuntimeLease.session_id == session.id))
        if lease:
            lease.status = "released"
            lease.released_at = now
        db.commit()

    def enqueue_stop(
        self,
        db: Session,
        session: BrowserSession,
    ) -> RuntimeTask:
        existing = db.scalar(
            select(RuntimeTask)
            .where(
                RuntimeTask.session_id == session.id,
                RuntimeTask.task_type == "stop",
                RuntimeTask.status.in_(("queued", "running")),
            )
            .order_by(RuntimeTask.id.desc())
        )
        if existing:
            return existing

        task = RuntimeTask(
            organization_id=session.organization_id,
            profile_id=session.profile_id,
            session_id=session.id,
            task_type="stop",
            status="queued",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def mark_stop_running(self, db: Session, task: RuntimeTask) -> None:
        now = datetime.now(timezone.utc)
        task.status = "running"
        task.locked_by = settings.local_worker_key
        task.locked_at = now
        task.attempt_count += 1
        task.updated_at = now
        db.commit()

    def complete_stop(
        self,
        db: Session,
        session: BrowserSession,
        task: RuntimeTask,
    ) -> None:
        now = datetime.now(timezone.utc)
        session.status = "stopped"
        session.stopped_at = now
        task.status = "succeeded"
        task.updated_at = now

        lease = db.scalar(select(RuntimeLease).where(RuntimeLease.session_id == session.id))
        if lease and lease.status == "active":
            lease.status = "released"
            lease.released_at = now
        db.commit()

    def fail_stop(
        self,
        db: Session,
        task: RuntimeTask,
        error: str,
    ) -> None:
        task.status = "failed"
        task.error = error[:4000]
        task.updated_at = datetime.now(timezone.utc)
        db.commit()


runtime_orchestrator = RuntimeOrchestrator()
