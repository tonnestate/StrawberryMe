# StrawberryMe

<p align="center">
  <img src="docs/strawberryme-banner.png" alt="StrawberryMe — persistent architecture orientation and observed architecture verification for software-engineering agents" width="100%">
</p>

<p align="center">
  <strong>Persistent architecture orientation for software-engineering agents.</strong><br>
  Know where you are. Preserve boundaries. Observe what really happened.
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-experimental-orange">
  <img alt="Version" src="https://img.shields.io/badge/version-0.2.0-red">
  <img alt="Python" src="https://img.shields.io/badge/python-%3E%3D3.11-3776AB">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-v2-5b5bd6">
  <img alt="Agent Skill" src="https://img.shields.io/badge/agent-skill-purple">
  <img alt="Built-in LLM" src="https://img.shields.io/badge/built--in%20LLM-none-black">
</p>

---

## What StrawberryMe is

StrawberryMe is a **persistent architecture-orientation and verification interface for coding agents**.

A coding agent can usually implement code. The harder problem over long sessions is preserving a reliable model of the system and distinguishing what the source appears to do from what the running system actually did:

```text
Where am I?
      ↓
What comes in and what goes out?
      ↓
What depends on this area?
      ↓
Which system boundaries must remain intact?
      ↓
What structural change did I intend?
      ↓
What did the executed code actually do?
```

StrawberryMe externalizes that orientation so it does not depend on the model remembering the whole repository correctly.

It is deliberately **not** another coding agent. StrawberryMe contains no planner, no built-in LLM, no autonomous task manager, no deployment authority and no requirement for a permanently running agent.

> **Agents reason. StrawberryMe keeps architectural orientation and bounded execution evidence outside the context window.**

---

# v0.2.0 — Observed Architecture

v0.2 adds a third architecture view without turning StrawberryMe into a container platform or observability stack:

```text
DECLARED ARCHITECTURE
project boundaries + rules + expected delta
        │
        ▼
STATIC ARCHITECTURE
Python AST Current MAP
        │
        ▼
OBSERVED ARCHITECTURE
project-internal runtime calls + selected effects
```

The important new distinction is:

```text
STATIC PASS
is not the same as
RUNTIME PASS
```

A dependency can be invisible to conservative static analysis and still appear during a real execution through dynamic imports, plugin wiring, runtime dispatch or similar mechanisms.

StrawberryMe v0.2 can now execute an explicit Python command through a lightweight runtime probe, bind the observation to the exact source snapshot, and compare the resulting runtime edges against project architecture rules.

It still does **not** implement a security sandbox. Use the host harness sandbox when one is available.

---

## What StrawberryMe v0.2.0 can do today

| Capability | v0.2.0 behavior |
|---|---|
| Source identity | Binds observations to Git HEAD, branch, dirty state and a source snapshot fingerprint. |
| Current MAP | Builds a lightweight technical projection of Python modules, classes, functions and dependencies. |
| MAP Cursor | Returns a bounded neighborhood around one module or symbol instead of dumping the repository. |
| Input boundaries | Reads Python function parameters and annotations as lightweight inputs. |
| Output boundaries | Reads return annotations as lightweight outputs. |
| Static dependency edges | Records local `IMPORT` and conservative `CALL` edges. |
| Architecture boundaries | Maps declared paths to project-defined system boundaries. |
| Static boundary conformance | Detects forbidden cross-boundary dependencies visible in the Current MAP. |
| Future Delta | Records a small expected structural change as edges to add or remove. |
| Preflight | Checks an intended static architecture delta before completion is claimed. |
| Runtime probe | Instruments explicit Python entrypoints without requiring an LLM, daemon or container. |
| Observed MAP | Records project-internal runtime `CALL` edges for the executed trace. |
| Runtime-only edges | Surfaces observed project relationships not represented by the static dependency projection. |
| Runtime boundary conformance | Applies the same project boundary rules to observed runtime edges. |
| Runtime effects | Records selected Python-observed `FILE_WRITE`, `NETWORK_CONNECT` and `PROCESS_SPAWN` effects. |
| Claim-bound runtime assertions | Can require or forbid specific runtime edges for one execution contract. |
| Evidence binding | Runtime evidence becomes stale automatically when the source snapshot changes. |
| Build evidence | Runs Python compile validation. |
| Persistent local state | Stores Future Delta and the latest normalized runtime observation in SQLite under `.strawberry/`. |
| MCP v2 | Exposes the deterministic core through five semantic MCP operations. |
| Agent Skill | Includes a portable operating procedure for agents using StrawberryMe. |
| No built-in LLM | Core results do not require model inference. |

The Current and Observed MAPs are **technical projections**, not new canonical truth.

---

## The v0.2 operating model

