from __future__ import annotations

import subprocess
from pathlib import Path

from .models import SourceIdentity


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
    )
