from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EvidenceOrigin = Literal["STATIC", "DECLARED", "RUNTIME", "INFERRED"]
EdgeKind = Literal["IMPORT", "CALL", "READ", "WRITE"]


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
        )
