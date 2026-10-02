# StrawberryMe

<p align="center">
  <img src="docs/strawberryme-banner.png" alt="StrawberryMe — adaptive architecture orientation and runtime evidence for software-engineering agents" width="100%">
</p>

<p align="center">
  <strong>Adaptive architecture orientation for software-engineering agents.</strong><br>
  Start small. Follow evidence. Expand only where uncertainty remains.
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-experimental-orange">
  <img alt="Version" src="https://img.shields.io/badge/version-0.3.0-red">
  <img alt="Python" src="https://img.shields.io/badge/python-%3E%3D3.11-3776AB">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-v2-5b5bd6">
  <img alt="Agent Skill" src="https://img.shields.io/badge/agent-skill-purple">
  <img alt="Built-in LLM" src="https://img.shields.io/badge/built--in%20LLM-none-black">
</p>

---

## What StrawberryMe is

StrawberryMe is a **persistent architecture-orientation and evidence interface for coding agents**.

Coding agents are usually capable of implementing local code. The harder problem is preserving a trustworthy model of the surrounding system across long sessions, context compression, handoffs and dynamic runtime behavior.

StrawberryMe keeps three views separate:

```text
DECLARED
what the project says should be allowed

STATIC
what the source projection currently shows

OBSERVED
what happened in a concrete execution
```

v0.3 adds a fourth dimension: **adaptive depth**. StrawberryMe no longer assumes that every change needs the same amount of analysis.

> **Agents reason. StrawberryMe decides how much architecture evidence is needed from concrete signals.**

It is not a coding agent, planner, long-term task manager, deployment authority or built-in LLM.

---

# v0.3.0 — Adaptive Evidence

The v0.3 operating principle is deliberately small:

```text
CHANGE SIGNALS
      ↓
RISK REASONS
      ↓
SMALLEST USEFUL CHECK
      ↓
OBSERVE
      ↓
EVIDENCE SUFFICIENT?
  ┌───────┴────────┐
 yes               no
  │                 │
VERIFY       EXPAND ONLY THE
             UNCERTAIN BRANCH
```

A documentation-only change should not trigger runtime probing. A change that touches an architectural boundary may need a bounded cursor and static verification. A change that introduces dynamic imports, runtime dispatch, plugins, process/network behavior or incomplete static evidence can escalate to a runtime probe.

There is no synthetic numeric confidence score. StrawberryMe returns concrete reasons such as:

```text
ARCHITECTURE_BOUNDARY_TOUCHED
DYNAMIC_BEHAVIOR_SIGNAL
STATIC_MAP_INCOMPLETE
EXPECTED_DELTA_ACTIVE
RUNTIME_ONLY_EDGE_PREVIOUSLY_OBSERVED
```

---

## What StrawberryMe v0.3.0 can do today

| Capability | v0.3.0 behavior |
|---|---|
| Source identity | Binds plans and observations to Git/source snapshot identity. |
| Current MAP | Python AST projection of modules, symbols and static dependencies. |
| Adaptive MAP Cursor | Chooses a small cursor horizon from concrete change signals instead of always expanding the graph. |
| I/O orientation | Exposes function inputs and outputs from Python annotations. |
| Architecture boundaries | Evaluates declared path boundaries and forbidden dependency rules. |
| Future Delta | Records intended static edge additions/removals. |
| Change assessment | Classifies a supplied or dirty-file change scope as LOW, MEDIUM or HIGH with explicit reason codes. |
| Minimal probe planning | Builds the smallest runtime case needed for the current uncertainty. |
| Execution Envelope | Freezes executable class, source snapshot, filesystem policy, network policy, process policy, named environment access and resource limits. |
| Envelope enforcement | Python runtime probing can block disallowed project writes, network connects and process spawning. |
| Approval gate | Capability-expanding plans remain pending until explicitly approved outside the normal MCP run path. |
| Observed MAP | Captures project-internal Python runtime call edges. |
| Runtime effects | Captures selected file-write, network-connect and process-spawn effects. |
| Runtime-only edges | Shows observed relationships absent from the static projection. |
| Adaptive follow-up | Stops after decisive evidence or recommends expansion only around unresolved runtime-only branches. |
| Stale-plan refusal | A probe plan cannot run after its bound source snapshot changes. |
| Stale-evidence refusal | Runtime evidence is not silently reused after source changes. |
| Claude Code adapter | Session, compaction, edit and stop lifecycle hooks can surface orientation or enforce deterministic completion checks. |
| Harness-neutral core | MCP/CLI/core remain usable without Claude Code or any specific agent provider. |

