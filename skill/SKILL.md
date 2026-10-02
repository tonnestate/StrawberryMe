---
name: strawberryme
description: Persistent architecture orientation and observed architecture verification for software-engineering agents. Use StrawberryMe to preserve source identity, I/O boundaries, dependencies, system boundaries, intended structural deltas and bounded runtime evidence across coding work.
---

# StrawberryMe Skill

StrawberryMe is an architecture-orientation and verification interface, not a coding agent. It contains no planner, built-in LLM, autonomous task manager, deployment authority or requirement for a permanently running agent.

Use this loop when StrawberryMe is available:

1. `strawberry_status` — establish repository/source identity, Current MAP health and whether a previous runtime observation is current or stale.
2. `strawberry_cursor` — orient on the target. Read inputs, outputs, upstream/downstream dependencies and known static boundary violations. Keep the horizon bounded.
3. `strawberry_preflight` — when the change intentionally alters architecture edges, record only the expected additions/removals. Do not model a complete Future MAP for a local change.
4. Implement the code with the normal coding tool or harness.
5. `strawberry_observe` — when runtime behavior can materially change the claim, execute one explicit Python entrypoint and inspect the Observed MAP, runtime-only edges, selected side effects and runtime boundary result.
6. `strawberry_verify` — rescan, compile-check, evaluate static boundaries, compare the Future Delta and incorporate only source-bound runtime evidence before claiming completion.

Rules:

- Do not treat the model's remembered repository structure as authoritative when StrawberryMe has current source evidence.
- `BUILD PASS` does not imply `ARCHITECTURE PASS`.
- `STATIC PASS` does not imply `RUNTIME PASS`.
- A matching output does not make an unintended dependency acceptable.
- Use runtime observation when dynamic imports, plugin wiring, dependency injection, runtime dispatch or an important system boundary may not be resolved statically.
- Do not treat one runtime trace as whole-program coverage.
- Treat `SATISFIED_ON_TRACE` literally: it applies only to that source snapshot and execution.
- Never reuse runtime evidence after StrawberryMe marks it `STALE`.
- If StrawberryMe reports `AMBIGUOUS`, `NOT_FOUND`, parse errors, unknown runtime coverage or unresolved drift, do not invent missing architecture facts. Inspect or narrow the target.
- Architecture rules must represent project boundaries, not generic style preferences.
- Record only intentional structural changes in the Future Delta.
- Treat Current MAP and Observed MAP as technical projections, not canonical truth.
- StrawberryMe v0.2 is Python-first. Dynamic/native behavior outside the observed Python trace may remain unresolved.
- The runtime probe is not a security sandbox. Prefer the host harness sandbox when available.
- StrawberryMe never decides commit, deployment, product acceptance or governance authority.
- Keep the MAP Cursor bounded. Expand the horizon only when evidence requires it.

Minimal operating model:

```text
STATUS
  source identity + observation freshness
      ↓
CURSOR
  position + INPUT + OUTPUT + dependencies
      ↓
PREFLIGHT
  expected static structural delta
      ↓
IMPLEMENT
  normal coding harness
      ↓
OBSERVE
  explicit execution → Observed MAP
      ↓
VERIFY
  build + static boundary + delta + bound runtime evidence
```

The purpose of StrawberryMe is to preserve architectural orientation outside model context and to make declared, static and observed architecture disagreements visible before a coding agent claims completion.
