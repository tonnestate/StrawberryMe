from __future__ import annotations

import fnmatch
import subprocess
from collections import deque
from pathlib import Path
from typing import Any

from .config import Config, load_config
from .models import ArchitectureMap, Delta, Edge, Node
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
        return {
            "strawberryme": "0.1.0",
            "root": str(self.root),
            "source": architecture.source.to_dict(),
            "language_support": {"python": "ACTIVE", "javascript": "PLANNED", "php": "PLANNED", "csharp": "PLANNED"},
            "map": {"nodes": len(architecture.nodes), "edges": len(architecture.edges), "parse_errors": len(architecture.parse_errors)},
            "architecture": {"rules": len(architecture.rules), "violations": len(violations)},
            "future_delta": delta.to_dict() if delta else None,
            "runtime": {"runner": "LOCAL_SUBPROCESS", "isolation": "NONE", "sandbox_provider": "NOT_CONFIGURED"},
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
        candidate = (current | set(delta.add)) - set(delta.remove)
        candidate_edges = [self._edge_from_key(k) for k in candidate]
        candidate_map = ArchitectureMap(architecture.source, architecture.nodes, candidate_edges, architecture.rules, architecture.parse_errors)
        violations = self._boundary_violations(candidate_map)
        missing_remove = sorted(set(delta.remove) - current)
        already_present_add = sorted(set(delta.add) & current)
        return {
            "status": "INVALID" if malformed else ("VIOLATION" if any(v["severity"] == "HARD" for v in violations) else "READY"),
            "source": architecture.source.to_dict(),
            "expected_delta": delta.to_dict(),
            "malformed_edges": malformed,
            "remove_not_present": missing_remove,
            "add_already_present": already_present_add,
            "architecture_violations": violations,
            "edge_format": "source|KIND|target, e.g. module:app.service|IMPORT|module:app.db",
        }

    def verify(self, command: list[str] | None = None, timeout_seconds: int = 30) -> dict[str, Any]:
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
        execution = self._execute(command, timeout_seconds) if command else {"status": "NOT_CHECKED"}
        violations = self._boundary_violations(architecture)
        hard = [v for v in violations if v["severity"] == "HARD"]
        return {
            "source": architecture.source.to_dict(),
            "build": build,
            "boundary": {"status": "FAIL" if hard else "PASS", "violations": violations},
            "expected_delta": expected_result,
            "execution": execution,
            "drift": "FOUND" if hard or expected_result.get("status") == "FAIL" else "NONE",
            "note": "Runtime execution in v0.1 uses a local subprocess and is not an isolation boundary.",
        }

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
                        "description": rule.description,
                    })
        return violations

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

    def _execute(self, command: list[str], timeout_seconds: int) -> dict[str, Any]:
        if not command:
            return {"status": "NOT_CHECKED"}
        try:
            result = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            return {
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout[-8000:],
                "stderr": result.stderr[-8000:],
                "isolation": "NONE",
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "TIMEOUT",
                "command": command,
                "timeout_seconds": timeout_seconds,
                "stdout": (exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else "",
                "stderr": (exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else "",
                "isolation": "NONE",
            }
