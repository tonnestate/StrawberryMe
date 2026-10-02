# StrawberryMe

<p align="center">
  <img src="docs/strawberryme-banner.png" alt="StrawberryMe — persistent architecture orientation and evidence-bound verification for software-engineering agents" width="100%">
</p>

<p align="center">
  <strong>Persistent architecture orientation and evidence-bound verification for software-engineering agents.</strong><br>
  Start small. Follow evidence. Expand only uncertainty.
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-experimental-orange">
  <img alt="Version" src="https://img.shields.io/badge/version-0.4.0-red">
  <img alt="Python" src="https://img.shields.io/badge/python-%3E%3D3.11-3776AB">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-v2-5b5bd6">
  <img alt="Agent Skill" src="https://img.shields.io/badge/agent-skill-purple">
  <img alt="Built-in LLM" src="https://img.shields.io/badge/built--in%20LLM-none-black">
</p>

---

## What StrawberryMe is

StrawberryMe is a deterministic architecture-orientation and verification layer for coding agents. It externalizes information that agents frequently lose across long sessions, context compaction and handoffs:

```text
Where am I?
What comes in and what goes out?
What depends on this area?
Which boundaries matter?
What structural change was intended?
What did the source show?
What did this execution actually do?
What changed since the previous verification?
```

StrawberryMe is not a coding agent, planner, deployment authority, security sandbox or built-in LLM.

> **Agents reason. StrawberryMe preserves architecture orientation and binds claims to inspectable evidence.**

---

# v0.4.0 — Provider-aware persistent architecture evidence

v0.4 deepens the v0.3 adaptive loop instead of adding more languages or autonomous behavior.

```text
CHANGE SIGNALS
      ↓
ADAPTIVE CURSOR
      ↓
MINIMAL PROBE PLAN
      ↓
EXECUTION ENVELOPE
      ↓
PROVIDER CAPABILITY CHECK
      ↓
SOURCE-BOUND EXECUTION
      ↓
OBSERVED MAP
      ↓
VERIFY
      ↓
EVIDENCE HISTORY + ARCHITECTURE DIFF
```

The important distinction is now explicit:

```text
Execution Envelope
≠
OS Security Sandbox
```

The envelope describes what a probe is allowed to require. The execution provider declares what it can actually enforce. StrawberryMe refuses a plan when the requested enforcement is stronger than the selected provider can provide.

---

## What v0.4 adds

| Capability | v0.4 behavior |
|---|---|
| Execution Provider Contract | Providers declare filesystem, network and process enforcement strength plus instrumentation capability. |
| Fail-closed provider selection | A plan requiring `OS_ISOLATED` enforcement is rejected by the local Python provider instead of pretending Python audit hooks are a sandbox. |
| Local Python provider | Current built-in provider uses a normal local subprocess plus Python profile/audit instrumentation. Enforcement is explicitly `PYTHON_AUDIT`; OS isolation is `NONE`. |
| Better Python call resolution | Import aliases, imported symbols and relative imports are resolved before falling back to conservative short-name matching. |
| AST-based dynamic signals | Dynamic import, reflection, process creation, network clients, plugin entrypoints and configuration access are detected from syntax trees rather than source substrings. |
| Incremental MAP cache | Per-file parser results are cached in SQLite and unchanged files are reused instead of reparsing the repository on every MAP request. |
| Scan telemetry | `parsed_files`, `reused_files`, `cache_hit_ratio` and parser version are exposed. |
| Runtime evidence history | Runtime observations are retained as bounded source-bound records rather than only replacing the previous observation. |
| Verification history | Each verification records static edges, violations and relevant runtime evidence references. |
| Architecture diff | StrawberryMe can report added/removed static edges and newly introduced/resolved violations between the latest verification states. |
| Adaptive evidence loop | v0.3 behavior remains: risk is signal-driven, probes stay minimal, runtime-only branches are expanded selectively, and capability expansion requires a new plan. |
| Claude Code lifecycle adapter | SessionStart, PreCompact, PreToolUse and Stop hooks remain available as an optional harness adapter. |

Multi-language support remains intentionally deferred until this Python path is empirically useful.

---

## Truth model

StrawberryMe keeps three architecture views separate:

