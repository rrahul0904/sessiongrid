# Automation Engine

## Goal

Automate repetitive authorized operations without creating an opaque bot fleet.

## Execution model

```text
Trigger
  -> policy check
  -> acquire runtime
  -> inspect/read
  -> optional agent reasoning
  -> approval if action is sensitive
  -> execute typed action
  -> capture evidence
  -> append audit
  -> release runtime
```

## Recommended foundation

Use Temporal once workflows become durable/distributed. The initial MVP should not add a workflow engine before the runtime lifecycle is reliable.

## Step types

- open_profile
- navigate
- wait_for_condition
- capture_screenshot
- extract_visible_data
- compare_evidence
- draft_text
- request_approval
- execute_approved_action
- create_ticket/webhook
- stop_profile

## Reliability

Each side-effecting step needs:
- idempotency key
- timeout
- retry policy
- cancellation behavior
- typed output
- evidence reference

## Policy

The workflow engine must be unable to bypass organization policies. Sensitive actions require an allow decision from the policy service and, where configured, a human approval record.

## Initial templates

- broken-link QA
- localization screenshot comparison
- community/support inbox triage
- content-presence verification
- scheduled evidence capture
