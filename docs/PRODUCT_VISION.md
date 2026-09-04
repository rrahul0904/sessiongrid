# Product Vision

## Thesis

SessionGrid is the operating system for teams that manage many **authorized** social/web/mobile workspaces. It combines persistent isolated sessions, remote visual control, permissions, evidence, audit trails, workflow automation and AI-assisted operations in one control plane.

The wedge is not "anti-detect." The wedge is **operational control**: an agency or brand should be able to give a teammate or approved agent access to a workspace without scattering passwords, phones, VPNs and screenshots across multiple tools.

## Primary ICP

1. Social agencies managing 20–200 legitimate client accounts.
2. Multi-location brands with regional workspaces.
3. Support/community teams sharing controlled account access.
4. Localization and QA teams validating region-specific experiences.
5. Enterprise teams requiring auditability and private runtime pools.

## Product principles

- Human ownership is always clear.
- Credentials and session state are isolated from broad team access.
- Every sensitive action is attributable.
- Automation is policy-aware and approval-capable.
- Browser and Android runtimes share one orchestration model.
- Cost per active runtime is visible and controllable.
- SessionGrid does not provide ban-evasion or platform-manipulation capabilities.

## North-star workflow

```text
Create workspace
   -> assign owner + policy
   -> start isolated runtime
   -> operate manually or invoke approved workflow
   -> capture evidence
   -> require approval for sensitive step
   -> execute
   -> append audit + usage event
   -> stop runtime while preserving approved state
```

## Success metrics

- weekly active organizations
- active managed profiles per organization
- successful runtime-start rate
- median session launch latency
- % work completed without credential sharing
- approval turnaround time
- workflow success rate
- runtime cost per completed task
- customer retention by managed-profile cohort