```text
DECLARED
project rules + intended delta

STATIC
source-derived Current MAP

OBSERVED
relationships/effects seen in a concrete source-bound execution
```

A result should never silently collapse these into one truth claim.

```text
BUILD PASS != ARCHITECTURE PASS
STATIC PASS != RUNTIME PASS
OBSERVED ON ONE TRACE != WHOLE-PROGRAM PROOF
```

---

## Execution providers

v0.4 introduces a provider contract instead of embedding container technology into the core.

The built-in provider currently declares approximately:

```text
provider_id: local-python
runtime: LOCAL_SUBPROCESS
filesystem_enforcement: PYTHON_AUDIT
network_enforcement: PYTHON_AUDIT
process_enforcement: PYTHON_AUDIT
python_instrumentation: true
arbitrary_command: false
```

An execution envelope can require one of:

```text
NONE
PYTHON_AUDIT
HOST_MANAGED
OS_ISOLATED
```

Example:

```text
required_enforcement: OS_ISOLATED
provider: local-python

→ PROVIDER_CAPABILITY_INSUFFICIENT
```

That failure is intentional. Python audit/profile hooks can improve observation and enforce policy inside cooperating Python execution, but they are not an OS security boundary.

Future providers can implement the same contract for harness-managed sandboxes, Docker/Podman or another isolation technology without changing StrawberryMe architecture semantics.

---

## Static MAP improvements

v0.4 still uses the standard-library Python AST, but call resolution is less naive.

These forms can now be resolved deterministically when the referenced project symbol exists:

```python
from app.worker import work as run_work
run_work()
```

```python
import app.worker as worker
worker.work()
```

```python
from .worker import work
work()
```

Short-name matching remains only a conservative fallback.

---

## Dynamic signals are structural

Adaptive risk no longer relies on comments or raw source substring matching. Signals are derived from AST nodes.

Examples include:

```text
DYNAMIC_IMPORT
REFLECTIVE_ACCESS
PROCESS_CREATION
NETWORK_CLIENT
PLUGIN_ENTRYPOINT
CONFIG_ACCESS
```

A comment containing `importlib.import_module(...)` therefore does not create a dynamic-import signal.

Assessment remains deterministic and explanatory:

```text
RISK HIGH
reasons:
- DYNAMIC_BEHAVIOR_SIGNAL
- ARCHITECTURE_BOUNDARY_TOUCHED
signals:
- DYNAMIC_IMPORT app/payment.py:81
```

There is deliberately no invented numerical confidence score.

---

## Incremental MAP

The MAP remains derived rather than canonical, but StrawberryMe no longer needs to reparse every unchanged Python file on every request.

```text
repository
   ↓
file metadata + parser version
   ↓
changed file? ── no ─→ reuse cached parser payload
      │
     yes
      ↓
parse only this file
      ↓
recompose project graph
```

`strawberry_status` exposes scan statistics such as:

```text
files: 420
parsed_files: 2
reused_files: 418
cache_hit_ratio: 0.9952
```

The cache is an optimization. The source repository remains authoritative.

---

## Evidence history and architecture diff

Runtime evidence is stored as history in `.strawberry/strawberry.db` and remains source-bound.

Verification also records a compact structural state. `strawberry_history` can compare the latest verification records:

```text
from snapshot S17
to snapshot S18

ADDED STATIC EDGE
PaymentService → PaymentPort

REMOVED STATIC EDGE
PaymentService → LegacyPaymentService

NEW VIOLATION
application → database
```

This is intended to answer not only “what is true now?” but also “what structurally changed since the previous verified state?”

History is evidence, not repository truth, and stale observations remain stale after source changes.

---

## Adaptive operating model

v0.4 preserves the v0.3 principle:

```text
ASSESS
  ↓
LOW     → static-only path
MEDIUM  → bounded cursor + verify
HIGH    → minimal runtime probe
```

A probe begins with the smallest useful case. StrawberryMe then reacts to evidence:

```text
no unresolved runtime branch
→ VERIFY

runtime-only relationship
→ EXPAND_UNCERTAIN_BRANCH

concrete violation
→ VERIFY_AND_REPORT

envelope breach
→ NEW_PLAN_REQUIRED

insufficient trace
→ REFINE_PROBE
```

Expansion outside the frozen envelope is never silently authorized.

---

## Public MCP v2 surface