---

## Adaptive verification paths

### Low signal

Example: README-only change.

```text
ASSESS
risk: LOW
reason: NON_CODE_ONLY

recommended:
STATIC_ONLY
```

No runtime probe is needed.

### Medium signal

Example: code inside a declared application boundary changes but no dynamic behavior is visible.

```text
ASSESS
risk: MEDIUM
reason: ARCHITECTURE_BOUNDARY_TOUCHED

recommended:
CURSOR_THEN_VERIFY
```

### High signal

Example:

```python
module = importlib.import_module(configured_adapter)
handler = getattr(module, configured_handler)
```

StrawberryMe can report:

```text
risk: HIGH
reasons:
- DYNAMIC_BEHAVIOR_SIGNAL
- ARCHITECTURE_BOUNDARY_TOUCHED

recommended:
MINIMAL_RUNTIME_PROBE
```

The risk label is not a probability. It is a deterministic routing state derived from observable signals.

---

## Execution Envelope

A v0.3 probe is no longer just an arbitrary command. `strawberry_probe_plan` creates a frozen plan with an execution envelope.

Example:

```text
EXECUTION ENVELOPE

source_snapshot: S17
allowed_executables:
  - python
filesystem: TEMP_WRITE
network: DENY
process_spawn: DENY
allowed_env_names: []
max_cases: 3
max_repeats: 3
max_runtime_seconds: 60
```

The envelope is validated before execution and source-bound.

If the source changes:

```text
PLAN S17
source becomes S18
      ↓
STALE_PLAN
```

If observed behavior exceeds the envelope:

```text
probe attempts project write
filesystem = TEMP_WRITE
      ↓
blocked
      ↓
ENVELOPE_EXCEEDED
      ↓
NEW_PLAN_REQUIRED
```

The Python probe can currently enforce selected filesystem, network and process-spawn limits. This is still **not a general-purpose OS security sandbox**. Native code, non-Python child environments and host-level isolation remain the responsibility of the harness or an external sandbox.

---

## Adaptive expansion

StrawberryMe does not automatically fan out into an exhaustive probe matrix.

After a run it chooses a bounded next action:

```text
ENVELOPE_EXCEEDED
→ NEW_PLAN_REQUIRED

architecture violation observed
→ VERIFY_AND_REPORT

runtime-only relationship remains unexplained
→ EXPAND_UNCERTAIN_BRANCH

runtime coverage missing
→ REFINE_PROBE

no unresolved branch
→ VERIFY
```

Example:

```text
P1
PaymentService → PluginLoader
PluginLoader → RuntimeAdapter

runtime-only:
RuntimeAdapter → LegacyDB
```

The next recommendation is not “scan everything”. It is:

```text
EXPAND_UNCERTAIN_BRANCH
TARGET
module:...RuntimeAdapter
```

---

## Public MCP v2 surface

```text
strawberry_status()

strawberry_assess(paths=[], target=None)

strawberry_cursor(target, horizon=1, adaptive=False)

strawberry_preflight(add=[], remove=[])

strawberry_probe_plan(
    command,
    target=None,
    paths=[],
    expected_runtime_edges=[],
    forbidden_runtime_edges=[],
    filesystem="TEMP_WRITE",
    network="DENY",
    process_spawn="DENY",
    allowed_env_names=[],
    max_cases=3,
    max_repeats=3,
    max_runtime_seconds=60,
)

strawberry_probe_run(plan_id)

strawberry_verify()
```

`strawberry_observe(...)` remains as a low-level v0.2-compatible operation. New agent integrations should prefer `probe_plan → probe_run`.

The MCP surface intentionally does **not** expose an approval tool. Capability-expanding approval is expected to come from a user/harness-controlled path. The bundled CLI provides a local approval command; it records a policy signal, not cryptographic proof of human identity.

---

## CLI example

Assess a change:

```bash
strawberry --root . assess --path app/application/payment.py
```

Use an adaptive cursor:

```bash
strawberry --root . cursor PaymentService --adaptive
```

Create a safe local probe plan:

