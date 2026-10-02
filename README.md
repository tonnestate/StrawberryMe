# StrawberryMe

<p align="center">
  <img src="docs/strawberryme-banner.png" alt="StrawberryMe — persistent architecture orientation and lightweight verification for software-engineering agents" width="100%">
</p>

> **v0.1.0 — experimental**

**Persistent architecture orientation and lightweight verification for software-engineering agents.**

StrawberryMe is a small MCP-oriented connector that keeps a coding agent anchored to the system it is changing. It focuses on four questions:

1. Where am I in the system?
2. What comes in and what goes out?
3. What depends on this area and which system boundaries apply?
4. Did the implementation preserve the expected architecture delta?

It is intentionally not a coding agent, project manager, container runtime, or replacement for the host harness sandbox.

## v0.1 architecture

```text
AGENT / HARNESS
      │
      ▼
StrawberryMe MCP v2
      │
      ▼
Strawberry Core
      ├─ Source Identity
      ├─ Current MAP (Python AST)
      ├─ MAP Cursor
      ├─ I/O Boundaries
      ├─ Architecture Rules
      ├─ Future Delta
      └─ Verify / Drift
      │
      ▼
SQLite state (.strawberry/strawberry.db)
```

The MCP adapter uses the official MCP Python SDK v2 (`MCPServer`). The core has no MCP dependency and is directly testable.

## What v0.1 does

- binds results to repository/source identity (Git HEAD, branch, dirty state when Git is available);
- scans Python modules/functions/classes with the standard AST;
- exposes function input and output annotations as lightweight I/O boundaries;
- builds local `IMPORT` and conservative `CALL` edges;
- assigns files to declared architecture boundaries;
- detects forbidden cross-boundary dependencies;
- gives the agent a bounded MAP cursor around one symbol/module;
- records a small expected Future MAP delta (`add` / `remove` edges);
- rescans after mutation and checks whether that delta occurred;
- runs Python compile validation;
- can optionally execute one local command with timeout (not a security sandbox).

## Public MCP surface

```text
strawberry_status()
strawberry_cursor(target, horizon=1)
strawberry_preflight(add=[], remove=[])
strawberry_verify(command=None, timeout_seconds=30)
```

No background agent or daemon is required.

## Install

Python 3.11+:

```bash
pip install -e ".[mcp]"
```

Copy `strawberry.toml.example` to `strawberry.toml` and adapt only the boundaries that matter for your project.

## Run as MCP v2

The current official Python SDK v2 uses `MCPServer`. For local development:

```bash
export STRAWBERRY_ROOT=/path/to/repository
mcp dev src/strawberryme/server.py
```

Or run over Streamable HTTP:

```bash
export STRAWBERRY_ROOT=/path/to/repository
mcp run src/strawberryme/server.py --transport streamable-http
```

For an MCP host that launches stdio servers, point it at the same server module using the host's MCP configuration.

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

A planned refactor can be recorded as:

```bash
strawberry --root . preflight \
  --remove 'module:app.application.service|IMPORT|module:app.db.repo'
```

After the implementation:

```bash
strawberry --root . verify
```

## Architecture rules

StrawberryMe is not a Clean-Code police system. Rules should express real system boundaries only.

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

A build can therefore pass while StrawberryMe still reports an architecture violation. That distinction is intentional.

## Execution and sandboxing

v0.1 does **not** implement a security sandbox. `strawberry_verify(command=...)` uses a local subprocess with a timeout and labels its isolation as `NONE`.

The intended design is to reuse a sandbox already provided by the agent harness (Copilot/Codex/etc.) or add an execution-provider adapter later. StrawberryMe's own responsibility is source identity, orientation, architecture conformance and evidence binding—not container technology.

## Limits of v0.1

- Python only.
- Static `CALL` resolution is intentionally conservative.
- Dynamic imports, dependency injection, reflection, generated code, SQL/data dependencies and runtime-only edges may be missed.
- I/O boundaries are currently derived from Python function annotations; they are not API-schema inference.
- Current MAP is a technical projection, not canonical truth.
- No claim of general correctness is made from a successful build or command.

These limits are surfaced rather than hidden. JavaScript, PHP and C# should be added through parser adapters only after the Python MAP/Cursor/Drift loop proves useful.

## v0.1 acceptance test

The hypothesis is useful only if StrawberryMe can make a context-free agent safer and faster. The first evaluation should test whether a fresh agent can:

- orient on a target through `strawberry_cursor`;
- identify relevant I/O and dependencies without broad repository archaeology;
- avoid a declared forbidden boundary;
- implement a known Future Delta;
- detect when the actual structure differs from the intended delta.

If it cannot outperform ordinary search/context on these tasks, the project should not be expanded.
