# StrawberryMe

<p align="center">
  <img src="docs/strawberryme-banner.png" alt="StrawberryMe — persistent architecture orientation and lightweight verification for software-engineering agents" width="100%">
</p>

<p align="center">
  <strong>Persistent architecture orientation for software-engineering agents.</strong><br>
  Know where you are. Preserve boundaries. Verify what changed.
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-experimental-orange">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0-red">
  <img alt="Python" src="https://img.shields.io/badge/python-%3E%3D3.11-3776AB">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-v2-5b5bd6">
  <img alt="Agent Skill" src="https://img.shields.io/badge/agent-skill-purple">
  <img alt="Built-in LLM" src="https://img.shields.io/badge/built--in%20LLM-none-black">
</p>

---

## What StrawberryMe is

StrawberryMe is a **persistent architecture-orientation and verification interface for coding agents**.

A coding agent can usually implement code. The harder problem over long sessions is preserving a reliable mental model of the system:

```text
Where am I?
      ↓
What comes in?
      ↓
What goes out?
      ↓
What depends on this area?
      ↓
Which system boundaries must remain intact?
      ↓
Did my implementation produce the structural change I intended?
```

StrawberryMe externalizes that orientation so it does not depend on the model remembering the whole repository correctly.

It is deliberately **not** another coding agent. StrawberryMe contains no planner, no built-in LLM, no autonomous task manager, no deployment authority and no requirement for a permanently running agent.

> **Agents reason. StrawberryMe keeps architectural orientation outside the context window.**

---

## What StrawberryMe v0.1.0 can do today

| Capability | v0.1.0 behavior |
|---|---|
| Source identity | Binds observations to Git HEAD, branch and dirty state when Git is available. |
| Current MAP | Builds a lightweight technical projection of Python modules, classes, functions and dependencies. |
| MAP Cursor | Returns a bounded neighborhood around one module or symbol instead of dumping the repository. |
| Input boundaries | Reads Python function parameters and annotations as lightweight inputs. |
| Output boundaries | Reads return annotations as lightweight outputs. |
| Dependency edges | Records local `IMPORT` edges and conservative `CALL` edges. |
| Architecture boundaries | Maps declared paths to project-defined system boundaries. |
| Boundary conformance | Detects forbidden cross-boundary dependencies without imposing a universal architecture style. |
| Future Delta | Records a small expected structural change as edges to add or remove. |
| Preflight | Checks whether the intended change conflicts with known architecture rules before completion is claimed. |
| Drift verification | Rescans after implementation and compares expected structural delta with actual structure. |
| Build evidence | Runs Python compile validation. |
| Optional command evidence | Can run one explicit local command with a timeout; this is not a security sandbox. |
| Persistent local state | Stores small map/change state in SQLite under `.strawberry/`. |
| MCP v2 | Exposes the same deterministic core through four semantic MCP operations. |
| Agent Skill | Includes a portable operating procedure for agents using StrawberryMe. |
| No built-in LLM | Core results do not require model inference. |

The Current MAP is intentionally a **technical projection**, not a new canonical source of truth.

---

## The operating model

```text
SOURCE IDENTITY
repo + revision + dirty state
        │
        ▼
CURRENT MAP
modules + symbols + dependencies
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
using its normal coding tools
        │
        ▼
RESCAN / VERIFY
        │
   ┌────┴─────────────┐
   ▼                  ▼
expected delta    actual structure
   └───────┬──────────┘
           ▼
        DRIFT
```

The important distinction is:

```text
BUILD PASS
is not the same as
ARCHITECTURE PASS
```

A change may compile and still introduce an unintended or forbidden dependency.

---

## Public MCP v2 surface

StrawberryMe deliberately exposes a small semantic interface:

```text
strawberry_status()
strawberry_cursor(target, horizon=1)
strawberry_preflight(add=[], remove=[])
strawberry_verify(command=None, timeout_seconds=30)
```

### `strawberry_status`

Establishes source identity and current MAP health.

### `strawberry_cursor`

Opens a bounded architecture view around the target and returns the relevant inputs, outputs, upstream/downstream relationships and known boundary violations.

### `strawberry_preflight`

Records only the structural delta the change is intended to produce. StrawberryMe does not require a complete Future MAP for every small change.

### `strawberry_verify`

Rescans the repository, validates Python compilation, checks declared architecture boundaries and compares the expected Future Delta with the resulting structure.

No background agent or daemon is required.

---

## Agent Skill

StrawberryMe ships with an Agent Skill because the MCP tools alone do not define **when** an agent should use them.

The Skill is intentionally small:

