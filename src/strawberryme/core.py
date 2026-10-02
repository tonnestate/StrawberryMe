from __future__ import annotations

import fnmatch
import subprocess
from collections import deque
from pathlib import Path
from typing import Any

from .config import Config, load_config
from .models import ArchitectureMap, Delta, Edge, Node, RuntimeObservation
from .runtime_probe import observe_python
from .scanner import scan_python
from .store import Store


class StrawberryCore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(self.root)
        self.config: Config = load_config(self.root)
        self.store = Store(self.root)

    def map(self) -> ArchitectureMap:
        return scan_python(self.root, self.config)

    def status(self) -> dict[str, Any]:
        architecture = self.map()
        delta = self.store.get_delta()
        violations = self._boundary_violations(architecture)
        observation = self.store.get_runtime_observation()
        runtime_state: dict[str, Any] = {
            "probe": "PYTHON_SITECUSTOMIZE",
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
            "strawberryme": "0.2.0",
            "root": str(self.root),
            "source": architecture.source.to_dict(),
            "language_support": {"python": "ACTIVE", "javascript": "PLANNED", "php": "PLANNED", "csharp": "PLANNED"},
            "map": {"nodes": len(architecture.nodes), "edges": len(architecture.edges), "parse_errors": len(architecture.parse_errors)},
            "architecture": {"rules": len(architecture.rules), "violations": len(violations)},
            "future_delta": delta.to_dict() if delta else None,
            "runtime": runtime_state,
        }

    def cursor(self, target: str, horizon: int = 1) -> dict[str, Any]:
        architecture = self.map()
        matches = self._find_nodes(architecture, target)
        if not matches:
            return {"status": "NOT_FOUND", "target": target, "candidates": []}
        if len(matches) > 1:
            return {"status": "AMBIGUOUS", "target": target, "candidates": [n.to_dict() for n in matches[:20]]}
        focus = matches[0]
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
            "nodes": [by_id[x].to_dict() for x in sorted(seen) if x in by_id],
            "edges": [e.to_dict() for e in relevant_edges],
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
        observation = observe_python(self.root, architecture.source, command, timeout_seconds)
        self.store.set_runtime_observation(observation)
        self.store.set_json(
            "runtime_contract",
            {"expected_runtime_edges": list(expected), "forbidden_runtime_edges": list(forbidden)},
        )
        return self._runtime_result(architecture, observation, expected, forbidden)

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
        violations = self._boundary_violations(architecture)
        hard = [v for v in violations if v["severity"] == "HARD"]
        runtime = self._latest_runtime_result(architecture)
        runtime_failed = runtime.get("evidence_result") == "VIOLATED_ON_TRACE"
        runtime_stale = runtime.get("status") == "STALE"
        drift_found = bool(hard or expected_result.get("status") == "FAIL" or runtime_failed)
        return {
            "source": architecture.source.to_dict(),
            "build": build,
            "boundary": {"status": "FAIL" if hard else "PASS", "violations": violations},
            "expected_delta": expected_result,
            "runtime": runtime,
            "drift": "FOUND" if drift_found else ("UNKNOWN" if runtime_stale else "NONE"),
            "truth_model": {
                "declared": "architecture rules + expected delta",
                "static": "Python AST Current MAP",
                "observed": "latest bound runtime trace when available",
            },
        }

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
        if hard or missing_expected or observed_forbidden:
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
            },
            "observed_map": {
                "coverage": observation.coverage,
                "trace_files": observation.trace_files,
                "edges": [edge.to_dict() for edge in observation.edges],
                "runtime_only_edges": runtime_only,
                "effects": [effect.to_dict() for effect in observation.effects],
            },
            "runtime_boundary": {
                "status": "UNKNOWN" if observation.coverage != "OBSERVED" else ("FAIL" if hard else "PASS"),
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
        result = subprocess.run(
            ["python", "-m", "compileall", "-q", str(self.root)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return {
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "exit_code": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        }
