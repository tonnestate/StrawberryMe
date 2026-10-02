from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from .models import Edge, ExecutionEnvelope, RuntimeEffect, RuntimeObservation, SourceIdentity


_BOOTSTRAP = r'''
from __future__ import annotations

import atexit
import json
import os
import runpy
import sys

ROOT = os.path.abspath(os.environ["STRAWBERRY_TRACE_ROOT"])
TRACE_DIR = os.path.abspath(os.environ["STRAWBERRY_TRACE_DIR"])
os.makedirs(TRACE_DIR, exist_ok=True)
_EDGES = set()
_EFFECTS = []
_IN_AUDIT = False
_ENVELOPE = json.loads(os.environ.get("STRAWBERRY_EXECUTION_ENVELOPE", "{}"))
_BREACHES = []


def _module_id(filename):
    if not filename or filename.startswith("<"):
        return None
    try:
        path = os.path.abspath(filename)
        if os.path.commonpath([ROOT, path]) != ROOT:
            return None
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    except Exception:
        return None
    if rel.startswith(".strawberry/") or not rel.endswith(".py"):
        return None
    rel = rel[:-3]
    if rel.endswith("/__init__"):
        rel = rel[:-9]
    name = rel.strip("/").replace("/", ".")
    return f"module:{name or rel}"


def _actor():
    frame = sys._getframe(2)
    while frame:
        module = _module_id(frame.f_code.co_filename)
        if module:
            return module
        frame = frame.f_back
    return None


def _profile(frame, event, arg):
    if event != "call":
        return
    caller = frame.f_back
    if caller is None:
        return
    source = _module_id(caller.f_code.co_filename)
    target = _module_id(frame.f_code.co_filename)
    if source and target and source != target:
        _EDGES.add((source, "CALL", target))


def _deny(reason):
    _BREACHES.append(reason)
    raise PermissionError(f"StrawberryMe execution envelope blocked: {reason}")


def _audit(event, args):
    global _IN_AUDIT
    if _IN_AUDIT:
        return
    _IN_AUDIT = True
    try:
        actor = _actor()
        if event == "open" and actor and args:
            raw_path = args[0]
            mode = args[1] if len(args) > 1 else "r"
            if isinstance(raw_path, (str, bytes, os.PathLike)):
                path = os.fspath(raw_path)
                if isinstance(path, bytes):
                    path = os.fsdecode(path)
                if any(flag in str(mode) for flag in ("w", "a", "+", "x")):
                    target = os.path.abspath(path)
                    _EFFECTS.append({"actor": actor, "kind": "FILE_WRITE", "target": target})
                    fs = _ENVELOPE.get("filesystem", "PROJECT_WRITE")
                    if fs == "READ_ONLY":
                        _deny(f"FILE_WRITE:{target}")
                    if fs == "TEMP_WRITE":
                        try:
                            in_project = os.path.commonpath([ROOT, target]) == ROOT
                        except Exception:
                            in_project = False
                        allowed_state = target.startswith(os.path.join(ROOT, ".strawberry"))
                        if in_project and not allowed_state:
                            _deny(f"PROJECT_WRITE:{target}")
        elif event == "socket.connect" and actor:
            address = args[1] if len(args) > 1 else args[0]
            target = repr(address)
            _EFFECTS.append({"actor": actor, "kind": "NETWORK_CONNECT", "target": target})
            if _ENVELOPE.get("network", "ALLOW") == "DENY":
                _deny(f"NETWORK_CONNECT:{target}")
        elif event in {"subprocess.Popen", "os.system"} and actor:
            target = repr(args[0] if args else "")
            _EFFECTS.append({"actor": actor, "kind": "PROCESS_SPAWN", "target": target})
            if _ENVELOPE.get("process_spawn", "ALLOW") == "DENY":
                _deny(f"PROCESS_SPAWN:{target}")
    finally:
        _IN_AUDIT = False
_ENVELOPE = json.loads(os.environ.get("STRAWBERRY_EXECUTION_ENVELOPE", "{}"))
_BREACHES = []


def _flush():
    payload = {
        "pid": os.getpid(),
        "edges": [
            {"source": source, "kind": kind, "target": target}
            for source, kind, target in sorted(_EDGES)
        ],
        "effects": _EFFECTS[-2000:],
        "envelope_breaches": _BREACHES[-2000:],
    }
    target = os.path.join(TRACE_DIR, f"trace-{os.getpid()}.json")
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
    except Exception:
        pass


sys.setprofile(_profile)
try:
    sys.addaudithook(_audit)
except Exception:
    pass
atexit.register(_flush)

mode = os.environ["STRAWBERRY_TARGET_MODE"]
value = os.environ["STRAWBERRY_TARGET_VALUE"]
args = json.loads(os.environ.get("STRAWBERRY_TARGET_ARGS", "[]"))
if mode == "code":
    sys.argv = ["-c", *args]
    namespace = {"__name__": "__main__", "__file__": "<string>", "__package__": None}
    exec(compile(value, "<string>", "exec"), namespace, namespace)
elif mode == "module":
    sys.argv = [value, *args]
    runpy.run_module(value, run_name="__main__", alter_sys=True)
elif mode == "script":
    sys.argv = [value, *args]
    runpy.run_path(value, run_name="__main__")
else:
    raise SystemExit(f"Unsupported StrawberryMe probe mode: {mode}")
'''


