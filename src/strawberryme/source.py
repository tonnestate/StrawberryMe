from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .models import SourceIdentity


_COMMON_EXCLUDES = {".git", ".venv", "venv", "node_modules", ".strawberry", "dist", "build", "__pycache__"}


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _fallback_python_snapshot(root: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(root.rglob("*.py")):
        try:
            rel = file.relative_to(root)
        except ValueError:
            continue
        if any(part in _COMMON_EXCLUDES for part in rel.parts):
            continue
        digest.update(rel.as_posix().encode("utf-8"))
        try:
            digest.update(file.read_bytes())
        except OSError:
            continue
    return digest.hexdigest()


def _snapshot_id(root: Path, head: str | None, porcelain: str | None) -> str:
    if head:
        digest = hashlib.sha256()
        digest.update(head.encode("utf-8"))
        diff = _git(root, "diff", "--binary", "HEAD") or ""
        digest.update(diff.encode("utf-8", errors="replace"))
        untracked = _git(root, "ls-files", "--others", "--exclude-standard") or ""
        for rel in sorted(line for line in untracked.splitlines() if line.strip()):
            digest.update(rel.encode("utf-8"))
            path = root / rel
            try:
                digest.update(path.read_bytes())
            except OSError:
                pass
        if porcelain:
            digest.update(porcelain.encode("utf-8", errors="replace"))
        return digest.hexdigest()
    return _fallback_python_snapshot(root)


def source_identity(root: Path) -> SourceIdentity:
    head = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "branch", "--show-current")
    porcelain = _git(root, "status", "--porcelain")
    dirty_files: tuple[str, ...] = ()
    dirty = False
    if porcelain is not None:
        lines = [line for line in porcelain.splitlines() if line.strip()]
        dirty = bool(lines)
        dirty_files = tuple(sorted(line[3:].strip() for line in lines if len(line) >= 4))
    return SourceIdentity(
        root=str(root.resolve()),
        git_head=head or None,
        branch=branch or None,
        dirty=dirty,
        dirty_files=dirty_files,
        snapshot_id=_snapshot_id(root, head or None, porcelain),
    )