```text
SOURCE IDENTITY
repo + revision + dirty state + snapshot
        │
        ▼
CURRENT MAP
static modules + symbols + dependencies
        │
        ▼
MAP CURSOR
bounded working architecture
        │
   ┌────┴────┐
   ▼         ▼
INPUTS     OUTPUTS
   │         │
   └────┬────┘
        ▼
BOUNDARIES + DEPENDENCIES
        │
        ▼
FUTURE DELTA
what should structurally change?
        │
        ▼
AGENT IMPLEMENTS
using its normal coding harness
        │
        ▼
EXECUTION CONTRACT
explicit command + optional runtime assertions
        │
        ▼
HOST / EXTERNAL SANDBOX
or local execution when explicitly chosen
        │
        ▼
OBSERVATION RECORD
runtime calls + selected effects
        │
        ▼
OBSERVED MAP
        │
   ┌────┴──────────────┐
   ▼                   ▼
STATIC vs OBSERVED   BOUNDARY RULES
   │                   │
   └─────────┬─────────┘
             ▼
            DRIFT
```

StrawberryMe therefore keeps three views separate:

```text
DECLARED
What should be allowed or intentionally changed?

STATIC
What does the source projection show?

OBSERVED
What happened in this concrete execution?
```

---

## Public MCP v2 surface

StrawberryMe deliberately keeps the agent interface small:

```text
strawberry_status()
strawberry_cursor(target, horizon=1)
strawberry_preflight(add=[], remove=[])
strawberry_observe(command, timeout_seconds=30,
                   expected_runtime_edges=[], forbidden_runtime_edges=[])
strawberry_verify(command=None, timeout_seconds=30)
```

### `strawberry_status`

Establishes source identity, static MAP health and the state of the latest runtime observation.

### `strawberry_cursor`

Opens a bounded architecture view around the target and returns relevant inputs, outputs, upstream/downstream relationships and known static boundary violations.

### `strawberry_preflight`

Records only the structural delta the change is intended to produce. StrawberryMe does not require a complete Future MAP for every local change.

### `strawberry_observe`

Executes one explicit command and produces an Observed MAP for that trace. For Python entrypoints it captures project-internal runtime calls and selected effects. Optional runtime-edge assertions keep conclusions bounded to the executed trace.

### `strawberry_verify`

Rescans the source, validates Python compilation, checks static boundaries, checks the expected Future Delta and incorporates the latest **source-bound** runtime observation when one exists.

No background agent or daemon is required.

---

## Agent Skill

StrawberryMe ships with an Agent Skill because MCP tools alone do not define **when** an agent should use them.

The normal loop is:

```text
STATUS
  establish source identity
        ↓
CURSOR
  orient on component + I/O + dependencies
        ↓
PREFLIGHT
  record intentional static delta when relevant
        ↓
IMPLEMENT
  normal coding harness
        ↓
OBSERVE
  only when runtime behavior can materially change the claim
        ↓
VERIFY
  build + static boundary + delta + bound runtime evidence
```

Runtime observation is particularly useful when a change involves dynamic imports, plugins, dependency injection, runtime dispatch or a system boundary that static analysis may not resolve completely.

The agent must treat StrawberryMe signals literally:

- `BUILD PASS` does **not** override an architecture violation;
- `STATIC PASS` does **not** imply `RUNTIME PASS`;
- `SATISFIED_ON_TRACE` applies only to the exact source snapshot and execution that produced it;
- stale runtime evidence must not be reused after source changes;
- an unresolved or ambiguous cursor must not be filled with invented architecture facts;
- runtime coverage is never silently treated as complete-system coverage;
- StrawberryMe does not decide product acceptance, deployment or governance.

The canonical skill is available at `SKILL.md`; `skill/SKILL.md` remains a compatibility copy.

---

## Example: statically clean, runtime violation

Suppose the project declares:

```text
application !→ database
```

The application loads a database module dynamically:

```python
repo = importlib.import_module("app.db.repo")
getattr(repo, "save")(order)
```

Conservative static analysis may not resolve that dependency:

```text
STATIC BOUNDARY
PASS
```

Now execute the behavior:

```bash
strawberry --root . observe -- \
  python -c "from app.application.service import handle; handle('x')"
```

The Observed MAP can contain:

```text
module:app.application.service
        │ CALL / RUNTIME
        ▼
module:app.db.repo
```

StrawberryMe then reports:

```text
STATIC BOUNDARY
PASS

RUNTIME BOUNDARY
FAIL

RUNTIME-ONLY EDGE
application → database

EVIDENCE RESULT
VIOLATED_ON_TRACE
```

That is the central v0.2 capability.

---

## Claim-bound runtime assertions

An execution can optionally state which runtime edge must or must not be observed:

```text
EXPECTED
module:app.application.service|CALL|module:app.ports.pricing

FORBIDDEN
module:app.application.service|CALL|module:app.db.repo
```

Results use bounded semantics:

