from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .core import StrawberryCore


def _root(payload: dict[str, Any]) -> Path:
    return Path(
        os.environ.get("CLAUDE_PROJECT_DIR")
        or payload.get("cwd")
        or os.environ.get("STRAWBERRY_ROOT")
        or os.getcwd()
    ).resolve()


def _read_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def session_context(core: StrawberryCore) -> dict[str, Any]:
    status = core.status()
    return {
        "continue": True,
        "suppressOutput": False,
        "systemMessage": (
            "StrawberryMe orientation: "
            f"snapshot={status['source'].get('snapshot_id', 'unknown')}; "
            f"static_violations={status['architecture']['violations']}; "
            f"future_delta={'active' if status['future_delta'] else 'none'}; "
            "use strawberry_assess/cursor before expanding context unnecessarily."
        ),
    }


def pre_tool(core: StrawberryCore, payload: dict[str, Any]) -> dict[str, Any]:
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path")
    if not path:
        return {"continue": True, "suppressOutput": True}
    try:
        rel = Path(path).resolve().relative_to(core.root).as_posix()
    except Exception:
        rel = str(path).replace("\\", "/")
    assessment = core.assess_change(paths=[rel])
    if assessment["risk"] == "LOW":
        return {"continue": True, "suppressOutput": True}
    return {
        "continue": True,
        "suppressOutput": False,
        "systemMessage": (
            f"StrawberryMe change signal {assessment['risk']} for {rel}: "
            + ", ".join(assessment["reasons"])
            + f". Recommended: {assessment['recommended_path']}."
        ),
    }


def stop(core: StrawberryCore) -> dict[str, Any]:
    result = core.verify()
    failures: list[str] = []
    if result["build"]["status"] == "FAIL":
        failures.append("build failed")
    if result["boundary"]["status"] == "FAIL":
        failures.append("static architecture boundary failed")
    if result["expected_delta"].get("status") == "FAIL":
        failures.append("expected architecture delta is incomplete")
    if result["runtime"].get("evidence_result") in {"VIOLATED_ON_TRACE", "ENVELOPE_EXCEEDED"}:
        failures.append(f"runtime evidence={result['runtime']['evidence_result']}")
    if failures:
        return {
            "decision": "block",
            "reason": "; ".join(failures),
            "systemMessage": "StrawberryMe completion gate found unresolved evidence. Resolve it before claiming completion.",
        }
    return {
        "decision": "approve",
        "reason": "No blocking StrawberryMe evidence is currently present.",
        "systemMessage": "StrawberryMe completion gate passed for the evidence currently available.",
    }


def main() -> None:
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = _read_payload()
    core = StrawberryCore(_root(payload))
    if event in {"session-start", "pre-compact"}:
        _emit(session_context(core))
        return
    if event == "pre-tool-use":
        _emit(pre_tool(core, payload))
        return
    if event == "stop":
        _emit(stop(core))
        return
    _emit({"continue": True, "suppressOutput": True})


if __name__ == "__main__":
    main()
