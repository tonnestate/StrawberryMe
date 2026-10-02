from __future__ import annotations

import ast
from pathlib import Path

from .config import Config
from .models import ArchitectureMap, Edge, Node
from .source import source_identity


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


def _resolve_import_target(module: str, imported: str, known_modules: set[str]) -> str | None:
    candidates = [imported, imported.split(".")[0]]
    for candidate in candidates:
        for known in known_modules:
            if known == candidate or known.startswith(candidate + ".") or candidate.startswith(known + "."):
                return f"module:{known}"
    return None


def _call_name(node: ast.Call) -> str | None:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        parts: list[str] = []
        cur: ast.AST = fn
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
    return None


def scan_python(root: Path, config: Config) -> ArchitectureMap:
    root = root.resolve()
    py_files: list[Path] = []
    for file in root.rglob("*.py"):
        rel = file.relative_to(root).as_posix()
        if not config.excluded(rel):
            py_files.append(file)

    module_by_file = {f: _module_name(root, f) for f in py_files}
    known_modules = {m for m in module_by_file.values() if m}
    result = ArchitectureMap(source=source_identity(root), rules=config.rules)
    symbols_by_short_name: dict[str, list[str]] = {}
    trees: dict[Path, ast.AST] = {}

    for file in py_files:
        rel = file.relative_to(root).as_posix()
        module = module_by_file[file]
        boundary = config.boundary_for(rel)
        module_id = f"module:{module or rel}"
        result.nodes.append(Node(module_id, "module", rel, module or rel, module or rel, boundary))
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"), filename=rel)
            trees[file] = tree
        except (SyntaxError, UnicodeDecodeError) as exc:
            result.parse_errors.append({"path": rel, "error": str(exc)})
            continue

        class StackVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.stack: list[str] = []

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                qual = ".".join([module, *self.stack, node.name]).strip(".")
                node_id = f"symbol:{qual}"
                result.nodes.append(Node(node_id, "class", rel, node.name, qual, boundary))
                symbols_by_short_name.setdefault(node.name, []).append(node_id)
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                qual = ".".join([module, *self.stack, node.name]).strip(".")
                node_id = f"symbol:{qual}"
                inputs = tuple(
                    f"{arg.arg}:{_annotation(arg.annotation)}"
                    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                    if arg.arg not in {"self", "cls"}
                )
                output = _annotation(node.returns)
                outputs = () if output in {"None", "unknown"} else (output,)
                result.nodes.append(Node(node_id, "function", rel, node.name, qual, boundary, inputs, outputs))
                symbols_by_short_name.setdefault(node.name, []).append(node_id)
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

        StackVisitor().visit(tree)

    for file, tree in trees.items():
        rel = file.relative_to(root).as_posix()
        module = module_by_file[file]
        module_id = f"module:{module or rel}"
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = _resolve_import_target(module, alias.name, known_modules)
                    if target and target != module_id:
                        result.edges.append(Edge(module_id, target, "IMPORT", evidence=f"{rel}:{getattr(node, 'lineno', 0)}"))
            elif isinstance(node, ast.ImportFrom) and node.module:
                target = _resolve_import_target(module, node.module, known_modules)
                if target and target != module_id:
                    result.edges.append(Edge(module_id, target, "IMPORT", evidence=f"{rel}:{getattr(node, 'lineno', 0)}"))
            elif isinstance(node, ast.Call):
                name = _call_name(node)
                if not name:
                    continue
                short = name.split(".")[-1]
                matches = symbols_by_short_name.get(short, [])
                if len(matches) == 1:
                    target = matches[0]
                    if target != module_id:
                        result.edges.append(Edge(module_id, target, "CALL", evidence=f"{rel}:{getattr(node, 'lineno', 0)}"))

    unique_edges = {e.key: e for e in result.edges}
    result.edges = sorted(unique_edges.values(), key=lambda e: e.key)
    result.nodes.sort(key=lambda n: n.id)
    return result
