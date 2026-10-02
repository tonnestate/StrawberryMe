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
        """Return source identity, architecture state, runtime evidence and adaptive probe state."""
        return _core().status()

    @mcp.tool()
    def strawberry_assess(paths: list[str] | None = None, target: str | None = None) -> dict[str, Any]:
        """Classify concrete change signals and choose the smallest useful verification path."""
        return _core().assess_change(paths=paths, target=target)

    @mcp.tool()
    def strawberry_cursor(target: str, horizon: int = 1, adaptive: bool = False) -> dict[str, Any]:
        """Orient around one module/symbol; adaptive mode chooses a bounded horizon from evidence signals."""
        return _core().cursor(target, horizon=max(0, min(horizon, 4)), adaptive=adaptive)

    @mcp.tool()
    def strawberry_preflight(add: list[str] | None = None, remove: list[str] | None = None) -> dict[str, Any]:
        """Record and preflight an expected static architecture delta before mutation."""
        return _core().preflight(add=add, remove=remove)

    @mcp.tool()
    def strawberry_probe_plan(
        command: list[str],
        target: str | None = None,
        paths: list[str] | None = None,
        expected_runtime_edges: list[str] | None = None,
        forbidden_runtime_edges: list[str] | None = None,
        filesystem: str = "TEMP_WRITE",
        network: str = "DENY",
        process_spawn: str = "DENY",
        required_enforcement: str = "PYTHON_AUDIT",
        provider_id: str = "local-python",
        allowed_env_names: list[str] | None = None,
        max_cases: int = 3,
        max_repeats: int = 3,
        max_runtime_seconds: int = 60,
    ) -> dict[str, Any]:
        """Create a source-bound minimal probe plan and compile its execution envelope."""
        return _core().probe_plan(
            command=command,
            target=target,
            paths=paths,
            expected_runtime_edges=expected_runtime_edges,
            forbidden_runtime_edges=forbidden_runtime_edges,
            filesystem=filesystem,
            network=network,
            process_spawn=process_spawn,
            required_enforcement=required_enforcement,
            provider_id=provider_id,
            allowed_env_names=allowed_env_names,
            max_cases=max_cases,
            max_repeats=max_repeats,
            max_runtime_seconds=max_runtime_seconds,
        )

    @mcp.tool()
    def strawberry_probe_approve(plan_id: str, approved_by: str = "local-user") -> dict[str, Any]:
        """Approve a frozen source-bound probe plan after reviewing its execution envelope."""
        return _core().approve_probe_plan(plan_id, approved_by=approved_by)

    @mcp.tool()
    def strawberry_probe_run(plan_id: str) -> dict[str, Any]:
        """Execute a frozen probe plan inside its compiled execution envelope and return adaptive next action."""
        return _core().probe_run(plan_id)

    @mcp.tool()
    def strawberry_observe(
        command: list[str],
        timeout_seconds: int = 30,
        expected_runtime_edges: list[str] | None = None,
        forbidden_runtime_edges: list[str] | None = None,
    ) -> dict[str, Any]:
        """Low-level compatibility observation API. Prefer probe_plan -> probe_run for adaptive workflows."""
        return _core().observe(
            command=command,
            timeout_seconds=max(1, min(timeout_seconds, 300)),
            expected_runtime_edges=expected_runtime_edges,
            forbidden_runtime_edges=forbidden_runtime_edges,
        )


    @mcp.tool()
    def strawberry_history(limit: int = 10) -> dict[str, Any]:
        """Return bounded source-bound runtime evidence history and latest architecture diff between verifications."""
        return _core().evidence_history(limit=max(1, min(limit, 100)))

    @mcp.tool()
    def strawberry_verify(command: list[str] | None = None, timeout_seconds: int = 30) -> dict[str, Any]:
        """Verify build, static boundaries, expected delta and current source-bound runtime evidence."""
        return _core().verify(command=command, timeout_seconds=max(1, min(timeout_seconds, 300)))
else:
    mcp = None


def main() -> None:
    if _MCP_IMPORT_ERROR is not None:
        raise SystemExit('MCP support requires: pip install "strawberryme[mcp]"') from _MCP_IMPORT_ERROR
    if mcp is None:
        raise SystemExit("MCP server is unavailable")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
