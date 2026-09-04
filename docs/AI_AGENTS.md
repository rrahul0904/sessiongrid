# AI Agent Architecture

## Role

AI is a bounded copilot inside SessionGrid, not an unrestricted autonomous social bot.

## Agent runtime

Each agent run receives:
- explicit task
- profile/workspace authorization
- current policy bundle
- approved tool set
- evidence/context bundle
- time/token/cost budget

The agent returns a structured plan or typed tool request. Side effects still pass through the policy/approval layer.

## Tool classes

### Read-only
- inspect page
- capture screenshot
- read visible content
- compare current vs expected state
- summarize notifications
- classify support items

### Controlled side effects
- navigate
- enter text
- create internal note/ticket
- submit an approved action

Controlled side effects require policy evaluation and may require human approval.

## Evidence intelligence

Every material conclusion should carry evidence:
- screenshot/artifact id
- page URL
- timestamp
- extracted observation
- confidence/uncertainty

## Context intelligence

Build a context package from:
- organization policy
- workspace/client rules
- profile metadata
- current task
- recent approved workflow state
- relevant documents/templates
- live page observations

The agent should not infer missing permissions or invent external facts.

## Guardrails

- allowlisted tools only
- maximum action count
- cost/token budget
- no credential visibility
- no CAPTCHA solving
- no detection-evasion tooling
- no automatic high-risk publishing without configured approval
- complete run trace
