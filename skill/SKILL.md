---
name: strawberryme
description: Persistent architecture orientation and evidence-bound verification for software-engineering agents. Use StrawberryMe to preserve I/O, dependencies, boundaries, intended structural deltas and source-bound runtime evidence while adapting verification depth to concrete risk signals.
---

# StrawberryMe Skill

StrawberryMe is an architecture-orientation and verification interface, not a coding agent, planner, deployment authority or security sandbox.

Its operating principle is:

```text
Start small.
Follow evidence.
Expand only uncertainty.
```

Do not run the full workflow mechanically for every edit.

## Operating loop

1. `strawberry_status` — establish source identity, MAP/cache health, current architecture failures, provider capabilities and stale/current runtime evidence.
2. `strawberry_assess` — classify the concrete changed area. Use the returned reasons literally; do not invent numerical confidence.
3. `strawberry_cursor` — open only the architecture neighborhood needed for the task. Prefer adaptive mode when the required horizon is unclear.
4. `strawberry_preflight` — record only intentional static edge additions/removals when architecture is expected to change.
5. Implement with the normal coding harness.
6. When runtime behavior can materially change the claim, use `strawberry_probe_plan`, obtain `strawberry_probe_approve` only when the plan requires approval, then use `strawberry_probe_run`. Do not bypass provider capability failures.
7. `strawberry_verify` — check build, static boundaries, expected delta and current source-bound runtime evidence before a completion claim.
8. Use `strawberry_history` when the question is what structurally changed across verification states or runtime observations.

## Adaptive routing

Treat StrawberryMe's recommended path as a minimum evidence path, not a universal checklist:

```text
LOW
→ static-only path may be enough

MEDIUM
→ bounded cursor + verify

HIGH
→ minimal runtime probe is normally warranted
```

Expand only the unresolved branch. A runtime-only edge should cause targeted follow-up around that relationship, not a repository-wide probe.

## Execution providers and envelopes

`ExecutionEnvelope` is an execution contract, not an OS sandbox.

Before a probe runs, StrawberryMe compares the envelope's required enforcement with the selected provider's declared capabilities. Respect these outcomes:

```text
PROVIDER_CAPABILITY_INSUFFICIENT
→ do not run and do not downgrade silently

STALE_PLAN
→ create a new source-bound plan

APPROVAL_REQUIRED
→ obtain explicit approval before capability expansion

ENVELOPE_EXCEEDED
→ stop; create a new plan if broader capability is actually required
```

The built-in `local-python` provider uses Python audit/profile instrumentation. Its enforcement level is `PYTHON_AUDIT`; it is not `OS_ISOLATED`.

Never describe Python audit-hook enforcement as container, namespace, seccomp, Landlock or host isolation.

## Evidence discipline

Keep these distinctions explicit:

```text
BUILD PASS != ARCHITECTURE PASS
STATIC PASS != RUNTIME PASS
SATISFIED_ON_TRACE != GENERAL CORRECTNESS
```

Runtime evidence is valid only for the source snapshot and concrete execution that produced it.

If evidence is `STALE`, `INCONCLUSIVE`, `NOT_OBSERVED`, `AMBIGUOUS`, `NOT_FOUND`, parse-incomplete or provider-insufficient, do not fill the gap with model memory.

Current MAP, Observed MAP, parser cache and history are derived technical views. Repository source remains authoritative.

## Static and dynamic interpretation

v0.4 improves Python import/call resolution and uses AST-derived dynamic signals. Treat signal names as evidence reasons, not proof that a behavior occurred.

For example:

```text
DYNAMIC_IMPORT
```

means the source contains a syntactic dynamic-import mechanism. Whether a particular target was actually loaded requires observed runtime evidence.

## History

Use `strawberry_history` to answer bounded questions such as:

```text
Which static edges appeared since the previous verification?
Which edges disappeared?
Which architecture violations are new or resolved?
Which runtime relationships/effects changed between recent traces?
```

Do not treat historical evidence as current after its source binding becomes stale.

## Harness integration

Harness adapters may automate lifecycle use, but the core semantics must remain portable.

For Claude Code, the included adapter can restore orientation on session start/compaction, surface risk around edits and gate completion on concrete blocking evidence.

For other harnesses, use MCP/CLI directly. Never assume a host provides isolation or approval mechanisms unless it explicitly does.

## Completion rule

A completion claim is acceptable only when current evidence does not contain an unresolved blocking failure relevant to the task. Absence of runtime evidence is not automatically a failure when the assessed path did not require runtime validation.
