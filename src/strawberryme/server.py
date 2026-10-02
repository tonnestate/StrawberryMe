from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from mcp.server import MCPServer
except ImportError as exc:  # pragma: no cover
    MCPServer = None  # type: ignore[assignment]
    _MCP_IMPORT_ERROR = exc
else:
    _MCP_IMPORT_ERROR = None

from .core import StrawberryCore


def _core() -> StrawberryCore:
    return StrawberryCore(Path(os.environ.get("STRAWBERRY_ROOT", os.getcwd())))


if MCPServer is not None:
    mcp = MCPServer("StrawberryMe")

    @mcp.tool()
    def strawberry_status() -> dict[str, Any]:
        """Return source identity, map health, architecture rule status and runtime capability."""
        return _core().status()

    @mcp.tool()
    def strawberry_cursor(target: str, horizon: int = 1) -> dict[str, Any]:
        """Orient the agent around one module/symbol with I/O, upstream/downstream dependencies and local violations."""
        return _core().cursor(target, horizon=max(0, min(horizon, 4)))

    @mcp.tool()
    def strawberry_preflight(add: list[str] | None = None, remove: list[str] | None = None) -> dict[str, Any]:
        """Record and preflight an expected architecture delta before mutation."""
        return _core().preflight(add=add, remove=remove)

    @mcp.tool()
    def strawberry_verify(command: list[str] | None = None, timeout_seconds: int = 30) -> dict[str, Any]:
        """Rescan the code, check build/boundaries/expected delta, and optionally run one local command."""
        return _core().verify(command=command, timeout_seconds=max(1, min(timeout_seconds, 300)))
else:
    mcp = None


def main() -> None:
    if _MCP_IMPORT_ERROR is not None:
        raise SystemExit('MCP support requires: pip install "strawberryme[mcp]"') from _MCP_IMPORT_ERROR
    raise SystemExit("Run with the official MCP CLI, e.g. `mcp run src/strawberryme/server.py --transport stdio`.")

if __name__ == "__main__":
    main()
