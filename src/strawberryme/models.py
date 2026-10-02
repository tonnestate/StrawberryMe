from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EvidenceOrigin = Literal["STATIC", "DECLARED", "RUNTIME", "INFERRED"]
EdgeKind = Literal["IMPORT", "CALL", "READ", "WRITE"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


@dataclass(frozen=True)
class SourceIdentity:
    root: str
    git_head: str | None
    branch: str | None
    dirty: bool
    dirty_files: tuple[str, ...] = ()
    snapshot_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    path: str
    name: str
    qualname: str
    boundary: str | None = None
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: EdgeKind
    origin: EvidenceOrigin = "STATIC"
    evidence: str | None = None

    @property
    def key(self) -> str:
        return f"{self.source}|{self.kind}|{self.target}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BoundaryRule:
    source: str
    target: str
    mode: Literal["forbid", "allow"] = "forbid"
    severity: Literal["HARD", "SOFT"] = "HARD"
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureMap:
    source: SourceIdentity
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    rules: list[BoundaryRule] = field(default_factory=list)
    parse_errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "rules": [r.to_dict() for r in self.rules],
            "parse_errors": list(self.parse_errors),
        }


@dataclass(frozen=True)
class Delta:
    add: tuple[str, ...] = ()
    remove: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeEffect:
    actor: str
    kind: str
    target: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionEnvelope:
    source_snapshot: str
    allowed_executables: tuple[str, ...] = ("python",)
    filesystem: Literal["READ_ONLY", "TEMP_WRITE", "PROJECT_WRITE"] = "TEMP_WRITE"
    network: Literal["DENY", "ALLOW"] = "DENY"
    process_spawn: Literal["DENY", "ALLOW"] = "DENY"
    allowed_env_names: tuple[str, ...] = ()
    max_cases: int = 3
    max_repeats: int = 3
    max_runtime_seconds: int = 60

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ExecutionEnvelope":
        return cls(
            source_snapshot=str(raw.get("source_snapshot", "")),
            allowed_executables=tuple(str(x) for x in raw.get("allowed_executables", ["python"])),
            filesystem=str(raw.get("filesystem", "TEMP_WRITE")),  # type: ignore[arg-type]
            network=str(raw.get("network", "DENY")),  # type: ignore[arg-type]
            process_spawn=str(raw.get("process_spawn", "DENY")),  # type: ignore[arg-type]
            allowed_env_names=tuple(str(x) for x in raw.get("allowed_env_names", [])),
            max_cases=int(raw.get("max_cases", 3)),
            max_repeats=int(raw.get("max_repeats", 3)),
            max_runtime_seconds=int(raw.get("max_runtime_seconds", 60)),
        )


@dataclass(frozen=True)
class ProbeCase:
    case_id: str
    scenario: str
    command: tuple[str, ...]
    mode: Literal["SINGLE_SHOT", "REPEAT_N", "WARMUP_REPEAT_N"] = "SINGLE_SHOT"
    repeats: int = 1
    expected_runtime_edges: tuple[str, ...] = ()
    forbidden_runtime_edges: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProbeCase":
        return cls(
            case_id=str(raw.get("case_id", "case")),
            scenario=str(raw.get("scenario", "runtime observation")),
            command=tuple(str(x) for x in raw.get("command", [])),
            mode=str(raw.get("mode", "SINGLE_SHOT")),  # type: ignore[arg-type]
            repeats=int(raw.get("repeats", 1)),
            expected_runtime_edges=tuple(str(x) for x in raw.get("expected_runtime_edges", [])),
            forbidden_runtime_edges=tuple(str(x) for x in raw.get("forbidden_runtime_edges", [])),
        )


