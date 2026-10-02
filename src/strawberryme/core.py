from __future__ import annotations

import fnmatch
import hashlib
import json
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from . import __version__
from .config import Config, load_config
from .models import ArchitectureMap, Delta, Edge, ExecutionEnvelope, Node, ProbeCase, ProbePlan, RuntimeObservation
from .provider import ProviderRegistry
from .scanner import scan_python
from .store import Store


class StrawberryCore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(self.root)
        self.config: Config = load_config(self.root)
        self.store = Store(self.root)
        self.providers = ProviderRegistry()

    def map(self) -> ArchitectureMap:
        self.config = load_config(self.root)
        return scan_python(self.root, self.config, self.store)

    def status(self) -> dict[str, Any]:
        architecture = self.map()
        delta = self.store.get_delta()
        violations = self._boundary_violations(architecture)
        observation = self.store.get_runtime_observation()
        latest_plan = self.store.get_latest_probe_plan()
        runtime_state: dict[str, Any] = {
            "probe": "PYTHON_PROFILE_AUDIT_BOOTSTRAP",
            "isolation": "NONE",
            "sandbox_provider": "HOST_OR_EXTERNAL",
            "latest_observation": None,
        }
        if observation is not None:
            runtime_state["latest_observation"] = {
                "run_id": observation.run_id,
                "status": observation.status,
                "coverage": observation.coverage,
                "source_binding": "CURRENT" if self._observation_current(observation, architecture) else "STALE",
                "edges": len(observation.edges),
                "effects": len(observation.effects),
            }
        return {
            "strawberryme": __version__,
            "root": str(self.root),
            "source": architecture.source.to_dict(),
            "language_support": {"python": "ACTIVE", "javascript": "PLANNED", "php": "PLANNED", "csharp": "PLANNED"},
            "map": {"nodes": len(architecture.nodes), "edges": len(architecture.edges), "parse_errors": len(architecture.parse_errors), **architecture.scan_stats},
            "architecture": {
                "mode": "CONFORMANCE" if self._conformance_state(architecture) == "CONFIGURED" else "ORIENTATION_ONLY",
                "conformance": self._conformance_state(architecture),
                "declared_boundaries": len(self.config.boundary_patterns),
                "rules": len(architecture.rules),
                "violations": len(violations),
            },
            "future_delta": delta.to_dict() if delta else None,
            "runtime": runtime_state,
            "execution_providers": self.providers.capabilities(),
            "adaptive": {
                "latest_probe_plan": (latest_plan.to_dict() if latest_plan else None),
                "principle": "start small; follow evidence; expand only unresolved branches",
            },
        }

    def cursor(self, target: str, horizon: int = 1, adaptive: bool = False) -> dict[str, Any]:
        architecture = self.map()
        matches = self._find_nodes(architecture, target)
        if not matches:
            return {"status": "NOT_FOUND", "target": target, "candidates": []}
        if len(matches) > 1:
            return {"status": "AMBIGUOUS", "target": target, "candidates": [n.to_dict() for n in matches[:20]]}
        focus = matches[0]
        requested_horizon = horizon
        expansion_basis: list[str] = []
        if adaptive:
            assessment = self.assess_change(paths=[focus.path], target=target)
            horizon = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}[assessment["risk"]]
            expansion_basis = list(assessment["reasons"])
        by_id = {n.id: n for n in architecture.nodes}
        adjacency: dict[str, set[str]] = {}
        reverse: dict[str, set[str]] = {}
        for edge in architecture.edges:
            adjacency.setdefault(edge.source, set()).add(edge.target)
            reverse.setdefault(edge.target, set()).add(edge.source)
        seen = {focus.id}
        q: deque[tuple[str, int]] = deque([(focus.id, 0)])
        while q:
            current, depth = q.popleft()
            if depth >= max(0, horizon):
                continue
            for neighbor in adjacency.get(current, set()) | reverse.get(current, set()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    q.append((neighbor, depth + 1))
        relevant_edges = [e for e in architecture.edges if e.source in seen or e.target in seen]
        upstream = sorted({e.source for e in relevant_edges if e.target == focus.id})
        downstream = sorted({e.target for e in relevant_edges if e.source == focus.id})
        return {
            "status": "OK",
            "source": architecture.source.to_dict(),
            "position": focus.to_dict(),
            "inputs": list(focus.inputs),
            "outputs": list(focus.outputs),
            "boundary": focus.boundary,
            "upstream": [by_id[x].to_dict() if x in by_id else {"id": x} for x in upstream],
            "downstream": [by_id[x].to_dict() if x in by_id else {"id": x} for x in downstream],
            "horizon": horizon,
            "requested_horizon": requested_horizon,
            "adaptive": adaptive,
            "expansion_basis": expansion_basis,
            "nodes": [by_id[x].to_dict() for x in sorted(seen) if x in by_id],
            "edges": [e.to_dict() for e in relevant_edges],
            "conformance": self._conformance_state(architecture),
            "violations": [v for v in self._boundary_violations(architecture) if v["source_node"] in seen or v["target_node"] in seen],
        }

    def preflight(self, add: list[str] | None = None, remove: list[str] | None = None) -> dict[str, Any]:
        architecture = self.map()
        delta = Delta(tuple(sorted(set(add or []))), tuple(sorted(set(remove or []))))
        self.store.set_delta(delta)
        current = {e.key for e in architecture.edges}
        malformed = [item for item in [*delta.add, *delta.remove] if len(item.split("|")) != 3]
        if malformed:
            return {
                "status": "INVALID",
                "source": architecture.source.to_dict(),
                "conformance": self._conformance_state(architecture),
                "expected_delta": delta.to_dict(),
                "malformed_edges": malformed,
                "architecture_violations": self._boundary_violations(architecture),
                "edge_format": "source|KIND|target, e.g. module:app.service|IMPORT|module:app.db",
            }
        candidate = (current | set(delta.add)) - set(delta.remove)
        candidate_edges = [self._edge_from_key(k) for k in candidate]
        candidate_map = ArchitectureMap(architecture.source, architecture.nodes, candidate_edges, architecture.rules, architecture.parse_errors)
        violations = self._boundary_violations(candidate_map)
        missing_remove = sorted(set(delta.remove) - current)
        already_present_add = sorted(set(delta.add) & current)
        return {
            "status": "VIOLATION" if any(v["severity"] == "HARD" for v in violations) else "READY",
            "source": architecture.source.to_dict(),
            "conformance": self._conformance_state(architecture),
            "expected_delta": delta.to_dict(),
            "malformed_edges": [],
            "remove_not_present": missing_remove,
            "add_already_present": already_present_add,
            "architecture_violations": violations,
            "edge_format": "source|KIND|target, e.g. module:app.service|IMPORT|module:app.db",
        }

    def observe(
        self,
        command: list[str],
        timeout_seconds: int = 30,
        expected_runtime_edges: list[str] | None = None,
        forbidden_runtime_edges: list[str] | None = None,
        envelope: ExecutionEnvelope | None = None,
    ) -> dict[str, Any]:
        architecture = self.map()
        expected = tuple(sorted(set(expected_runtime_edges or [])))
        forbidden = tuple(sorted(set(forbidden_runtime_edges or [])))
        malformed = [item for item in [*expected, *forbidden] if len(item.split("|")) != 3]
        if malformed:
            return {
                "status": "INVALID",
                "malformed_edges": malformed,
                "edge_format": "source|CALL|target, e.g. module:app.service|CALL|module:app.db",
            }
        effective_envelope = envelope or ExecutionEnvelope(source_snapshot=architecture.source.snapshot_id or "", allowed_executables=(Path(command[0]).name.lower(),))
        provider = self.providers.get(effective_envelope.provider_id)
        if provider is None:
            return {"status": "PROVIDER_NOT_FOUND", "provider_id": effective_envelope.provider_id}
        capability_errors = provider.validate(effective_envelope, command)
        if capability_errors:
            return {"status": "PROVIDER_CAPABILITY_INSUFFICIENT", "errors": capability_errors, "provider": provider.capabilities.to_dict()}
        observation = provider.execute(self.root, architecture.source, command, timeout_seconds, effective_envelope)
        self.store.set_runtime_observation(observation)
        self.store.set_json(
            "runtime_contract",
            {"expected_runtime_edges": list(expected), "forbidden_runtime_edges": list(forbidden)},
        )
        return self._runtime_result(architecture, observation, expected, forbidden)

    def assess_change(self, paths: list[str] | None = None, target: str | None = None) -> dict[str, Any]:
        architecture = self.map()
        selected = sorted(set(paths or architecture.source.dirty_files))
        selected_norm = {p.replace("\\", "/") for p in selected}
        reasons: list[str] = []
        boundaries: set[str] = set()
        code_paths = [p for p in selected_norm if p.endswith(".py")]
        dynamic_hits = [signal for signal in architecture.dynamic_signals if signal.get("path") in selected_norm]

        for rel in code_paths:
            boundary = self.config.boundary_for(rel)
            if boundary:
                boundaries.add(boundary)
        if not selected:
            reasons.append("NO_CHANGE_SCOPE")
        if selected and not code_paths:
            reasons.append("NON_CODE_ONLY")
        if boundaries:
            reasons.append("ARCHITECTURE_BOUNDARY_TOUCHED")
        if dynamic_hits:
            reasons.append("DYNAMIC_BEHAVIOR_SIGNAL")
        if architecture.parse_errors:
            reasons.append("STATIC_MAP_INCOMPLETE")
        delta = self.store.get_delta()
        if delta and (delta.add or delta.remove):
            reasons.append("EXPECTED_DELTA_ACTIVE")
        latest = self.store.get_runtime_observation()
        if latest and self._observation_current(latest, architecture):
            static_pairs = self._static_module_pairs(architecture)
            if any((edge.source, edge.target) not in static_pairs for edge in latest.edges):
                reasons.append("RUNTIME_ONLY_EDGE_PREVIOUSLY_OBSERVED")
        if any(r in reasons for r in ("DYNAMIC_BEHAVIOR_SIGNAL", "STATIC_MAP_INCOMPLETE", "RUNTIME_ONLY_EDGE_PREVIOUSLY_OBSERVED")):
            risk = "HIGH"
        elif any(r in reasons for r in ("ARCHITECTURE_BOUNDARY_TOUCHED", "EXPECTED_DELTA_ACTIVE")):
            risk = "MEDIUM"
        else:
            risk = "LOW"
        return {
            "status": "OK", "source": architecture.source.to_dict(), "target": target, "paths": selected,
            "conformance": self._conformance_state(architecture),
            "risk": risk, "reasons": sorted(set(reasons)), "dynamic_signals": dynamic_hits,
            "boundaries": sorted(boundaries),
            "recommended_path": {"LOW": "STATIC_ONLY", "MEDIUM": "CURSOR_THEN_VERIFY", "HIGH": "MINIMAL_RUNTIME_PROBE"}[risk],
            "recommended_horizon": {"LOW": 0, "MEDIUM": 1, "HIGH": 2}[risk],
        }

    def probe_plan(
        self,
        command: list[str],
        target: str | None = None,
        paths: list[str] | None = None,
        expected_runtime_edges: list[str] | None = None,
        forbidden_runtime_edges: list[str] | None = None,
        filesystem: str = "TEMP_WRITE",
        network: str = "DENY",
        process_spawn: str = "DENY",
        required_enforcement: str = "PYTHON_AUDIT",
        provider_id: str = "local-python",
        allowed_env_names: list[str] | None = None,
        max_cases: int = 3,
        max_repeats: int = 3,
        max_runtime_seconds: int = 60,
    ) -> dict[str, Any]:
        if not command:
            return {"status": "INVALID", "reason": "command must not be empty"}
        architecture = self.map()
        assessment = self.assess_change(paths=paths, target=target)
        executable = Path(command[0]).name.lower()
        envelope = ExecutionEnvelope(
            source_snapshot=architecture.source.snapshot_id or "",
            provider_id=provider_id,
            required_enforcement=required_enforcement,  # type: ignore[arg-type]
            allowed_executables=(executable,),
            filesystem=filesystem,  # type: ignore[arg-type]
            network=network,  # type: ignore[arg-type]
            process_spawn=process_spawn,  # type: ignore[arg-type]
            allowed_env_names=tuple(sorted(set(allowed_env_names or []))),
            max_cases=max(1, min(int(max_cases), 20)),
            max_repeats=max(1, min(int(max_repeats), 20)),
            max_runtime_seconds=max(1, min(int(max_runtime_seconds), 600)),
        )
        errors = self._validate_envelope(envelope)
        if errors:
            return {"status": "INVALID", "errors": errors, "envelope": envelope.to_dict()}

        provider = self.providers.get(envelope.provider_id)
        if provider is None:
            return {"status": "PROVIDER_NOT_FOUND", "provider_id": envelope.provider_id}
        provider_errors = provider.validate(envelope, command)
        if provider_errors:
            return {"status": "PROVIDER_CAPABILITY_INSUFFICIENT", "errors": provider_errors, "provider": provider.capabilities.to_dict(), "envelope": envelope.to_dict()}

        expected = tuple(sorted(set(expected_runtime_edges or [])))
        forbidden = tuple(sorted(set(forbidden_runtime_edges or [])))
        malformed = [item for item in [*expected, *forbidden] if len(item.split("|")) != 3]
        if malformed:
            return {"status": "INVALID", "malformed_edges": malformed}

        risk = assessment["risk"]
        repeats = 1
        mode = "SINGLE_SHOT"
        if risk == "HIGH" and envelope.max_repeats >= 2:
            repeats = min(2, envelope.max_repeats)
            mode = "REPEAT_N"
        case = ProbeCase(
            case_id="P1",
            scenario="minimal runtime probe",
            command=tuple(command),
            mode=mode,  # type: ignore[arg-type]
            repeats=repeats,
            expected_runtime_edges=expected,
            forbidden_runtime_edges=forbidden,
        )
        privileged = (
            envelope.network == "ALLOW"
            or envelope.process_spawn == "ALLOW"
            or envelope.filesystem == "PROJECT_WRITE"
            or bool(envelope.allowed_env_names)
        )
        approval_reason = None
        if privileged:
            approval_reason = "Execution envelope grants network, process, project-write, or named-environment capability."
        plan = ProbePlan(
            plan_id=uuid.uuid4().hex[:16],
            source=architecture.source,
            risk=risk,
            reasons=tuple(assessment["reasons"]),
            target=target,
            cases=(case,),
            envelope=envelope,
            approval_required=privileged,
            approval_reason=approval_reason,
        )
        self.store.set_probe_plan(plan)
        return {
            "status": "APPROVAL_REQUIRED" if privileged else "READY",
            "plan": plan.to_dict(),
            "assessment": assessment,
            "execution_policy": "The plan is frozen to this source snapshot. Expansion outside the envelope requires a new plan.",
        }

    def approve_probe_plan(self, plan_id: str, approved_by: str = "local-user") -> dict[str, Any]:
        plan = self.store.get_probe_plan(plan_id)
        if plan is None:
            return {"status": "NOT_FOUND", "plan_id": plan_id}
        architecture = self.map()
        if plan.envelope.source_snapshot != (architecture.source.snapshot_id or ""):
            return {"status": "STALE", "plan_id": plan_id, "reason": "source snapshot changed"}
        self.store.approve_probe_plan(plan_id, approved_by)
        return {
            "status": "APPROVED",
            "plan_id": plan_id,
            "approved_by": approved_by,
            "note": "Approval is a local policy signal, not cryptographic proof of human identity.",
        }

    def probe_run(self, plan_id: str) -> dict[str, Any]:
        plan = self.store.get_probe_plan(plan_id)
        if plan is None:
            return {"status": "NOT_FOUND", "plan_id": plan_id}
        architecture = self.map()
        current_snapshot = architecture.source.snapshot_id or ""
        if current_snapshot != plan.envelope.source_snapshot:
            return {
                "status": "STALE_PLAN",
                "plan_id": plan_id,
                "planned_snapshot": plan.envelope.source_snapshot,
                "current_snapshot": current_snapshot,
            }
        if plan.approval_required and not self.store.get_probe_approval(plan_id):
            return {
                "status": "APPROVAL_REQUIRED",
                "plan_id": plan_id,
                "reason": plan.approval_reason,
                "envelope": plan.envelope.to_dict(),
            }

        results: list[dict[str, Any]] = []
        executed = 0
        for case in plan.cases[: plan.envelope.max_cases]:
            executable = Path(case.command[0]).name.lower() if case.command else ""
            if executable not in {x.lower() for x in plan.envelope.allowed_executables}:
                return {"status": "ENVELOPE_EXCEEDED", "reason": f"executable {executable!r} not allowed"}
            repeats = min(max(case.repeats, 1), plan.envelope.max_repeats)
            for attempt in range(repeats):
                provider = self.providers.get(plan.envelope.provider_id)
                if provider is None:
                    return {"status": "PROVIDER_NOT_FOUND", "provider_id": plan.envelope.provider_id}
                capability_errors = provider.validate(plan.envelope, list(case.command))
                if capability_errors:
                    return {"status": "PROVIDER_CAPABILITY_INSUFFICIENT", "errors": capability_errors, "provider": provider.capabilities.to_dict()}
                observation = provider.execute(
                    self.root, architecture.source, list(case.command),
                    min(plan.envelope.max_runtime_seconds, 300), plan.envelope,
                )
                self.store.set_runtime_observation(observation)
                self.store.set_json(
                    "runtime_contract",
                    {
                        "expected_runtime_edges": list(case.expected_runtime_edges),
                        "forbidden_runtime_edges": list(case.forbidden_runtime_edges),
                    },
                )
                normalized = self._runtime_result(
                    architecture,
                    observation,
                    case.expected_runtime_edges,
                    case.forbidden_runtime_edges,
                )
                normalized["case_id"] = case.case_id
                normalized["attempt"] = attempt + 1
                results.append(normalized)
                executed += 1
                if observation.envelope_breaches or normalized["evidence_result"] == "VIOLATED_ON_TRACE":
                    break
            if results and results[-1]["evidence_result"] in {"ENVELOPE_EXCEEDED", "VIOLATED_ON_TRACE"}:
                break

        adaptive = self._adaptive_next_action(architecture, results, plan)
        return {
            "status": "COMPLETE" if results else "NO_CASES",
            "plan_id": plan_id,
            "executed_runs": executed,
            "results": results,
            "adaptive": adaptive,
            "envelope": plan.envelope.to_dict(),
        }

    def _validate_envelope(self, envelope: ExecutionEnvelope) -> list[str]:
        errors: list[str] = []
        if envelope.filesystem not in {"READ_ONLY", "TEMP_WRITE", "PROJECT_WRITE"}:
            errors.append("filesystem must be READ_ONLY, TEMP_WRITE, or PROJECT_WRITE")
        if envelope.network not in {"DENY", "ALLOW"}:
            errors.append("network must be DENY or ALLOW")
        if envelope.process_spawn not in {"DENY", "ALLOW"}:
            errors.append("process_spawn must be DENY or ALLOW")
        if envelope.required_enforcement not in {"NONE", "PYTHON_AUDIT", "HOST_MANAGED", "OS_ISOLATED"}:
            errors.append("required_enforcement is invalid")
        if not envelope.allowed_executables:
            errors.append("at least one executable must be allowed")
        if envelope.max_cases < 1 or envelope.max_repeats < 1 or envelope.max_runtime_seconds < 1:
            errors.append("case, repeat, and runtime limits must be positive")
        return errors

    def _adaptive_next_action(
        self,
        architecture: ArchitectureMap,
        results: list[dict[str, Any]],
        plan: ProbePlan,
    ) -> dict[str, Any]:
        if not results:
            return {"evidence_sufficient": False, "next": "NO_EVIDENCE"}
        last = results[-1]
        if last.get("evidence_result") == "ENVELOPE_EXCEEDED":
            return {
                "evidence_sufficient": False,
                "next": "NEW_PLAN_REQUIRED",
                "reason": "Observed behavior exceeded the approved execution envelope.",
            }
        if last.get("evidence_result") == "VIOLATED_ON_TRACE":
            return {
                "evidence_sufficient": True,
                "next": "VERIFY_AND_REPORT",
                "reason": "A concrete architecture/runtime violation was observed; broader probing is unnecessary to establish this finding.",
            }
        runtime_only = last.get("observed_map", {}).get("runtime_only_edges", [])
        if runtime_only:
            targets = sorted({edge.get("target") for edge in runtime_only if isinstance(edge, dict) and edge.get("target")})
            return {
                "evidence_sufficient": False,
                "next": "EXPAND_UNCERTAIN_BRANCH",
                "targets": targets[:5],
                "reason": "Runtime-only relationships remain unexplained; expand only those branches.",
            }
        coverage = last.get("observed_map", {}).get("coverage")
        if coverage != "OBSERVED":
            return {
                "evidence_sufficient": False,
                "next": "REFINE_PROBE",
                "reason": f"Runtime coverage is {coverage}; do not broaden unrelated areas.",
            }
        return {
            "evidence_sufficient": True,
            "next": "VERIFY",
            "reason": "No unresolved runtime-only branch or envelope breach was observed in the planned cases.",
        }

    def evidence_history(self, limit: int = 10) -> dict[str, Any]:
        observations = self.store.evidence_history(limit)
        items = [obs.to_dict() for obs in observations]
        runtime_diff: dict[str, Any] | None = None
        if len(observations) >= 2:
            current, previous = observations[0], observations[1]
            current_edges = {e.key for e in current.edges}
            previous_edges = {e.key for e in previous.edges}
            current_effects = {(e.actor, e.kind, e.target) for e in current.effects}
            previous_effects = {(e.actor, e.kind, e.target) for e in previous.effects}
            runtime_diff = {
                "from_run": previous.run_id, "to_run": current.run_id,
                "added_edges": sorted(current_edges - previous_edges),
                "removed_edges": sorted(previous_edges - current_edges),
                "added_effects": sorted([list(x) for x in current_effects - previous_effects]),
                "removed_effects": sorted([list(x) for x in previous_effects - current_effects]),
            }
        verifications = self.store.verification_history(limit)
        architecture_diff: dict[str, Any] | None = None
        if len(verifications) >= 2:
            current, previous = verifications[0], verifications[1]
            current_edges = set(current.get("static_edges", []))
            previous_edges = set(previous.get("static_edges", []))
            current_violations = set(current.get("violations", []))
            previous_violations = set(previous.get("violations", []))
            architecture_diff = {
                "from_snapshot": previous.get("source_snapshot"),
                "to_snapshot": current.get("source_snapshot"),
                "added_static_edges": sorted(current_edges - previous_edges),
                "removed_static_edges": sorted(previous_edges - current_edges),
                "new_violations": sorted(current_violations - previous_violations),
                "resolved_violations": sorted(previous_violations - current_violations),
            }
        return {
            "status": "OK",
            "runtime_observations": {"count": len(items), "latest_diff": runtime_diff, "items": items},
            "verifications": {"count": len(verifications), "latest_architecture_diff": architecture_diff, "items": verifications},
        }

    def verify(self, command: list[str] | None = None, timeout_seconds: int = 30) -> dict[str, Any]:
        architecture = self.map()
        if command:
            self.observe(command, timeout_seconds)
            architecture = self.map()

        delta = self.store.get_delta()
        actual = {e.key for e in architecture.edges}
        expected_result: dict[str, Any]
        if delta is None:
            expected_result = {"status": "NOT_CHECKED", "reason": "No future delta recorded."}
        else:
            missing_add = sorted(set(delta.add) - actual)
            still_present = sorted(set(delta.remove) & actual)
            expected_result = {
                "status": "PASS" if not missing_add and not still_present else "FAIL",
                "missing_expected_additions": missing_add,
                "still_present_expected_removals": still_present,
            }

        build = self._compile_check()
        conformance = self._conformance_state(architecture)
        violations = self._boundary_violations(architecture)
        hard = [v for v in violations if v["severity"] == "HARD"]
        runtime = self._latest_runtime_result(architecture)
        runtime_failed = runtime.get("evidence_result") == "VIOLATED_ON_TRACE"
        runtime_stale = runtime.get("status") == "STALE"
        drift_found = bool(hard or expected_result.get("status") == "FAIL" or runtime_failed)
        boundary_status = "NOT_EVALUATED" if conformance != "CONFIGURED" else ("FAIL" if hard else "PASS")
        drift_unknown = runtime_stale or conformance != "CONFIGURED"
        result = {
            "source": architecture.source.to_dict(),
            "build": build,
            "boundary": {"status": boundary_status, "conformance": conformance, "violations": violations},
            "expected_delta": expected_result,
            "runtime": runtime,
            "drift": "FOUND" if drift_found else ("UNKNOWN" if drift_unknown else "NONE"),
            "truth_model": {
                "declared": "architecture rules + expected delta",
                "static": "Python AST Current MAP",
                "observed": "latest bound runtime trace when available",
            },
        }
        self.store.append_verification({
            "source_snapshot": architecture.source.snapshot_id,
            "git_head": architecture.source.git_head,
            "static_edges": sorted(e.key for e in architecture.edges),
            "violations": sorted(v.get("edge", "") for v in violations if v.get("edge")),
            "boundary_status": result["boundary"]["status"],
            "expected_delta_status": expected_result.get("status"),
            "runtime_run_id": runtime.get("execution", {}).get("run_id") if isinstance(runtime, dict) else None,
            "runtime_evidence_result": runtime.get("evidence_result") if isinstance(runtime, dict) else None,
            "drift": result["drift"],
        })
        return result

    def _runtime_result(
        self,
        architecture: ArchitectureMap,
        observation: RuntimeObservation,
        expected: tuple[str, ...],
        forbidden: tuple[str, ...],
    ) -> dict[str, Any]:
        observed = {edge.key for edge in observation.edges}
        missing_expected = sorted(set(expected) - observed)
        observed_forbidden = sorted(set(forbidden) & observed)
        runtime_map = ArchitectureMap(
            source=architecture.source,
            nodes=architecture.nodes,
            edges=list(observation.edges),
            rules=architecture.rules,
            parse_errors=[],
        )
        violations = self._boundary_violations(runtime_map)
        hard = [item for item in violations if item["severity"] == "HARD"]
        static_pairs = self._static_module_pairs(architecture)
        runtime_only = [
            edge.to_dict()
            for edge in observation.edges
            if (edge.source, edge.target) not in static_pairs
        ]

        expected_status = "NOT_CHECKED" if not expected else ("PASS" if not missing_expected else "FAIL")
        forbidden_status = "NOT_CHECKED" if not forbidden else ("PASS" if not observed_forbidden else "FAIL")
        if observation.envelope_breaches:
            evidence_result = "ENVELOPE_EXCEEDED"
        elif hard or missing_expected or observed_forbidden:
            evidence_result = "VIOLATED_ON_TRACE"
        elif observation.coverage != "OBSERVED":
            evidence_result = "INCONCLUSIVE"
        elif expected or forbidden:
            evidence_result = "SATISFIED_ON_TRACE"
        else:
            evidence_result = "INCONCLUSIVE"

        return {
            "status": "CURRENT",
            "source": observation.source.to_dict(),
            "execution": {
                "run_id": observation.run_id,
                "command": list(observation.command),
                "status": observation.status,
                "exit_code": observation.exit_code,
                "timeout_seconds": observation.timeout_seconds,
                "stdout": observation.stdout,
                "stderr": observation.stderr,
                "isolation": observation.isolation,
                "provider_id": observation.provider_id,
                "enforcement": observation.enforcement,
                "envelope_breaches": list(observation.envelope_breaches),
            },
            "observed_map": {
                "coverage": observation.coverage,
                "trace_files": observation.trace_files,
                "edges": [edge.to_dict() for edge in observation.edges],
                "runtime_only_edges": runtime_only,
                "effects": [effect.to_dict() for effect in observation.effects],
            },
            "runtime_boundary": {
                "status": (
                    "NOT_EVALUATED"
                    if self._conformance_state(architecture) != "CONFIGURED"
                    else ("UNKNOWN" if observation.coverage != "OBSERVED" else ("FAIL" if hard else "PASS"))
                ),
                "conformance": self._conformance_state(architecture),
                "violations": violations,
            },
            "assertions": {
                "expected_runtime_edges": {"status": expected_status, "missing": missing_expected},
                "forbidden_runtime_edges": {"status": forbidden_status, "observed": observed_forbidden},
            },
            "evidence_result": evidence_result,
            "note": "SATISFIED_ON_TRACE applies only to this source snapshot and execution. It is not a proof of general correctness.",
        }

    def _latest_runtime_result(self, architecture: ArchitectureMap) -> dict[str, Any]:
        observation = self.store.get_runtime_observation()
        if observation is None:
            return {"status": "NOT_OBSERVED", "evidence_result": "INCONCLUSIVE"}
        if not self._observation_current(observation, architecture):
            return {
                "status": "STALE",
                "evidence_result": "INCONCLUSIVE",
                "observed_source": observation.source.to_dict(),
                "current_source": architecture.source.to_dict(),
            }
        raw_contract = self.store.get_json("runtime_contract")
        expected: tuple[str, ...] = ()
        forbidden: tuple[str, ...] = ()
        if isinstance(raw_contract, dict):
            expected = tuple(str(item) for item in raw_contract.get("expected_runtime_edges", []))
            forbidden = tuple(str(item) for item in raw_contract.get("forbidden_runtime_edges", []))
        return self._runtime_result(architecture, observation, expected, forbidden)

    @staticmethod
    def _observation_current(observation: RuntimeObservation, architecture: ArchitectureMap) -> bool:
        observed_id = observation.source.snapshot_id
        current_id = architecture.source.snapshot_id
        if observed_id and current_id:
            return observed_id == current_id
        return (
            observation.source.git_head == architecture.source.git_head
            and observation.source.dirty_files == architecture.source.dirty_files
        )

    def _find_nodes(self, architecture: ArchitectureMap, target: str) -> list[Node]:
        target_l = target.lower()
        exact = [n for n in architecture.nodes if target_l in {n.id.lower(), n.name.lower(), n.qualname.lower(), n.path.lower()}]
        if exact:
            return exact
        return [n for n in architecture.nodes if target_l in n.id.lower() or target_l in n.qualname.lower() or target_l in n.path.lower()]

    def _conformance_state(self, architecture: ArchitectureMap) -> str:
        has_boundaries = bool(self.config.boundary_patterns)
        has_rules = bool(architecture.rules)
        if has_boundaries and has_rules:
            return "CONFIGURED"
        if has_boundaries or has_rules:
            return "INCOMPLETE_CONFIG"
        return "NOT_CONFIGURED"

    def _boundary_violations(self, architecture: ArchitectureMap) -> list[dict[str, Any]]:
        by_id = {n.id: n for n in architecture.nodes}
        violations: list[dict[str, Any]] = []
        for edge in architecture.edges:
            source = by_id.get(edge.source)
            target = by_id.get(edge.target)
            if not source or not target or not source.boundary or not target.boundary:
                continue
            for rule in architecture.rules:
                if rule.mode != "forbid":
                    continue
                if fnmatch.fnmatch(source.boundary, rule.source) and fnmatch.fnmatch(target.boundary, rule.target):
                    violations.append({
                        "type": "FORBIDDEN_DEPENDENCY",
                        "severity": rule.severity,
                        "source_boundary": source.boundary,
                        "target_boundary": target.boundary,
                        "source_node": source.id,
                        "target_node": target.id,
                        "edge": edge.key,
                        "evidence": edge.evidence,
                        "origin": edge.origin,
                        "description": rule.description,
                    })
        return violations

    def _static_module_pairs(self, architecture: ArchitectureMap) -> set[tuple[str, str]]:
        module_by_path = {node.path: node.id for node in architecture.nodes if node.kind == "module"}
        by_id = {node.id: node for node in architecture.nodes}

        def module_id(node_id: str) -> str | None:
            node = by_id.get(node_id)
            if node is None:
                return node_id if node_id.startswith("module:") else None
            if node.kind == "module":
                return node.id
            return module_by_path.get(node.path)

        pairs: set[tuple[str, str]] = set()
        for edge in architecture.edges:
            source = module_id(edge.source)
            target = module_id(edge.target)
            if source and target and source != target:
                pairs.add((source, target))
        return pairs

    @staticmethod
    def _edge_from_key(key: str) -> Edge:
        source, kind, target = key.split("|", 2)
        return Edge(source, target, kind)  # type: ignore[arg-type]

    def _compile_check(self) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        checked = 0
        for file in sorted(self.root.rglob("*.py")):
            rel = file.relative_to(self.root).as_posix()
            if self.config.excluded(rel):
                continue
            checked += 1
            try:
                source = file.read_text(encoding="utf-8")
                compile(source, str(file), "exec")
            except (OSError, UnicodeDecodeError, SyntaxError) as exc:
                errors.append({"path": rel, "error": str(exc)})
        return {
            "status": "PASS" if not errors else "FAIL",
            "checked_files": checked,
            "errors": errors[:100],
        }

