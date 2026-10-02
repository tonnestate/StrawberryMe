from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def _name(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def detect_dynamic_signals(tree: ast.AST, path: str) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            callee = _name(node.func) or ""
            signal: str | None = None
            if callee in {"importlib.import_module", "__import__"}:
                signal = "DYNAMIC_IMPORT"
            elif callee in {"getattr", "setattr"}:
                signal = "REFLECTIVE_ACCESS"
            elif callee in {"subprocess.run", "subprocess.Popen", "subprocess.call", "os.system", "os.execv", "os.execve", "os.execl", "os.execlp"}:
                signal = "PROCESS_CREATION"
            elif callee.startswith(("requests.", "httpx.", "aiohttp.", "socket.")):
                signal = "NETWORK_CLIENT"
            elif callee in {"importlib.metadata.entry_points", "pkg_resources.iter_entry_points"}:
                signal = "PLUGIN_ENTRYPOINT"
            elif callee in {"os.getenv", "os.environ.get"}:
                signal = "CONFIG_ACCESS"
            if signal:
                signals.append({
                    "path": path,
                    "line": int(getattr(node, "lineno", 0)),
                    "signal": signal,
                    "callee": callee,
                })
        elif isinstance(node, ast.Subscript) and _name(node.value) == "os.environ":
            signals.append({
                "path": path,
                "line": int(getattr(node, "lineno", 0)),
                "signal": "CONFIG_ACCESS",
                "callee": "os.environ[]",
            })
    unique = {(item["path"], item["line"], item["signal"], item["callee"]): item for item in signals}
    return [unique[key] for key in sorted(unique)]