```text
STATUS
  establish source identity

        ↓

CURSOR
  orient on the component
  read INPUT / OUTPUT
  inspect material dependencies

        ↓

PREFLIGHT
  record only intentional structural changes

        ↓

IMPLEMENT
  use the normal coding harness

        ↓

VERIFY
  build + boundary + expected-delta check
```

The agent must treat StrawberryMe signals literally:

- a passing build does **not** override an architecture violation;
- an unresolved or ambiguous cursor must not be filled with invented architecture facts;
- the model's remembered repository structure is not authoritative;
- only intentional architecture changes belong in the Future Delta;
- StrawberryMe does not decide product acceptance, deployment or governance;
- StrawberryMe v0.1 is Python-first and intentionally conservative where static analysis is incomplete.

The canonical skill is available at:

```text
SKILL.md
```

A compatibility copy is also kept at:

```text
skill/SKILL.md
```

The Skill and MCP server call the same deterministic StrawberryMe core.

---

## Example: architecture violation despite working code

Project rule:

```text
application !→ database
```

Expected change:

```text
REMOVE
OrderService → PricingService

ADD
OrderService → PricingPort
PricingAdapter → PricingPort
```

The implementation compiles and tests pass, but the resulting MAP contains:

```text
OrderService → PricingPort
OrderService → Database
PricingAdapter → PricingPort
```

StrawberryMe can therefore report:

```text
BUILD
PASS

EXPECTED DELTA
PARTIAL

ARCHITECTURE
FAIL

UNPLANNED / FORBIDDEN EDGE
application → database

DRIFT
FOUND
```

This is the gap StrawberryMe is designed to make visible.

---

## Architecture rules

StrawberryMe is **not Clean-Code police**.

Rules should represent real system boundaries that matter to the project, not universal style preferences.

Example:

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

The agent remains free to choose patterns, functions, classes and implementation details inside those boundaries.

---

## Install

Python 3.11+:

```bash
pip install -e ".[mcp]"
```

Copy the example configuration:

```bash
cp strawberry.toml.example strawberry.toml
```

Then define only the boundaries that matter for the target repository.

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

For an MCP host that launches stdio servers, point the host at the StrawberryMe server module.

---

## CLI smoke test

```bash
strawberry --root /path/to/repo status
strawberry --root /path/to/repo cursor PaymentService
```

An architecture edge is represented as:

```text
source|KIND|target
```

Example:

```text
module:app.application.service|IMPORT|module:app.db.repo
```

Record an expected structural change:

```bash
strawberry --root . preflight \
  --remove 'module:app.application.service|IMPORT|module:app.db.repo'
```

After implementation:

```bash
strawberry --root . verify
```

---

## Execution and sandboxing

v0.1.0 does **not** implement its own security sandbox.

`strawberry_verify(command=...)` uses a local subprocess with a timeout and reports its isolation as `NONE`.

The intended model is reuse-first:

```text
host harness sandbox
Copilot / Codex / other runner
        │
        ▼
StrawberryMe execution evidence
```

A future execution-provider adapter may bind to an existing sandbox. StrawberryMe's own responsibility is source identity, architecture orientation, conformance and lightweight evidence binding—not container technology.

---

## What StrawberryMe does not claim

StrawberryMe v0.1.0 does not claim that:

- static analysis reconstructs the complete runtime architecture;
- a passing build proves correctness;
- the Current MAP is canonical truth;
- Python annotations fully describe API contracts;
- all dependency injection, reflection, generated code, SQL/data dependencies or runtime-only edges are visible;
- one architecture style is universally correct.

Unknown information should remain unknown rather than being silently invented.

---

## Limits of v0.1.0

- Python only.
- Static `CALL` resolution is intentionally conservative.
- Dynamic imports and runtime-only dependencies may be missed.
- I/O boundaries are currently derived from Python function annotations.
- No background watcher or daemon.
- No built-in security sandbox.
- No built-in LLM.

JavaScript, PHP and C# should be added through parser adapters only after the Python MAP/Cursor/Drift loop proves useful.

---

## v0.1 acceptance hypothesis

StrawberryMe is useful only if it makes a context-limited or context-reset coding agent materially better at preserving system orientation.

The first evaluation should test whether a fresh agent can:

- orient on a target through `strawberry_cursor`;
- identify relevant inputs, outputs and dependencies without broad repository archaeology;
- avoid a declared forbidden system boundary;
- implement a known Future Delta;
- detect when actual structure differs from intended structure.

If StrawberryMe does not improve those outcomes over ordinary repository search/context, the project should not be expanded.

---

## License

StrawberryMe is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See [LICENSE](LICENSE).
