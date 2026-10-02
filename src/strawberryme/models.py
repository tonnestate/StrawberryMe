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
