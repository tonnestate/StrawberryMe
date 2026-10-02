---
name: strawberryme
description: Use StrawberryMe before and after non-trivial code changes to preserve system orientation, I/O boundaries, dependencies and architecture constraints.
---

# StrawberryMe

Use StrawberryMe as an external architecture-orientation layer. Do not treat the model's remembered repository structure as authoritative.

For an existing codebase:

1. Call `strawberry_status` once to establish source identity and map health.
2. Before changing a material component, call `strawberry_cursor` on the target. Read its inputs, outputs, upstream/downstream dependencies and boundary violations.
3. If the change intentionally adds or removes architectural edges, record only those expected edges with `strawberry_preflight`.
4. Implement the change with the normal coding tool/harness.
5. Call `strawberry_verify` before claiming completion. A passing build does not override a boundary violation or failed expected delta.
6. If StrawberryMe reports `AMBIGUOUS`, `NOT_FOUND`, parse errors, or unresolved drift, do not invent missing architecture facts. Inspect or narrow the target.

StrawberryMe v0.1 is Python-first. Its optional execution command is not a security sandbox; prefer the host harness sandbox when available.