```bash
strawberry --root . probe-plan \
  --path app/application/payment.py \
  -- python -m pytest tests/test_payment.py -q
```

Run the returned plan:

```bash
strawberry --root . probe-run <plan-id>
```

A capability-expanding plan, for example with network enabled, returns `APPROVAL_REQUIRED`:

```bash
strawberry --root . probe-plan \
  --network ALLOW \
  --env PAYMENT_API_KEY \
  -- python scripts/live_probe.py
```

Local approval is explicit:

```bash
strawberry --root . probe-approve <plan-id> --by operator
strawberry --root . probe-run <plan-id>
```

Environment variable **names** may be declared; StrawberryMe does not intentionally persist their values.

---

## Claude Code lifecycle adapter

v0.3 includes a thin optional adapter under:

```text
integrations/claude-code/hooks/hooks.json
```

It uses deterministic command hooks rather than another LLM layer:

```text
SessionStart
→ restore compact StrawberryMe orientation

PreCompact
→ re-surface architecture state before context compression

PreToolUse Write|Edit
→ assess the touched file; stay quiet for LOW signal

Stop
→ run deterministic StrawberryMe completion checks
```

The Stop hook blocks only on concrete current evidence such as build failure, hard static boundary failure, incomplete expected delta or violated runtime evidence. Missing optional runtime evidence by itself is not converted into a failure.

The core does not depend on Claude Code. Other harnesses can integrate the same MCP/CLI semantics through their own lifecycle mechanisms.

---

## Agent Skill

The Skill describes the control loop, but v0.3 moves important guarantees into code:

```text
ASSESS
      ↓
ADAPTIVE CURSOR when useful
      ↓
PREFLIGHT when architecture is intended to move
      ↓
IMPLEMENT
      ↓
PLAN minimal runtime evidence only when needed
      ↓
RUN inside frozen envelope
      ↓
FOLLOW evidence, not a fixed checklist
      ↓
VERIFY
```

Key rules:

- `BUILD PASS` does not imply `ARCHITECTURE PASS`.
- `STATIC PASS` does not imply `RUNTIME PASS`.
- A single runtime trace does not imply whole-program coverage.
- Unknown evidence remains unknown.
- Runtime evidence is source-bound.
- Probe plans are source-bound.
- Capability expansion requires a new/approved envelope.
- Do not broaden context or runtime probes when current evidence is already decisive.

---

## Architecture example

Declared rule:

```text
application !→ database
```

Static source:

```text
PaymentService → PaymentPort
STATIC PASS
```

Runtime:

```text
PaymentService → PluginLoader
PluginLoader → LegacyAdapter
LegacyAdapter → Database
```

StrawberryMe can distinguish:

```text
STATIC
PASS

OBSERVED
runtime-only relationship present

DECLARED
application !→ database

RESULT
VIOLATED_ON_TRACE
```

If the runtime path instead reveals a new but non-forbidden adapter relationship, StrawberryMe can return `EXPAND_UNCERTAIN_BRANCH` rather than declaring failure or recursively scanning the whole system.

---

## What v0.3 does not claim

StrawberryMe does not claim that:

- static analysis reconstructs a complete runtime architecture;
- one trace covers every execution path;
- the execution envelope is equivalent to a hardened container or VM sandbox;
- risk states are statistical probabilities;
- a passing probe proves general program correctness;
- the Current or Observed MAP is canonical truth;
- every DI container, native extension, generated dependency, SQL relation or external-service semantic is visible.

The goal is bounded, inspectable evidence rather than false certainty.

---

## v0.3 acceptance gates

The v0.3 hypothesis should be tested against at least these gates:

```text
G1  LOW changes avoid unnecessary runtime work.
G2  dynamic/boundary signals escalate to a minimal probe.
G3  a source change invalidates an existing plan.
G4  the execution envelope blocks a seeded forbidden capability.
G5  a runtime-only architecture edge is surfaced.
G6  follow-up expands only the unresolved branch.
G7  a completion hook blocks a concrete architecture failure.
```

A useful A/B/C evaluation remains:

```text
A  coding agent without StrawberryMe
B  agent + static StrawberryMe orientation
C  agent + adaptive StrawberryMe evidence loop
```

Measure boundary violations, missed dynamic dependencies, false completion claims, token/tool-call cost and unnecessary probe executions.

---

## License

StrawberryMe is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See [LICENSE](LICENSE).
