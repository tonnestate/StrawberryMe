from __future__ import annotations

import ast
from typing import Any


def _name(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name != "*":
                    aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _resolved_name(node: ast.AST | None, aliases: dict[str, str]) -> str | None:
    dotted = _name(node)
    if not dotted:
        return None
    head, *tail = dotted.split(".")
    base = aliases.get(head)
    return ".".join([base, *tail]) if base and tail else (base or dotted)


def detect_dynamic_signals(tree: ast.AST, path: str) -> list[dict[str, Any]]:
    aliases = _aliases(tree)
    signals: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            callee = _resolved_name(node.func, aliases) or ""
            signal: str | None = None
            if callee in {"importlib.import_module", "__import__"}:
                signal = "DYNAMIC_IMPORT"
            elif callee in {"getattr", "builtins.getattr", "setattr", "builtins.setattr"}:
                # A literal attribute name is statically inspectable; dynamic attribute selection is not.
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                    signal = None
                else:
                    signal = "REFLECTIVE_ACCESS"
            elif callee in {
                "subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call",
                "subprocess.check_output", "os.system", "os.posix_spawn", "os.posix_spawnp",
                "os.execv", "os.execve", "os.execl", "os.execlp", "os.execvp", "os.execvpe", "os.fork",
            }:
                signal = "PROCESS_CREATION"
            elif callee.startswith(("requests.", "httpx.", "aiohttp.", "socket.")):
                signal = "NETWORK_CLIENT"
            elif callee in {"importlib.metadata.entry_points", "pkg_resources.iter_entry_points"}:
                signal = "PLUGIN_ENTRYPOINT"
            elif callee in {"os.getenv", "os.environ.get"}:
                signal = "CONFIG_ACCESS"
            if signal:
                signals.append({"path": path, "line": int(getattr(node, "lineno", 0)), "signal": signal, "callee": callee})
        elif isinstance(node, ast.Subscript) and _resolved_name(node.value, aliases) == "os.environ":
            signals.append({"path": path, "line": int(getattr(node, "lineno", 0)), "signal": "CONFIG_ACCESS", "callee": "os.environ[]"})
    unique = {(item["path"], item["line"], item["signal"], item["callee"]): item for item in signals}
    return [unique[key] for key in sorted(unique)]