def _is_python_command(command: list[str]) -> bool:
    if not command:
        return False
    return Path(command[0]).name.lower().startswith("python")


def _instrumented_command(command: list[str], instrument_dir: Path, env: dict[str, str]) -> list[str]:
    if not _is_python_command(command):
        return list(command)
    bootstrap = str(instrument_dir / "bootstrap.py")
    if len(command) >= 3 and command[1] == "-c":
        env["STRAWBERRY_TARGET_MODE"] = "code"
        env["STRAWBERRY_TARGET_VALUE"] = command[2]
        env["STRAWBERRY_TARGET_ARGS"] = json.dumps(command[3:])
        return [command[0], bootstrap]
    if len(command) >= 3 and command[1] == "-m":
        env["STRAWBERRY_TARGET_MODE"] = "module"
        env["STRAWBERRY_TARGET_VALUE"] = command[2]
        env["STRAWBERRY_TARGET_ARGS"] = json.dumps(command[3:])
        return [command[0], bootstrap]
    if len(command) >= 2 and not command[1].startswith("-"):
        env["STRAWBERRY_TARGET_MODE"] = "script"
        env["STRAWBERRY_TARGET_VALUE"] = command[1]
        env["STRAWBERRY_TARGET_ARGS"] = json.dumps(command[2:])
        return [command[0], bootstrap]
    return list(command)


def observe_python(
    root: Path,
    source: SourceIdentity,
    command: list[str],
    timeout_seconds: int = 30,
    envelope: ExecutionEnvelope | None = None,
) -> RuntimeObservation:
    if not command:
        raise ValueError("command must not be empty")

    state_dir = root / ".strawberry"
    state_dir.mkdir(exist_ok=True)
    probe_parent = state_dir / "runtime"
    probe_parent.mkdir(exist_ok=True)
    run_id = uuid.uuid4().hex
    trace_dir = probe_parent / run_id
    trace_dir.mkdir(parents=True, exist_ok=True)
    instrument_dir = Path(tempfile.mkdtemp(prefix="instrument-", dir=trace_dir))
    (instrument_dir / "bootstrap.py").write_text(_BOOTSTRAP, encoding="utf-8")

    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    pythonpath = [str(root)]
    if existing:
        pythonpath.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    env["STRAWBERRY_TRACE_ROOT"] = str(root.resolve())
    env["STRAWBERRY_TRACE_DIR"] = str(trace_dir.resolve())
    if envelope is not None:
        env["STRAWBERRY_EXECUTION_ENVELOPE"] = json.dumps(envelope.to_dict(), sort_keys=True)
        keep = {"PATH", "PYTHONPATH", "PYTHONHOME", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_ALL"}
        keep.update(envelope.allowed_env_names)
        env = {key: value for key, value in env.items() if key in keep or key.startswith("STRAWBERRY_")}
    run_command = _instrumented_command(command, instrument_dir, env)

    try:
        result = subprocess.run(
            run_command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=env,
        )
        returncode: int | None = result.returncode
        stdout = result.stdout[-8000:]
        stderr = result.stderr[-8000:]
        status = "PASS" if result.returncode == 0 else "FAIL"
    except subprocess.TimeoutExpired as exc:
        returncode = None
        stdout = (exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else ""
        status = "TIMEOUT"

    edges_by_key: dict[str, Edge] = {}
    effects: list[RuntimeEffect] = []
    breaches: list[str] = []
    trace_files = sorted(trace_dir.glob("trace-*.json"))
    for trace_file in trace_files:
        try:
            raw = json.loads(trace_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for item in raw.get("edges", []):
            if not isinstance(item, dict):
                continue
            edge = Edge(
                str(item.get("source", "")),
                str(item.get("target", "")),
                "CALL",
                origin="RUNTIME",
                evidence=f"runtime:{run_id}",
            )
            if edge.source and edge.target:
                edges_by_key[edge.key] = edge
        breaches.extend(str(item) for item in raw.get("envelope_breaches", []))
        for item in raw.get("effects", []):
            if not isinstance(item, dict):
                continue
            actor = str(item.get("actor", ""))
            kind = str(item.get("kind", ""))
            target = str(item.get("target", ""))
            if actor and kind and target:
                effects.append(RuntimeEffect(actor=actor, kind=kind, target=target))

    unique_effects: dict[tuple[str, str, str], RuntimeEffect] = {
        (effect.actor, effect.kind, effect.target): effect for effect in effects
    }
    coverage = "OBSERVED" if edges_by_key or unique_effects else (
        "UNINSTRUMENTED_COMMAND" if not _is_python_command(command) else "NO_PROJECT_TRACE"
    )

    observation = RuntimeObservation(
        run_id=run_id,
        source=source,
        command=tuple(command),
        timeout_seconds=timeout_seconds,
        status=status,
        exit_code=returncode,
        stdout=stdout,
        stderr=stderr,
        isolation="NONE",
        coverage=coverage,
        edges=tuple(sorted(edges_by_key.values(), key=lambda edge: edge.key)),
        effects=tuple(sorted(unique_effects.values(), key=lambda effect: (effect.actor, effect.kind, effect.target))),
        trace_files=len(trace_files),
        envelope_breaches=tuple(sorted(set(breaches))),
    )

    shutil.rmtree(trace_dir, ignore_errors=True)
    return observation
