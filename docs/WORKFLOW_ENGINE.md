# Workflow and Approval Engine

## Purpose

SessionGrid workflows are durable, tenant-scoped state machines for authorized operations. The first implementation deliberately supports a small typed step set instead of arbitrary code execution.

Supported step types:

- `note` — records deterministic workflow context
- `require_artifact` — verifies that profile evidence exists
- `approval` — pauses the run until a reviewer explicitly approves or rejects it

## Lifecycle

```text
definition
   |
   v
workflow run (running)
   |
   +--> note --------------------> succeeded
   |
   +--> require_artifact --------> succeeded / failed
   |
   +--> approval ----------------> waiting_approval
                                      |
                          +-----------+-----------+
                          |                       |
                       approve                 reject
                          |                       |
                          v                       v
                       resume                   failed
                          |
                          v
                    remaining steps
                          |
                          v
                      succeeded
```

Every run persists step-level state and timestamps. Approvals are first-class records rather than transient UI confirmations.

## Built-in evidence-review workflow

Each bootstrapped organization receives `evidence-review:v1`:

1. record a checkpoint
2. require a screenshot artifact for the selected profile
3. request explicit human approval
4. record completion

This connects the runtime evidence system to the approval system without allowing an agent or workflow to invent evidence.

## API

```text
GET  /api/v1/workflows/definitions
POST /api/v1/workflows/definitions

POST /api/v1/workflows/definitions/{id}/runs
GET  /api/v1/workflows/runs
GET  /api/v1/workflows/runs/{id}

GET  /api/v1/approvals
POST /api/v1/approvals/{id}/decision
```

Definition creation requires manager-or-higher. Starting runs requires operator-or-higher. Approval decisions require reviewer-or-higher.

## Definition example

```json
{
  "name": "Content QA Checkpoint",
  "slug": "content-qa-checkpoint",
  "version": 1,
  "definition": {
    "steps": [
      {
        "key": "start",
        "type": "note",
        "message": "QA started"
      },
      {
        "key": "review",
        "type": "approval",
        "prompt": "Approve this checkpoint?"
      },
      {
        "key": "complete",
        "type": "note",
        "message": "QA approved"
      }
    ]
  }
}
```

## Evidence semantics

`require_artifact` looks for a real persisted artifact owned by the same organization/profile. It returns the artifact id and SHA-256 in step output. Missing evidence fails the run rather than silently bypassing the check.

## Current execution model

The engine advances synchronously through deterministic steps until it:

- finishes,
- fails, or
- reaches an approval.

The run is durable while waiting for approval. A decision resumes execution from the next step.

## Next steps

The typed executor registry should grow carefully:

- runtime acquisition/release
- navigate/read-only inspection
- capture evidence
- compare evidence
- create internal ticket/webhook
- bounded AI draft
- policy evaluation
- approved side effect

Sensitive side effects should continue to pause at approval/policy gates. Arbitrary Python/JavaScript execution should not become a workflow step type.
