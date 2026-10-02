from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .models import SourceIdentity

_COMMON_EXCLUDES = {".git", ".venv", "venv", "node_modules", ".strawberry", "dist", "build", "__pycache__"}


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True,
            timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _internal_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized == ".strawberry" or normalized.startswith(".strawberry/")


def _fallback_snapshot(root: Path) -> str:
    digest = hashlib.sha256()
    files = list(root.rglob("*.py"))
    config = root / "strawberry.toml"
    if config.exists():
        files.append(config)
    for file in sorted(set(files)):
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
    if not head:
        return _fallback_snapshot(root)
    digest = hashlib.sha256()
    digest.update(head.encode("utf-8"))
    diff = _git(root, "diff", "--binary", "HEAD", "--", ".", ":(exclude).strawberry/**") or ""
    digest.update(diff.encode("utf-8", errors="replace"))
    untracked = _git(root, "ls-files", "--others", "--exclude-standard") or ""
    for rel in sorted(line for line in untracked.splitlines() if line.strip() and not _internal_path(line)):
        digest.update(rel.encode("utf-8"))
        try:
            digest.update((root / rel).read_bytes())
        except OSError:
            pass
    if porcelain:
        filtered = "\n".join(
            line for line in porcelain.splitlines()
            if len(line) >= 4 and not _internal_path(line[3:].strip())
        )
        digest.update(filtered.encode("utf-8", errors="replace"))
    return digest.hexdigest()


def source_identity(root: Path) -> SourceIdentity:
    head = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "branch", "--show-current")
    porcelain = _git(root, "status", "--porcelain")
    dirty_files: tuple[str, ...] = ()
    dirty = False
    if porcelain is not None:
        lines = [
            line for line in porcelain.splitlines()
            if line.strip() and len(line) >= 4 and not _internal_path(line[3:].strip())
        ]
        dirty = bool(lines)
        dirty_files = tuple(sorted(line[3:].strip() for line in lines))
    return SourceIdentity(
        root=str(root.resolve()), git_head=head or None, branch=branch or None,
        dirty=dirty, dirty_files=dirty_files,
        snapshot_id=_snapshot_id(root, head or None, porcelain),
    )
