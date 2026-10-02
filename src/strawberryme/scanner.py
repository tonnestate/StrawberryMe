from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from .config import Config
from .models import ArchitectureMap, Edge, Node
from .signals import detect_dynamic_signals
from .source import source_identity

PARSER_VERSION = "py-ast-v3"


def _annotation(node: ast.AST | None) -> str:
    if node is None:
        return "unknown"
    try:
        return ast.unparse(node)
    except Exception:
        return "unknown"


def _module_name(root: Path, file: Path) -> str:
    rel = file.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _cache_version(root: Path) -> str:
    path = root / "strawberry.toml"
    digest = hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()[:16]
    return f"{PARSER_VERSION}:{digest}"


def _resolve_module(imported: str, known_modules: set[str]) -> str | None:
    if imported in known_modules:
        return imported
    # Only resolve to a parent package. Never guess an arbitrary child module.
    parents = [m for m in known_modules if imported.startswith(m + ".")]
    return sorted(parents, key=len, reverse=True)[0] if parents else None


def _dotted(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _parse_file(root: Path, file: Path, config: Config) -> dict[str, Any]:
    rel = file.relative_to(root).as_posix()
    module = _module_name(root, file)
    boundary = config.boundary_for(rel)
    payload: dict[str, Any] = {
        "path": rel, "module": module, "boundary": boundary,
        "nodes": [], "imports": [], "calls": [], "signals": [], "parse_error": None,
    }
    module_id = f"module:{module or rel}"
    payload["nodes"].append(Node(module_id, "module", rel, module or rel, module or rel, boundary).to_dict())
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=rel)
    except (SyntaxError, UnicodeDecodeError) as exc:
        payload["parse_error"] = str(exc)
        return payload

    aliases: dict[str, str] = {}

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            qual = ".".join([module, *self.stack, node.name]).strip(".")
            payload["nodes"].append(Node(f"symbol:{qual}", "class", rel, node.name, qual, boundary).to_dict())
            self.stack.append(node.name); self.generic_visit(node); self.stack.pop()

        def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            qual = ".".join([module, *self.stack, node.name]).strip(".")
            inputs = tuple(
                f"{arg.arg}:{_annotation(arg.annotation)}"
                for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                if arg.arg not in {"self", "cls"}
            )
            output = _annotation(node.returns)
            outputs = () if output in {"None", "unknown"} else (output,)
            payload["nodes"].append(Node(f"symbol:{qual}", "function", rel, node.name, qual, boundary, inputs, outputs).to_dict())
            self.stack.append(node.name); self.generic_visit(node); self.stack.pop()

        visit_FunctionDef = _function
        visit_AsyncFunctionDef = _function

    Visitor().visit(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                aliases[local] = alias.name if alias.asname else alias.name.split(".")[0]
                payload["imports"].append({"base": alias.name, "member": None, "line": getattr(node, "lineno", 0)})
        elif isinstance(node, ast.ImportFrom):
            package = module if file.stem == "__init__" else module.rsplit(".", 1)[0] if "." in module else ""
            if node.level:
                parts = package.split(".") if package else []
                climb = max(0, node.level - 1)
                if climb:
                    parts = parts[:-climb] if climb <= len(parts) else []
                base = ".".join([*parts, node.module] if node.module else parts)
            else:
                base = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    if base:
                        payload["imports"].append({"base": base, "member": None, "line": getattr(node, "lineno", 0)})
                    continue
                local = alias.asname or alias.name
                aliases[local] = ".".join(part for part in (base, alias.name) if part)
                if base:
                    payload["imports"].append({"base": base, "member": alias.name, "line": getattr(node, "lineno", 0)})
        elif isinstance(node, ast.Call):
            dotted = _dotted(node.func)
            if dotted:
                head, *tail = dotted.split(".")
                resolved = aliases.get(head)
                if resolved:
                    dotted = ".".join([resolved, *tail]) if tail else resolved
                payload["calls"].append({"name": dotted, "line": getattr(node, "lineno", 0)})
    payload["signals"] = detect_dynamic_signals(tree, rel)
    return payload


def scan_python(root: Path, config: Config, store: Any | None = None) -> ArchitectureMap:
    root = root.resolve()
    cache_version = _cache_version(root)
    py_files = [f for f in root.rglob("*.py") if not config.excluded(f.relative_to(root).as_posix())]
    module_by_file = {f: _module_name(root, f) for f in py_files}
    known_modules = {m for m in module_by_file.values() if m}
    result = ArchitectureMap(source=source_identity(root), rules=config.rules)
    payloads: list[dict[str, Any]] = []
    reused = parsed = 0

    current_paths = {f.relative_to(root).as_posix() for f in py_files}
    if store is not None:
        store.prune_file_cache(current_paths, cache_version)

    for file in py_files:
        rel = file.relative_to(root).as_posix(); stat = file.stat()
        cached = store.get_file_cache(rel, cache_version, stat.st_mtime_ns, stat.st_size) if store is not None else None
        if isinstance(cached, dict):
            payload = cached; reused += 1
        else:
            payload = _parse_file(root, file, config); parsed += 1
            if store is not None:
                store.set_file_cache(rel, cache_version, stat.st_mtime_ns, stat.st_size, payload)
        payloads.append(payload)

    nodes: list[Node] = []
    symbols_by_qual: dict[str, str] = {}
    symbols_by_short: dict[str, list[str]] = {}
    module_node_by_name: dict[str, str] = {}
    for payload in payloads:
        for raw in payload.get("nodes", []):
            node = Node.from_dict(raw); nodes.append(node)
            if node.kind == "module": module_node_by_name[node.qualname] = node.id
            else:
                symbols_by_qual[node.qualname] = node.id
                symbols_by_short.setdefault(node.name, []).append(node.id)
        result.dynamic_signals.extend(payload.get("signals", []))
        if payload.get("parse_error"):
            result.parse_errors.append({"path": payload["path"], "error": payload["parse_error"]})

    edges: dict[str, Edge] = {}
    for payload in payloads:
        module = payload["module"]; source_id = f"module:{module or payload['path']}"; rel = payload["path"]
        for item in payload.get("imports", []):
            base = str(item.get("base", "")); member = item.get("member")
            candidate = f"{base}.{member}" if base and member else base
            target_module = candidate if candidate in known_modules else _resolve_module(base, known_modules)
            if target_module and target_module != module:
                edge = Edge(source_id, f"module:{target_module}", "IMPORT", evidence=f"{rel}:{item['line']}", resolution="EXACT")
                edges[edge.key] = edge
        for item in payload.get("calls", []):
            name = str(item["name"]); target: str | None = None; resolution = "EXACT"
            if name in symbols_by_qual:
                target = symbols_by_qual[name]
            else:
                pieces = name.split(".")
                for i in range(len(pieces), 0, -1):
                    candidate_symbol = ".".join(pieces[:i])
                    if candidate_symbol in symbols_by_qual:
                        target = symbols_by_qual[candidate_symbol]; break
                if target is None and len(symbols_by_short.get(pieces[-1], [])) == 1:
                    target = symbols_by_short[pieces[-1]][0]; resolution = "HEURISTIC"
            if target and target != source_id:
                edge = Edge(source_id, target, "CALL", evidence=f"{rel}:{item['line']}", resolution=resolution)  # type: ignore[arg-type]
                edges[edge.key] = edge

    result.nodes = sorted(nodes, key=lambda n: n.id)
    result.edges = sorted(edges.values(), key=lambda e: e.key)
    result.scan_stats = {
        "files": len(py_files), "parsed_files": parsed, "reused_files": reused,
        "cache_hit_ratio": round(reused / len(py_files), 4) if py_files else 1.0,
        "parser_version": cache_version,
    }
    return result
