# Android Runtime Plan

## Why Android is Phase 5, not Phase 0

Browser sessions validate the product and control-plane UX at much lower infrastructure complexity. Real persistent Android workspaces require device virtualization, image management, app lifecycle, streaming, storage and stronger sandboxing.

## Provider interface

Implement `AndroidRuntimeProvider` behind the same orchestration contract used by browser runtimes:

- provision
- start
- inspect
- stream
- send_touch
- send_text
- capture
- stop
- snapshot_state
- destroy

## Initial infrastructure direction

Evaluate managed/self-hosted Anbox Cloud or a Cuttlefish-based provider rather than building a custom Android virtualization stack.

## Required capabilities

- persistent workspace identity
- controlled application install/update where permitted
- touch/text input
- low-latency stream
- screenshot/recording
- lifecycle reset
- runtime-minute metering
- capacity reporting
- tenant isolation
- encrypted state snapshots

## Capacity model

Schedule based on:
- CPU
- memory
- GPU availability if required
- region
- runtime image/version
- tenant isolation policy
- current concurrency

## Security

Android workers are high-risk render/execution boundaries and should be isolated from control-plane databases and secrets. Workers receive only short-lived scoped credentials.

## Product policy

Android support is for authorized account operations, app QA, localization, support and similar legitimate workflows. Do not advertise or engineer Android runtime as a method for evading platform enforcement.
