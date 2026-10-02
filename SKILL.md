---
name: strawberryme
description: Persistent architecture orientation for software-engineering agents. Use StrawberryMe before and after non-trivial code changes to preserve source identity, I/O boundaries, dependencies, system boundaries and intended structural deltas.
---

# StrawberryMe Skill

StrawberryMe is an architecture-orientation interface, not a coding agent. It contains no planner, built-in LLM, autonomous task manager, deployment authority or requirement for a permanently running agent.

Use exactly this loop when StrawberryMe is available:

1. `strawberry_status` — establish repository/source identity and Current MAP health before relying on stored orientation.
2. `strawberry_cursor` — orient on the target. Read inputs, outputs, upstream/downstream dependencies and known boundary violations. Keep the horizon bounded.
3. `strawberry_preflight` — when the change intentionally alters architecture edges, record only the expected additions/removals. Do not model a whole Future MAP for a local change.
4. Implement the code with the normal coding tool or harness.
5. `strawberry_verify` — rescan, compile-check, evaluate architecture boundaries and compare the expected delta with the resulting structure before claiming completion.

Rules:

- Do not treat the model's remembered repository structure as authoritative when StrawberryMe has current source evidence.
- A passing build does not override an architecture violation.
- A matching output does not make an unintended dependency acceptable.
- If StrawberryMe reports `AMBIGUOUS`, `NOT_FOUND`, parse errors, unknown boundaries or unresolved drift, do not invent missing architecture facts. Inspect or narrow the target.
- Architecture rules must represent project boundaries, not generic style preferences.
- Record only intentional structural changes in the Future Delta.
- Treat the Current MAP as a technical projection, not canonical truth.
- StrawberryMe v0.1 is Python-first. Dynamic imports, dependency injection, reflection, generated code and runtime-only dependencies may remain unresolved.
- The optional local execution command is not a security sandbox. Prefer the host harness sandbox when available.
- StrawberryMe never decides commit, deployment, product acceptance or governance authority.
- Keep the MAP Cursor bounded. Expand the horizon only when the current dependency evidence requires it.

Minimal operating model:

```text
STATUS
  source identity
      ↓
CURSOR
  position + INPUT + OUTPUT + dependencies
      ↓
PREFLIGHT
  expected structural delta
      ↓
IMPLEMENT
  normal coding harness
      ↓
VERIFY
  build + boundary + delta/drift
```

Interpret the result conservatively:

```text
BUILD PASS
does not imply
ARCHITECTURE PASS
```

The purpose of StrawberryMe is to preserve architectural orientation outside the model context so that context loss does not silently become dependency or boundary drift.