@dataclass(frozen=True)
class ProbePlan:
    plan_id: str
    source: SourceIdentity
    risk: RiskLevel
    reasons: tuple[str, ...]
    target: str | None
    cases: tuple[ProbeCase, ...]
    envelope: ExecutionEnvelope
    approval_required: bool
    approval_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "source": self.source.to_dict(),
            "risk": self.risk,
            "reasons": list(self.reasons),
            "target": self.target,
            "cases": [case.to_dict() for case in self.cases],
            "envelope": self.envelope.to_dict(),
            "approval_required": self.approval_required,
            "approval_reason": self.approval_reason,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProbePlan":
        source_raw = raw.get("source", {})
        source = SourceIdentity(
            root=str(source_raw.get("root", "")),
            git_head=source_raw.get("git_head"),
            branch=source_raw.get("branch"),
            dirty=bool(source_raw.get("dirty", False)),
            dirty_files=tuple(source_raw.get("dirty_files", [])),
            snapshot_id=source_raw.get("snapshot_id"),
        )
        return cls(
            plan_id=str(raw.get("plan_id", "")),
            source=source,
            risk=str(raw.get("risk", "LOW")),  # type: ignore[arg-type]
            reasons=tuple(str(x) for x in raw.get("reasons", [])),
            target=raw.get("target"),
            cases=tuple(ProbeCase.from_dict(x) for x in raw.get("cases", []) if isinstance(x, dict)),
            envelope=ExecutionEnvelope.from_dict(raw.get("envelope", {})),
            approval_required=bool(raw.get("approval_required", False)),
            approval_reason=raw.get("approval_reason"),
        )


@dataclass(frozen=True)
class RuntimeObservation:
    run_id: str
    source: SourceIdentity
    command: tuple[str, ...]
    timeout_seconds: int
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    isolation: str
    coverage: str
    edges: tuple[Edge, ...] = ()
    effects: tuple[RuntimeEffect, ...] = ()
    trace_files: int = 0
    envelope_breaches: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source": self.source.to_dict(),
            "command": list(self.command),
            "timeout_seconds": self.timeout_seconds,
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "isolation": self.isolation,
            "coverage": self.coverage,
            "edges": [edge.to_dict() for edge in self.edges],
            "effects": [effect.to_dict() for effect in self.effects],
            "trace_files": self.trace_files,
            "envelope_breaches": list(self.envelope_breaches),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RuntimeObservation":
        source_raw = raw.get("source", {})
        source = SourceIdentity(
            root=str(source_raw.get("root", "")),
            git_head=source_raw.get("git_head"),
            branch=source_raw.get("branch"),
            dirty=bool(source_raw.get("dirty", False)),
            dirty_files=tuple(source_raw.get("dirty_files", [])),
            snapshot_id=source_raw.get("snapshot_id"),
        )
        edges = tuple(
            Edge(
                source=str(item.get("source", "")),
                target=str(item.get("target", "")),
                kind=str(item.get("kind", "CALL")),  # type: ignore[arg-type]
                origin=str(item.get("origin", "RUNTIME")),  # type: ignore[arg-type]
                evidence=item.get("evidence"),
            )
            for item in raw.get("edges", [])
            if isinstance(item, dict)
        )
        effects = tuple(
            RuntimeEffect(
                actor=str(item.get("actor", "")),
                kind=str(item.get("kind", "")),
                target=str(item.get("target", "")),
            )
            for item in raw.get("effects", [])
            if isinstance(item, dict)
        )
        return cls(
            run_id=str(raw.get("run_id", "")),
            source=source,
            command=tuple(raw.get("command", [])),
            timeout_seconds=int(raw.get("timeout_seconds", 30)),
            status=str(raw.get("status", "UNKNOWN")),
            exit_code=raw.get("exit_code"),
            stdout=str(raw.get("stdout", "")),
            stderr=str(raw.get("stderr", "")),
            isolation=str(raw.get("isolation", "NONE")),
            coverage=str(raw.get("coverage", "UNKNOWN")),
            edges=edges,
            effects=effects,
            trace_files=int(raw.get("trace_files", 0)),
            envelope_breaches=tuple(str(x) for x in raw.get("envelope_breaches", [])),
        )