```text
SATISFIED_ON_TRACE
VIOLATED_ON_TRACE
INCONCLUSIVE
```

`SATISFIED_ON_TRACE` does not mean the program is generally correct. It means the requested runtime assertions were satisfied in that concrete source-bound execution.

---

## Source-bound evidence

v0.2 adds a source snapshot fingerprint to prevent stale runtime evidence from silently surviving a code change.

```text
SOURCE SNAPSHOT S1
        │
        ▼
OBSERVATION O1
        │
        ▼
source changes → S2
        │
        ▼
O1 becomes STALE
```

`strawberry_verify()` will report stale runtime evidence as `INCONCLUSIVE` rather than reusing it as proof for the new source state.

---

## Architecture rules

StrawberryMe is **not Clean-Code police**.

Rules should represent real system boundaries that matter to the project, not universal style preferences.

```toml
[boundaries.application]
paths = ["app/application/**"]

[boundaries.database]
paths = ["app/db/**"]

[[rules]]
source = "application"
target = "database"
mode = "forbid"
severity = "HARD"
```

The same rule can now be evaluated against static edges and runtime-observed project edges.

---

## Install

Python 3.11+:

```bash
pip install -e ".[mcp]"
```

Copy the example configuration and define only the boundaries that matter:

```bash
cp strawberry.toml.example strawberry.toml
```

---

## Run as MCP v2

For local development:

```bash
export STRAWBERRY_ROOT=/path/to/repository
mcp dev src/strawberryme/server.py
```

Or over Streamable HTTP:

```bash
export STRAWBERRY_ROOT=/path/to/repository
mcp run src/strawberryme/server.py --transport streamable-http
```

For an MCP host that launches stdio servers, point the host at the same server module.

---

## CLI examples

```bash
strawberry --root . status
strawberry --root . cursor PaymentService
```

Record an expected static change:

```bash
strawberry --root . preflight \
  --remove 'module:app.application.service|IMPORT|module:app.db.repo'
```

Observe one Python execution:

```bash
strawberry --root . observe \
  --expected-runtime-edge 'module:app.application.service|CALL|module:app.ports.pricing' \
  --forbidden-runtime-edge 'module:app.application.service|CALL|module:app.db.repo' \
  -- python -m pytest tests/test_payment.py -q
```

Then verify the combined static/runtime state:

```bash
strawberry --root . verify
```

---

## Execution and sandboxing

StrawberryMe v0.2 still does **not** implement its own security sandbox.

The runtime probe instruments explicit Python commands. The intended deployment model is reuse-first:

```text
Copilot / Codex / host harness sandbox
or another trusted execution provider
        │
        ▼
StrawberryMe runtime probe
        │
        ▼
normalized Observed MAP + evidence
```

When StrawberryMe executes locally, `isolation` is reported as `NONE`.

For runtime architecture tracing, use a Python entrypoint such as:

```text
python -c ...
python -m module ...
python script.py ...
```

Non-Python commands can still execute, but v0.2 reports runtime architecture coverage as `UNINSTRUMENTED_COMMAND` instead of pretending a trace exists.

---

## What StrawberryMe does not claim

StrawberryMe v0.2.0 does not claim that:

- static analysis reconstructs complete runtime architecture;
- one runtime trace covers every execution path;
- a passing build proves correctness;
- `SATISFIED_ON_TRACE` is a formal proof;
- the Current or Observed MAP is canonical truth;
- all dependency injection, reflection, native extensions, generated code, SQL/data dependencies or external-service semantics are visible;
- one architecture style is universally correct.

Unknown information remains unknown rather than being converted into false certainty.

---

## Limits of v0.2.0

- Source MAP is Python-first.
- Runtime architecture tracing is Python-entrypoint-first.
- Static `CALL` resolution remains intentionally conservative.
- Runtime observation is trace-specific, not whole-program coverage.
- Selected effects are observational signals, not a security monitor.
- No background watcher or daemon.
- No built-in security sandbox.
- No built-in LLM.

JavaScript, PHP and C# remain future parser-adapter candidates only after the Python MAP/Cursor/Observed loop proves useful.

---

## v0.2 acceptance hypothesis

The key v0.2 question is now stronger than v0.1:

> Can StrawberryMe detect architecture drift that a fresh coding agent and conservative static analysis would otherwise miss?

A useful A/B/C evaluation should compare:

```text
A  normal coding agent
B  agent + static StrawberryMe orientation
C  agent + static orientation + Observed MAP
```

Measure at least:

- forbidden dependency introduction;
- missed dynamic dependency;
- intended-delta completion;
- false `done` claims;
- stale-evidence reuse;
- token/tool-call cost.

If Observed Architecture does not materially improve those outcomes, the runtime layer should not be expanded.

---

## License

StrawberryMe is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See [LICENSE](LICENSE).
