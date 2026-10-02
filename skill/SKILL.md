---
name: strawberryme
description: Adaptive architecture orientation and source-bound runtime evidence for software-engineering agents. Use StrawberryMe to choose the smallest useful verification path, preserve I/O and dependency orientation, detect architecture drift and expand only unresolved evidence branches.
---

# StrawberryMe Skill

StrawberryMe is an architecture-orientation and evidence interface, not a coding agent. It contains no planner, built-in LLM, autonomous task manager, commit policy or deployment authority.

## Operating principle

Do not run the same checklist for every change.

Use this control loop:

1. `strawberry_status` — establish current source identity and existing evidence state.
2. `strawberry_assess` — evaluate the concrete change scope. Treat LOW/MEDIUM/HIGH as deterministic routing states, not probabilities.
3. Use `strawberry_cursor(..., adaptive=true)` when orientation is needed. Do not expand the graph beyond the evidence-relevant horizon.
4. Use `strawberry_preflight` only when architecture edges are intentionally expected to change.
5. Implement with the normal coding harness.
6. If assessment or later evidence shows runtime uncertainty, create `strawberry_probe_plan` rather than directly broadening the investigation.
7. Run only a READY/approved plan with `strawberry_probe_run`.
8. Follow the returned adaptive next action. Expand only targets named by unresolved runtime evidence.
9. Call `strawberry_verify` before claiming completion when StrawberryMe evidence is part of the task.

## Evidence rules

- `BUILD PASS` does not imply `ARCHITECTURE PASS`.
- `STATIC PASS` does not imply `RUNTIME PASS`.
- `SATISFIED_ON_TRACE` applies only to the bound source snapshot and executed trace.
- Never reuse `STALE` evidence or a `STALE_PLAN`.
- Never convert `UNKNOWN`, missing coverage or parse errors into success.
- Do not invent architecture facts when a cursor is ambiguous or incomplete.
- A runtime-only edge is a reason to inspect that branch, not the whole repository.
- A concrete violation is already useful evidence; do not expand the probe merely to accumulate more failures.

## Execution Envelope

Treat the execution envelope literally.

It can constrain:

- source snapshot;
- allowed executable class;
- filesystem write policy;
- network access;
- process spawning;
- named environment-variable access;
- case count;
- repeat count;
- runtime budget.

If StrawberryMe reports `ENVELOPE_EXCEEDED`, stop. Do not bypass the envelope. Create a new plan with the required capability and obtain approval through the user/harness-controlled path.

Capability-expanding approval is a policy signal. Do not describe it as proof of human identity unless the host provides an authenticated human-approval mechanism.

Never print or persist secret values. Only environment-variable names belong in plans or reports.

## Adaptive routing

Typical routing:

```text
LOW
→ static only

MEDIUM
→ bounded cursor + verify

HIGH
→ minimal runtime probe
```

Escalation reasons can include:

```text
ARCHITECTURE_BOUNDARY_TOUCHED
DYNAMIC_BEHAVIOR_SIGNAL
STATIC_MAP_INCOMPLETE
EXPECTED_DELTA_ACTIVE
RUNTIME_ONLY_EDGE_PREVIOUSLY_OBSERVED
```

Use the reason codes rather than guessing a confidence percentage.

## Runtime interpretation

Possible next actions include:

```text
NEW_PLAN_REQUIRED
VERIFY_AND_REPORT
EXPAND_UNCERTAIN_BRANCH
REFINE_PROBE
VERIFY
```

When `EXPAND_UNCERTAIN_BRANCH` is returned, narrow the next cursor/probe to the supplied target nodes. Do not turn it into repository-wide archaeology.

## Harness lifecycle

Where the host provides lifecycle hooks, prefer deterministic StrawberryMe integration:

- session start / context restoration → compact status/orientation;
- pre-compaction → preserve architecture orientation;
- code edit → assess touched scope, remaining silent for LOW-risk changes;
- stop/completion → block only on concrete current failures.

Do not require hook support. MCP and CLI remain the portable baseline.

The purpose of StrawberryMe is to keep architectural cognition and bounded execution evidence outside the model context while spending only the analysis effort that current evidence justifies.
