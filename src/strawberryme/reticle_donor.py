"""Deterministic Reticle verification donor, reusing StrawberryMe evidence history.

Donor: https://github.com/reticlehq/reticle
The Reticle CLI is invoked only when the operator explicitly requests a
single assertion. No Reticle daemon, cloud sync or JS injection is installed.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from .store import Store


def verify_reticle(
    root: Path,
    url: str,
    expect_file: Path,
    *,
    source_snapshot: str | None,
    timeout_seconds: int = 120,
    executable: str = "reticle",
) -> dict:
    """Save a source-bound, bounded verdict. Unknown is never promoted to PASS."""
    root = root.resolve()
    spec = urlsplit(url)
    if (
        spec.scheme != "http" or spec.hostname not in {"127.0.0.1", "::1", "localhost"}
        or spec.username or spec.password or spec.fragment
    ):
        raise ValueError("Reticle verification requires an explicit loopback HTTP app")
    try:
        port = spec.port
    except ValueError as exc:
        raise ValueError("invalid Reticle port") from exc
    if port is None or not 1 <= port <= 65535:
        raise ValueError("Reticle verification requires a concrete local port")
    assertion = expect_file.resolve()
    if not assertion.is_relative_to(root) or not assertion.is_file():
        raise ValueError("expect-file must exist beneath the selected repository")
    if assertion.stat().st_size > 65536:
        raise ValueError("expect-file exceeds 64 KiB")
    with assertion.open("r", encoding="utf-8") as handle:
        check = json.load(handle)
    if not isinstance(check, dict) or not check:
        raise ValueError("expect-file must contain one JSON assertion object")
    if not 1 <= timeout_seconds <= 600:
        raise ValueError("timeout_seconds must be between 1 and 600")

    args = [executable, "verify", url, "--expect-file", str(assertion)]
    status, reason, exit_code = "INCONCLUSIVE", "UNVERIFIED", None
    output_sha256 = None
    try:
        result = subprocess.run(
            args, cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout_seconds, check=False,
        )
        exit_code = result.returncode
        # Upstream contract: exit 0 only if a requested assertion is verified YES.
        status = "PASS" if exit_code == 0 else "INCONCLUSIVE"
        reason = "ASSERTION_VERIFIED" if status == "PASS" else "FAILED_OR_UNKNOWN"
        output_sha256 = hashlib.sha256(
            (result.stdout + "\n" + result.stderr).encode("utf-8")
        ).hexdigest()
    except FileNotFoundError:
        reason = "RETICLE_NOT_INSTALLED"
    except subprocess.TimeoutExpired:
        reason = "RETICLE_TIMEOUT"
    except OSError:
        reason = "RETICLE_EXECUTION_ERROR"

    # No raw URL/query, report text, page content, cookies, or user data in
    # StrawberryMe's SQLite evidence history.
    receipt = {
        "kind": "EXTERNAL_RUNTIME_VERIFICATION",
        "donor": "reticlehq/reticle",
        "status": status,
        "reason": reason,
        "source_snapshot": source_snapshot,
        "assertion_sha256": hashlib.sha256(assertion.read_bytes()).hexdigest(),
        "output_sha256": output_sha256,
        "exit_code": exit_code,
        "target": f"http://{spec.hostname}:{port}",
        "automated": False,
    }
    Store(root).append_verification(receipt)
    return receipt
