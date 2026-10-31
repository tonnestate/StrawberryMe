from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from strawberryme.reticle_donor import verify_reticle
from strawberryme.store import Store


def _assertion(root: Path) -> Path:
    target = root / "assertion.json"
    target.write_text(json.dumps({
        "kind": "element",
        "query": {"role": "heading", "name": "Welcome"},
        "state": "visible",
    }), encoding="utf-8")
    return target


def test_upstream_reticle_exit_zero_is_source_bound_verified_evidence(tmp_path, monkeypatch):
    assertion = _assertion(tmp_path)
    commands = []
    def stub(args, **kwargs):
        commands.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="yes", stderr="")
    monkeypatch.setattr(subprocess, "run", stub)
    receipt = verify_reticle(tmp_path, "http://127.0.0.1:8765/path", assertion,
                             source_snapshot="git-sha-1")
    assert receipt["status"] == "PASS"
    assert receipt["source_snapshot"] == "git-sha-1"
    assert receipt["output_sha256"]
    command = commands[0][0]
    assert command[:4] == [
        "reticle", "verify", "http://127.0.0.1:8765/path", "--expect-file",
    ]
    assert Path(command[4]).name == "assertion.json"
    assert command[-2:] == ["--timeout", "120000"]
    assert not Path(command[4]).exists()  # private pinned copy cleaned up
    assert commands[0][1]["cwd"] == str(tmp_path)
    history = Store(tmp_path).verification_history()
    assert history[0] == receipt
    assert "yes" not in json.dumps(history)


@pytest.mark.parametrize("exit_code", [1, 2, 19])
def test_failed_or_unknown_reticle_verdict_never_passes(tmp_path, monkeypatch, exit_code):
    assertion = _assertion(tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=exit_code, stdout="unknown", stderr=""))
    receipt = verify_reticle(tmp_path, "http://localhost:8765/", assertion, source_snapshot="x")
    assert receipt["status"] == "INCONCLUSIVE"
    assert receipt["reason"] == "FAILED_OR_UNKNOWN"


def test_timeout_and_missing_cli_remain_inconclusive(tmp_path, monkeypatch):
    assertion = _assertion(tmp_path)
    for error, reason in [
        (FileNotFoundError("no reticle"), "RETICLE_NOT_INSTALLED"),
        (subprocess.TimeoutExpired("reticle", 120), "RETICLE_TIMEOUT"),
    ]:
        def fails(*args, **kwargs):
            raise error
        monkeypatch.setattr(subprocess, "run", fails)
        receipt = verify_reticle(tmp_path, "http://127.0.0.1:8765/", assertion, source_snapshot=None)
        assert receipt["status"] == "INCONCLUSIVE"
        assert receipt["reason"] == reason


@pytest.mark.parametrize("url", [
    "https://example.com", "http://example.org:8080", "http://localhost",
    "http://user:pass@localhost:8080", "http://localhost:99999",
    "file:///etc/passwd", "http://127.0.0.1:8765/path#fragment",
])
def test_refuse_nonlocal_or_unbounded_targets(tmp_path, url):
    assertion = _assertion(tmp_path)
    with pytest.raises(ValueError):
        verify_reticle(tmp_path, url, assertion, source_snapshot=None)


def test_refuse_assertions_outside_root(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = _assertion(tmp_path)
    with pytest.raises(ValueError):
        verify_reticle(root, "http://localhost:8765", outside, source_snapshot=None)


def test_reject_invalid_single_assertion(tmp_path):
    assertion = tmp_path / "assertion.json"
    assertion.write_text("[]")
    with pytest.raises(ValueError):
        verify_reticle(tmp_path, "http://localhost:8765", assertion, source_snapshot=None)


def test_reticle_timeout_is_milliseconds_and_process_has_teardown_budget(tmp_path, monkeypatch):
    assertion = _assertion(tmp_path)
    seen = []
    def fake(args, **kwargs):
        seen.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="yes", stderr="")
    monkeypatch.setattr(subprocess, "run", fake)
    result = verify_reticle(tmp_path, "http://localhost:8765/", assertion,
                            source_snapshot="git", timeout_seconds=7)
    assert result["status"] == "PASS"
    assert seen[0][0][-2:] == ["--timeout", "7000"]
    assert seen[0][1]["timeout"] == 12


def test_mutated_assertion_is_never_granted_a_pass(tmp_path, monkeypatch):
    assertion = _assertion(tmp_path)
    original = assertion.read_bytes()
    pinned_location = []
    def changing_check(command, **kwargs):
        snapshot = Path(command[4])
        pinned_location.append(snapshot)
        assert snapshot.read_bytes() == original
        assertion.write_text('{"kind":"text","contains":"Changed"}', encoding="utf-8")
        assert snapshot.read_bytes() == original
        return SimpleNamespace(returncode=0, stdout="verified yes", stderr="")
    monkeypatch.setattr(subprocess, "run", changing_check)
    receipt = verify_reticle(tmp_path, "http://localhost:8765/", assertion,
                             source_snapshot="checkout")
    assert receipt["status"] == "INCONCLUSIVE"
    assert receipt["reason"] == "ASSERTION_CHANGED_DURING_VERIFICATION"
    assert receipt["assertion_sha256"] == __import__("hashlib").sha256(original).hexdigest()
    assert not pinned_location[0].exists()
    assert Store(tmp_path).verification_history()[0] == receipt


def test_deleted_original_assertion_never_becomes_current_pass(tmp_path, monkeypatch):
    assertion = _assertion(tmp_path)
    def remove_during_verify(command, **kwargs):
        assert Path(command[4]).is_file()
        assertion.unlink()
        return SimpleNamespace(returncode=0, stdout="yes", stderr="")
    monkeypatch.setattr(subprocess, "run", remove_during_verify)
    receipt = verify_reticle(tmp_path, "http://localhost:8765/", assertion,
                             source_snapshot="checkout")
    assert receipt["status"] == "INCONCLUSIVE"
    assert receipt["reason"] == "ASSERTION_CHANGED_DURING_VERIFICATION"
