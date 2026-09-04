# UI / UX Specification

## Navigation

1. Dashboard
2. Screens
3. Profiles
4. Automation
5. Statistics / Cost
6. Audit
7. Settings / Organization

## Dashboard

Primary questions:
- What is active now?
- What needs attention?
- What failed?
- What is costing money?
- What requires approval?

Required surfaces:
- active sessions
- concurrency utilization
- recent failures
- pending approvals
- runtime minutes/cost
- recent audit events

## Screen wall

Each card shows:
- profile name
- platform
- owner
- runtime status
- streamed screen/frame
- start/stop
- screenshot/evidence action
- control ownership
- session age
- failure state

Support 1/2/3/4-column density and a focused single-session mode.

## Profiles

Table-first inventory:
- name
- platform
- workspace/client
- owner
- runtime type
- locale
- network policy
- current status
- last active
- health

## Automation

Workflow runs should be exception-first, not a decorative node canvas. Show queued/running/waiting approval/failed/completed runs and the exact step requiring intervention.

## Accessibility

- keyboard navigation
- visible focus states
- semantic buttons and dialogs
- WCAG AA contrast target
- reduced-motion support
- status communicated with text, not color alone

## Visual direction

Dark operator-console aesthetic inspired by the provided concept image, but with denser enterprise information hierarchy and clear separation between profile identity, runtime state, policy state and actions.
