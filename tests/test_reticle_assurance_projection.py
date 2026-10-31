from dataclasses import replace

from strawberryme.core import StrawberryCore


def _receipt(snapshot: str, verdict: str = "PASS") -> dict:
    return {
        "kind": "EXTERNAL_RUNTIME_VERIFICATION",
        "donor": "reticlehq/reticle",
        "status": verdict,
        "source_snapshot": snapshot,
        "assertion_sha256": "a" * 64,
        "output_sha256": "b" * 64,
    }


def test_no_external_assertion_never_claims_acceptance(tmp_path):
    core = StrawberryCore(tmp_path)
    result = core.verify()
    assert result["external_ui"]["assertion_verdict"] == "NOT_CHECKED"
    assert result["external_ui"]["accepted_completion"] is False
    assert result["external_ui"]["deployment_provenance_verified"] is False


def test_explicit_external_ui_evidence_current_stale_and_unattested(tmp_path):
    core = StrawberryCore(tmp_path)
    architecture = core.map()
    source = architecture.source
    core.store.append_verification(_receipt("s1"))

    architecture.source = replace(source, git_head="git123", snapshot_id="s1")
    status = core._external_ui_evidence(architecture)
    assert status["assertion_verdict"] == "PASS"
    assert status["source_binding"] == "CURRENT"
    assert status["accepted_completion"] is False

    architecture.source = replace(source, git_head="git123", snapshot_id="s2")
    assert core._external_ui_evidence(architecture)["source_binding"] == "STALE"

    architecture.source = replace(source, git_head=None, snapshot_id="s1")
    assert core._external_ui_evidence(architecture)["source_binding"] == "UNATTESTED_SOURCE"


def test_verify_shows_reticle_but_does_not_override_strict_existing_evidence(tmp_path):
    core = StrawberryCore(tmp_path)
    snapshot = core.map().source.snapshot_id
    core.store.append_verification(_receipt(snapshot))
    result = core.verify()
    assert result["external_ui"]["assertion_verdict"] == "PASS"
    assert result["external_ui"]["source_binding"] == "UNATTESTED_SOURCE"
    assert result["external_ui"]["accepted_completion"] is False
    assert result["boundary"]["conformance"] == "NOT_CONFIGURED"
    assert result["drift"] == "UNKNOWN"


def test_inconclusive_external_receipt_never_raises_assurance(tmp_path):
    core = StrawberryCore(tmp_path)
    core.store.append_verification(_receipt("irrelevant", verdict="INCONCLUSIVE"))
    result = core.status()["external_ui"]
    assert result["assertion_verdict"] == "INCONCLUSIVE"
    assert result["accepted_completion"] is False
