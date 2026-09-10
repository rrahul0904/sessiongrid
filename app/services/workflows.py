import json
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Approval,
    Artifact,
    Profile,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStepRun,
)


ALLOWED_STEP_TYPES = {"note", "require_artifact", "approval"}


def canonical_json(value: dict | list) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


class WorkflowEngine:
    def validate_definition(self, definition: dict) -> list[dict]:
        if not isinstance(definition, dict):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Workflow definition must be an object")
        steps = definition.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= 50:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Workflow requires 1-50 steps")

        keys: set[str] = set()
        normalized: list[dict] = []
        for index, raw in enumerate(steps):
            if not isinstance(raw, dict):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Step {index} must be an object")
            key = raw.get("key")
            step_type = raw.get("type")
            if not isinstance(key, str) or not key or len(key) > 120:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Step {index} has an invalid key")
            if key in keys:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Duplicate step key: {key}")
            if step_type not in ALLOWED_STEP_TYPES:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Unsupported step type: {step_type}",
                )
            keys.add(key)
            step = dict(raw)
            if step_type == "approval" and not step.get("prompt"):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Approval step {key} requires prompt")
            if step_type == "require_artifact":
                step.setdefault("kind", "screenshot")
            if step_type == "note":
                step.setdefault("message", key)
            normalized.append(step)
        return normalized

    def ensure_builtin_definition(
        self,
        db: Session,
        organization_id: int,
        user_id: int,
    ) -> WorkflowDefinition:
        existing = db.scalar(
            select(WorkflowDefinition).where(
                WorkflowDefinition.organization_id == organization_id,
                WorkflowDefinition.slug == "evidence-review",
                WorkflowDefinition.version == 1,
            )
        )
        if existing:
            return existing

        definition = {
            "steps": [
                {
                    "key": "checkpoint",
                    "type": "note",
                    "message": "Evidence review checkpoint started",
                },
                {
                    "key": "evidence",
                    "type": "require_artifact",
                    "kind": "screenshot",
                },
                {
                    "key": "review",
                    "type": "approval",
                    "prompt": "Confirm that the captured evidence is acceptable.",
                },
                {
                    "key": "complete",
                    "type": "note",
                    "message": "Evidence was reviewed and approved",
                },
            ]
        }
        workflow = WorkflowDefinition(
            organization_id=organization_id,
            name="Evidence Review",
            slug="evidence-review",
            version=1,
            is_active=True,
            definition=canonical_json(definition),
            created_by_user_id=user_id,
        )
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        return workflow

    def start_run(
        self,
        db: Session,
        *,
        definition: WorkflowDefinition,
        profile_id: int | None,
        input_payload: dict,
        user_id: int,
        actor: str,
    ) -> WorkflowRun:
        steps = self.validate_definition(json.loads(definition.definition))
        if not definition.is_active:
            raise HTTPException(status.HTTP_409_CONFLICT, "Workflow definition is inactive")

        if profile_id is not None:
            profile = db.scalar(
                select(Profile).where(
                    Profile.id == profile_id,
                    Profile.organization_id == definition.organization_id,
                )
            )
            if not profile:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")

        now = datetime.now(timezone.utc)
        run = WorkflowRun(
            organization_id=definition.organization_id,
            definition_id=definition.id,
            profile_id=profile_id,
            status="running",
            current_step_index=0,
            input=canonical_json(input_payload),
            started_by_user_id=user_id,
            created_at=now,
            started_at=now,
        )
        db.add(run)
        db.flush()

        for index, step in enumerate(steps):
            db.add(
                WorkflowStepRun(
                    organization_id=definition.organization_id,
                    run_id=run.id,
                    step_index=index,
                    step_key=step["key"],
                    step_type=step["type"],
                    status="pending",
                    input=canonical_json(step),
                )
            )
        db.commit()
        db.refresh(run)
        return self.advance(db, run=run, actor=actor)

    def _fail_run(
        self,
        db: Session,
        run: WorkflowRun,
        step_run: WorkflowStepRun,
        error: str,
    ) -> WorkflowRun:
        now = datetime.now(timezone.utc)
        step_run.status = "failed"
        step_run.error = error
        step_run.completed_at = now
        run.status = "failed"
        run.error = error
        run.completed_at = now
        db.commit()
        db.refresh(run)
        return run

    def advance(self, db: Session, *, run: WorkflowRun, actor: str) -> WorkflowRun:
        definition = db.get(WorkflowDefinition, run.definition_id)
        steps = self.validate_definition(json.loads(definition.definition))
        step_runs = {
            step.step_index: step
            for step in db.scalars(
                select(WorkflowStepRun)
                .where(WorkflowStepRun.run_id == run.id)
                .order_by(WorkflowStepRun.step_index)
            ).all()
        }

        while run.current_step_index < len(steps):
            index = run.current_step_index
            spec = steps[index]
            step_run = step_runs[index]
            now = datetime.now(timezone.utc)
            step_run.started_at = step_run.started_at or now
            step_run.status = "running"

            if spec["type"] == "note":
                step_run.output = canonical_json({"message": spec.get("message", spec["key"])})
                step_run.status = "succeeded"
                step_run.completed_at = now
                run.current_step_index = index + 1
                db.commit()
                continue

            if spec["type"] == "require_artifact":
                if run.profile_id is None:
                    return self._fail_run(
                        db,
                        run,
                        step_run,
                        "Artifact requirement needs a profile-scoped workflow run",
                    )
                kind = spec.get("kind", "screenshot")
                artifact = db.scalar(
                    select(Artifact)
                    .where(
                        Artifact.organization_id == run.organization_id,
                        Artifact.profile_id == run.profile_id,
                        Artifact.kind == kind,
                    )
                    .order_by(Artifact.id.desc())
                )
                if not artifact:
                    return self._fail_run(
                        db,
                        run,
                        step_run,
                        f"Required artifact is missing: {kind}",
                    )
                step_run.output = canonical_json(
                    {
                        "artifact_id": artifact.id,
                        "kind": artifact.kind,
                        "sha256": artifact.sha256,
                    }
                )
                step_run.status = "succeeded"
                step_run.completed_at = now
                run.current_step_index = index + 1
                db.commit()
                continue

            if spec["type"] == "approval":
                approval = db.scalar(
                    select(Approval).where(Approval.step_run_id == step_run.id)
                )
                if not approval:
                    approval = Approval(
                        organization_id=run.organization_id,
                        run_id=run.id,
                        step_run_id=step_run.id,
                        status="pending",
                        prompt=spec["prompt"],
                        requested_by=actor,
                        requested_at=now,
                    )
                    db.add(approval)
                step_run.status = "waiting_approval"
                run.status = "waiting_approval"
                db.commit()
                db.refresh(run)
                return run

        run.status = "succeeded"
        run.output = canonical_json({"completed_steps": len(steps)})
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return run

    def decide(
        self,
        db: Session,
        *,
        approval: Approval,
        decision: str,
        reason: str | None,
        actor: str,
    ) -> WorkflowRun:
        if approval.status != "pending":
            raise HTTPException(status.HTTP_409_CONFLICT, "Approval has already been decided")

        run = db.get(WorkflowRun, approval.run_id)
        step_run = db.get(WorkflowStepRun, approval.step_run_id)
        now = datetime.now(timezone.utc)

        approval.status = decision
        approval.decided_by = actor
        approval.reason = reason
        approval.decided_at = now

        if decision == "rejected":
            step_run.status = "failed"
            step_run.error = reason or "Approval rejected"
            step_run.completed_at = now
            run.status = "failed"
            run.error = reason or "Approval rejected"
            run.completed_at = now
            db.commit()
            db.refresh(run)
            return run

        step_run.status = "succeeded"
        step_run.output = canonical_json(
            {
                "decision": "approved",
                "decided_by": actor,
                "reason": reason,
            }
        )
        step_run.completed_at = now
        run.status = "running"
        run.current_step_index = step_run.step_index + 1
        db.commit()
        return self.advance(db, run=run, actor=actor)


workflow_engine = WorkflowEngine()