```text
strawberry_status()
strawberry_assess(paths=None, target=None)
strawberry_cursor(target, horizon=1, adaptive=False)
strawberry_preflight(add=[], remove=[])

strawberry_probe_plan(
    command,
    target=None,
    paths=None,
    expected_runtime_edges=[],
    forbidden_runtime_edges=[],
    filesystem="TEMP_WRITE",
    network="DENY",
    process_spawn="DENY",
    required_enforcement="PYTHON_AUDIT",
    provider_id="local-python",
    allowed_env_names=[],
    max_cases=3,
    max_repeats=3,
    max_runtime_seconds=60,
)

strawberry_probe_run(plan_id)
strawberry_history(limit=10)
strawberry_verify(command=None, timeout_seconds=30)
```

`strawberry_observe(...)` remains available as a low-level compatibility API. New adaptive integrations should prefer `probe_plan → probe_run`.

---

## Agent Skill

The canonical operating procedure is in `SKILL.md`; `skill/SKILL.md` is kept as a compatibility copy.

The key rule is not “always run everything.” It is:

> **Use the smallest verification path supported by current evidence and expand only where uncertainty remains.**

The Skill does not substitute for provider capability checks. If a harness does not expose strong isolation, StrawberryMe must not infer it.

---

## Claude Code adapter

`integrations/claude-code/hooks/hooks.json` provides an optional lifecycle adapter:

```text
SessionStart
→ restore compact StrawberryMe orientation

PreCompact
→ refresh critical architecture context before context compaction

PreToolUse Write/Edit
→ surface material change signals without blocking low-risk edits

Stop
→ reject completion only when current StrawberryMe evidence contains a blocking failure
```

The core remains harness-neutral. Hooks are adapters, not the architecture.

---

## CLI examples

```bash
strawberry --root . status
strawberry --root . assess --path app/payment.py
strawberry --root . cursor PaymentService --adaptive
```

Create a local Python-audit probe:

```bash
strawberry --root . probe-plan \
  --required-enforcement PYTHON_AUDIT \
  --provider local-python \
  --path app/payment.py \
  -- python -m pytest tests/test_payment.py -q
```

A plan demanding OS-level isolation will fail on the built-in provider:

```bash
strawberry --root . probe-plan \
  --required-enforcement OS_ISOLATED \
  -- python -m pytest tests/test_payment.py -q
```

Inspect structural history:

```bash
strawberry --root . history --limit 10
```

---

## Execution-envelope semantics

The built-in Python provider can observe and attempt to block selected Python-level effects such as:

```text
FILE_WRITE
NETWORK_CONNECT
PROCESS_SPAWN
```

Its enforcement label is `PYTHON_AUDIT`, not `OS_ISOLATED`.

Native code, direct syscalls, alternate runtimes, inherited descriptors and host-level escape resistance are outside this provider's security guarantees. Stronger claims require a provider that explicitly advertises stronger enforcement.

---

## Persistence

SQLite under `.strawberry/` stores only derived StrawberryMe state, including:

```text
Future Delta
probe plans / approvals
per-file parser cache
latest runtime observation
runtime evidence history
verification history
```

Deleting `.strawberry/` removes this derived state; it does not modify repository source.

---

## Current limitations

- Python source MAP and runtime instrumentation only.
- Runtime profiling observes executed Python paths, not all possible paths.
- The built-in provider is not an OS sandbox.
- Static resolution is improved but is not full type/data-flow analysis.
- Dependency injection, generated code, native extensions and external-service semantics can remain unresolved.
- Incremental caching avoids repeated parsing but still recomposes the project graph from cached per-file payloads.
- No daemon and no background watcher.
- No built-in LLM.

Unknown evidence remains unknown.

---

## Evaluation target

The next meaningful proof is empirical rather than architectural.

Use the same tasks and repositories across:

```text
A  coding agent only
B  agent + StrawberryMe static orientation
C  agent + StrawberryMe adaptive + observed evidence
```

Measure at least:

```text
forbidden dependency introduction
missed consumers
runtime-only dependency detection
false completion claims
unnecessary probes
token usage
tool calls
elapsed time
```

StrawberryMe should expand further only if B/C materially improve architecture outcomes relative to their cost.

---

## License

StrawberryMe is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).
