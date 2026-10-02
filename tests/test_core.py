from pathlib import Path

from strawberryme.core import StrawberryCore


def make_project(tmp_path: Path) -> None:
    (tmp_path / "app/application").mkdir(parents=True)
    (tmp_path / "app/db").mkdir(parents=True)
    (tmp_path / "app/application/service.py").write_text(
        "from app.db.repo import save\n\ndef handle(order: str) -> str:\n    save(order)\n    return order\n",
        encoding="utf-8",
    )
    (tmp_path / "app/db/repo.py").write_text(
        "def save(order: str) -> None:\n    return None\n",
        encoding="utf-8",
    )
    (tmp_path / "strawberry.toml").write_text(
        """
[boundaries.application]
paths = ["app/application/**"]
[boundaries.database]
paths = ["app/db/**"]
[[rules]]
source = "application"
target = "database"
mode = "forbid"
severity = "HARD"
""",
        encoding="utf-8",
    )


def test_cursor_exposes_io_and_dependency(tmp_path: Path) -> None:
    make_project(tmp_path)
    result = StrawberryCore(tmp_path).cursor("handle")
    assert result["status"] == "OK"
    assert result["inputs"] == ["order:str"]
    assert result["outputs"] == ["str"]


def test_architecture_violation_detected(tmp_path: Path) -> None:
    make_project(tmp_path)
    result = StrawberryCore(tmp_path).verify()
    assert result["boundary"]["status"] == "FAIL"
    assert result["boundary"]["violations"][0]["type"] == "FORBIDDEN_DEPENDENCY"


def test_expected_delta_roundtrip(tmp_path: Path) -> None:
    make_project(tmp_path)
    core = StrawberryCore(tmp_path)
    edge = "module:app.application.service|IMPORT|module:app.db.repo"
    pre = core.preflight(remove=[edge])
    assert pre["status"] in {"READY", "VIOLATION"}
    (tmp_path / "app/application/service.py").write_text(
        "def handle(order: str) -> str:\n    return order\n", encoding="utf-8"
    )
    verified = core.verify()
    assert verified["expected_delta"]["status"] == "PASS"


def test_runtime_observation_finds_dynamic_boundary_violation(tmp_path: Path) -> None:
    import sys

    (tmp_path / "app/application").mkdir(parents=True)
    (tmp_path / "app/db").mkdir(parents=True)
    (tmp_path / "app/application/service.py").write_text(
        "import importlib\n\ndef handle(order: str) -> str:\n    repo = importlib.import_module('app.db.repo')\n    getattr(repo, 'save')(order)\n    return order\n",
        encoding="utf-8",
    )
    (tmp_path / "app/db/repo.py").write_text(
        "def save(order: str) -> None:\n    return None\n",
        encoding="utf-8",
    )
    (tmp_path / "strawberry.toml").write_text(
        """
[boundaries.application]
paths = ["app/application/**"]
[boundaries.database]
paths = ["app/db/**"]
[[rules]]
source = "application"
target = "database"
mode = "forbid"
severity = "HARD"
""",
        encoding="utf-8",
    )

    core = StrawberryCore(tmp_path)
    static_verify = core.verify()
    assert static_verify["boundary"]["status"] == "PASS"

    observed = core.observe(
        [sys.executable, "-c", "from app.application.service import handle; handle('x')"]
    )
    assert observed["observed_map"]["coverage"] == "OBSERVED"
    assert observed["runtime_boundary"]["status"] == "FAIL"
    assert any(
        edge["source"] == "module:app.application.service"
        and edge["target"] == "module:app.db.repo"
        for edge in observed["observed_map"]["runtime_only_edges"]
    )
    assert observed["evidence_result"] == "VIOLATED_ON_TRACE"


def test_runtime_claim_bound_edge_assertions(tmp_path: Path) -> None:
    import sys

    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text(
        "from app.b import work\n\ndef run() -> None:\n    work()\n",
        encoding="utf-8",
    )
    (tmp_path / "app/b.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")

    edge = "module:app.a|CALL|module:app.b"
    observed = StrawberryCore(tmp_path).observe(
        [sys.executable, "-c", "from app.a import run; run()"],
        expected_runtime_edges=[edge],
    )
    assert observed["assertions"]["expected_runtime_edges"]["status"] == "PASS"
    assert observed["evidence_result"] == "SATISFIED_ON_TRACE"


def test_runtime_evidence_becomes_stale_after_source_change(tmp_path: Path) -> None:
    import sys

    (tmp_path / "app").mkdir()
    target = tmp_path / "app/a.py"
    target.write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    core = StrawberryCore(tmp_path)
    core.observe([sys.executable, "-c", "from app.a import run; run()"])
    target.write_text("def run() -> int:\n    return 2\n", encoding="utf-8")
    result = core.verify()
    assert result["runtime"]["status"] == "STALE"
    assert result["runtime"]["evidence_result"] == "INCONCLUSIVE"


def test_runtime_observation_records_file_write_effect(tmp_path: Path) -> None:
    import sys

    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text(
        "from pathlib import Path\n\ndef run() -> None:\n    Path('out.txt').write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )
    observed = StrawberryCore(tmp_path).observe(
        [sys.executable, "-c", "from app.a import run; run()"]
    )
    assert any(
        effect["actor"] == "module:app.a"
        and effect["kind"] == "FILE_WRITE"
        and effect["target"].endswith("out.txt")
        for effect in observed["observed_map"]["effects"]
    )


def test_assess_change_escalates_dynamic_code(tmp_path: Path) -> None:
    (tmp_path / "app/application").mkdir(parents=True)
    target = tmp_path / "app/application/service.py"
    target.write_text(
        "import importlib\n\ndef run(name: str):\n    return importlib.import_module(name)\n",
        encoding="utf-8",
    )
    (tmp_path / "strawberry.toml").write_text(
        '[boundaries.application]\npaths = ["app/application/**"]\n', encoding="utf-8"
    )
    result = StrawberryCore(tmp_path).assess_change(paths=["app/application/service.py"])
    assert result["risk"] == "HIGH"
    assert "DYNAMIC_BEHAVIOR_SIGNAL" in result["reasons"]
    assert result["recommended_path"] == "MINIMAL_RUNTIME_PROBE"


def test_probe_plan_compiles_safe_execution_envelope(tmp_path: Path) -> None:
    import sys

    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    core = StrawberryCore(tmp_path)
    planned = core.probe_plan(
        [sys.executable, "-c", "from app.a import run; run()"],
        paths=["app/a.py"],
    )
    assert planned["status"] == "READY"
    envelope = planned["plan"]["envelope"]
    assert envelope["network"] == "DENY"
    assert envelope["process_spawn"] == "DENY"
    assert envelope["filesystem"] == "TEMP_WRITE"
    assert envelope["source_snapshot"]


def test_probe_run_rejects_stale_plan(tmp_path: Path) -> None:
    import sys

    (tmp_path / "app").mkdir()
    target = tmp_path / "app/a.py"
    target.write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    core = StrawberryCore(tmp_path)
    planned = core.probe_plan([sys.executable, "-c", "from app.a import run; run()"], paths=["app/a.py"])
    plan_id = planned["plan"]["plan_id"]
    target.write_text("def run() -> int:\n    return 2\n", encoding="utf-8")
    result = core.probe_run(plan_id)
    assert result["status"] == "STALE_PLAN"


def test_execution_envelope_blocks_project_write(tmp_path: Path) -> None:
    import sys

    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text(
        "from pathlib import Path\n\ndef run() -> None:\n    Path('forbidden.txt').write_text('x')\n",
        encoding="utf-8",
    )
    core = StrawberryCore(tmp_path)
    planned = core.probe_plan(
        [sys.executable, "-c", "from app.a import run; run()"],
        paths=["app/a.py"],
        filesystem="TEMP_WRITE",
    )
    result = core.probe_run(planned["plan"]["plan_id"])
    assert result["results"][0]["evidence_result"] == "ENVELOPE_EXCEEDED"
    assert result["adaptive"]["next"] == "NEW_PLAN_REQUIRED"
    assert not (tmp_path / "forbidden.txt").exists()


def test_privileged_probe_requires_explicit_local_approval(tmp_path: Path) -> None:
    import sys

    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    core = StrawberryCore(tmp_path)
    planned = core.probe_plan(
        [sys.executable, "-c", "from app.a import run; run()"],
        paths=["app/a.py"],
        network="ALLOW",
    )
    assert planned["status"] == "APPROVAL_REQUIRED"
    plan_id = planned["plan"]["plan_id"]
    blocked = core.probe_run(plan_id)
    assert blocked["status"] == "APPROVAL_REQUIRED"
    approved = core.approve_probe_plan(plan_id, approved_by="test-user")
    assert approved["status"] == "APPROVED"
    completed = core.probe_run(plan_id)
    assert completed["status"] == "COMPLETE"


def test_adaptive_cursor_uses_risk_signals(tmp_path: Path) -> None:
    (tmp_path / "app/application").mkdir(parents=True)
    (tmp_path / "app/db").mkdir(parents=True)
    (tmp_path / "app/application/service.py").write_text(
        "import importlib\n\ndef handle() -> None:\n    importlib.import_module('app.db.repo')\n",
        encoding="utf-8",
    )
    (tmp_path / "app/db/repo.py").write_text("def save():\n    pass\n", encoding="utf-8")
    (tmp_path / "strawberry.toml").write_text(
        '[boundaries.application]\npaths=["app/application/**"]\n[boundaries.database]\npaths=["app/db/**"]\n',
        encoding="utf-8",
    )
    result = StrawberryCore(tmp_path).cursor("handle", adaptive=True)
    assert result["adaptive"] is True
    assert result["horizon"] == 2
    assert "DYNAMIC_BEHAVIOR_SIGNAL" in result["expansion_basis"]


def test_claude_stop_gate_blocks_static_violation(tmp_path: Path) -> None:
    from strawberryme.claude_hook import stop

    make_project(tmp_path)
    result = stop(StrawberryCore(tmp_path))
    assert result["decision"] == "block"


def test_provider_refuses_stronger_isolation_than_it_can_enforce(tmp_path: Path) -> None:
    import sys

    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    result = StrawberryCore(tmp_path).probe_plan(
        [sys.executable, "-c", "from app.a import run; run()"],
        paths=["app/a.py"],
        required_enforcement="OS_ISOLATED",
    )
    assert result["status"] == "PROVIDER_CAPABILITY_INSUFFICIENT"
    assert result["provider"]["provider_id"] == "local-python"
    assert result["provider"]["network_enforcement"] == "PYTHON_AUDIT"


def test_static_resolution_handles_import_aliases_and_relative_imports(tmp_path: Path) -> None:
    (tmp_path / "app/pkg").mkdir(parents=True)
    (tmp_path / "app/pkg/worker.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")
    (tmp_path / "app/pkg/a.py").write_text(
        "from .worker import work as run_work\n\ndef run() -> None:\n    run_work()\n",
        encoding="utf-8",
    )
    (tmp_path / "app/pkg/c.py").write_text(
        "import app.pkg.worker as worker\n\ndef run() -> None:\n    worker.work()\n",
        encoding="utf-8",
    )
    architecture = StrawberryCore(tmp_path).map()
    keys = {edge.key for edge in architecture.edges}
    assert "module:app.pkg.a|IMPORT|module:app.pkg.worker" in keys
    assert "module:app.pkg.a|CALL|symbol:app.pkg.worker.work" in keys
    assert "module:app.pkg.c|IMPORT|module:app.pkg.worker" in keys
    assert "module:app.pkg.c|CALL|symbol:app.pkg.worker.work" in keys


def test_dynamic_signals_are_ast_based_not_comment_substrings(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text(
        "# importlib.import_module('fake.module')\n"
        "import os\n\n"
        "def run() -> str:\n"
        "    return os.environ['MODE']\n",
        encoding="utf-8",
    )
    result = StrawberryCore(tmp_path).assess_change(paths=["app/a.py"])
    signals = {item["signal"] for item in result["dynamic_signals"]}
    assert "CONFIG_ACCESS" in signals
    assert "DYNAMIC_IMPORT" not in signals


def test_incremental_map_reuses_unchanged_files(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    first = tmp_path / "app/a.py"
    second = tmp_path / "app/b.py"
    first.write_text("def a() -> int:\n    return 1\n", encoding="utf-8")
    second.write_text("def b() -> int:\n    return 2\n", encoding="utf-8")
    core = StrawberryCore(tmp_path)
    initial = core.map()
    assert initial.scan_stats["parsed_files"] == 2
    cached = core.map()
    assert cached.scan_stats["reused_files"] == 2
    first.write_text("def a() -> int:\n    return 100\n", encoding="utf-8")
    changed = core.map()
    assert changed.scan_stats["parsed_files"] == 1
    assert changed.scan_stats["reused_files"] == 1


def test_history_reports_static_architecture_diff_between_verifications(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    source = tmp_path / "app/a.py"
    source.write_text("def run() -> None:\n    return None\n", encoding="utf-8")
    (tmp_path / "app/b.py").write_text("def work() -> None:\n    return None\n", encoding="utf-8")
    core = StrawberryCore(tmp_path)
    core.verify()
    source.write_text(
        "from app.b import work\n\ndef run() -> None:\n    work()\n",
        encoding="utf-8",
    )
    core.verify()
    history = core.evidence_history()
    diff = history["verifications"]["latest_architecture_diff"]
    assert diff is not None
    assert "module:app.a|IMPORT|module:app.b" in diff["added_static_edges"]
    assert "module:app.a|CALL|symbol:app.b.work" in diff["added_static_edges"]


def _git_init(root: Path) -> None:
    import subprocess
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Strawberry Test"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)


def test_git_snapshot_ignores_strawberry_state(tmp_path: Path) -> None:
    import sys
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    _git_init(tmp_path)
    core = StrawberryCore(tmp_path)
    planned = core.probe_plan([sys.executable, "-c", "from app.a import run; run()"], paths=["app/a.py"])
    before = planned["plan"]["envelope"]["source_snapshot"]
    result = core.probe_run(planned["plan"]["plan_id"])
    after = core.status()["source"]["snapshot_id"]
    assert result["status"] == "COMPLETE"
    assert before == after
    assert ".strawberry" not in core.status()["source"]["dirty_files"]


def test_map_cache_invalidates_when_config_changes(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("from app.b import work\nwork()\n", encoding="utf-8")
    (tmp_path / "app/b.py").write_text("def work():\n    pass\n", encoding="utf-8")
    cfg = tmp_path / "strawberry.toml"
    cfg.write_text('''[boundaries.application]\npaths=["app/a.py"]\n[boundaries.database]\npaths=["app/b.py"]\n[[rules]]\nsource="application"\ntarget="storage"\nmode="forbid"\nseverity="HARD"\n''', encoding="utf-8")
    core = StrawberryCore(tmp_path)
    assert core.verify()["boundary"]["status"] == "PASS"
    cfg.write_text('''[boundaries.application]\npaths=["app/a.py"]\n[boundaries.storage]\npaths=["app/b.py"]\n[[rules]]\nsource="application"\ntarget="storage"\nmode="forbid"\nseverity="HARD"\n''', encoding="utf-8")
    result = core.verify()
    assert result["boundary"]["status"] == "FAIL"


def test_envelope_blocks_os_open_and_strawberry_prefix_bypass(tmp_path: Path) -> None:
    import sys
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text(
        "import os\n\ndef run():\n    fd=os.open('.strawberry_evil.txt', os.O_WRONLY|os.O_CREAT); os.close(fd)\n",
        encoding="utf-8",
    )
    core = StrawberryCore(tmp_path)
    plan = core.probe_plan([sys.executable, "-c", "from app.a import run; run()"], paths=["app/a.py"])
    result = core.probe_run(plan["plan"]["plan_id"])
    assert result["results"][0]["evidence_result"] == "ENVELOPE_EXCEEDED"
    assert not (tmp_path / ".strawberry_evil.txt").exists()


def test_envelope_blocks_evidence_database_access(tmp_path: Path) -> None:
    import sys
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text(
        "import sqlite3\n\ndef run():\n    sqlite3.connect('.strawberry/strawberry.db').execute('DELETE FROM evidence_history')\n",
        encoding="utf-8",
    )
    core = StrawberryCore(tmp_path)
    plan = core.probe_plan([sys.executable, "-c", "from app.a import run; run()"], paths=["app/a.py"])
    result = core.probe_run(plan["plan"]["plan_id"])
    assert result["results"][0]["evidence_result"] == "ENVELOPE_EXCEEDED"


def test_envelope_blocks_posix_spawn_when_available(tmp_path: Path) -> None:
    import os, sys, pytest
    if not hasattr(os, "posix_spawn"):
        pytest.skip("posix_spawn unavailable")
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text(
        "import os,sys\n\ndef run():\n    os.posix_spawn(sys.executable,[sys.executable,'-c','pass'],os.environ.copy())\n",
        encoding="utf-8",
    )
    core = StrawberryCore(tmp_path)
    plan = core.probe_plan([sys.executable, "-c", "from app.a import run; run()"], paths=["app/a.py"])
    result = core.probe_run(plan["plan"]["plan_id"])
    assert result["results"][0]["evidence_result"] == "ENVELOPE_EXCEEDED"


def test_import_from_package_member_prefers_real_submodule(tmp_path: Path) -> None:
    (tmp_path / "app/db").mkdir(parents=True)
    (tmp_path / "app/service.py").write_text("from app.db import repo\nrepo.save()\n", encoding="utf-8")
    (tmp_path / "app/db/repo.py").write_text("def save():\n    pass\n", encoding="utf-8")
    edges = StrawberryCore(tmp_path).map().edges
    assert any(e.kind == "IMPORT" and e.target == "module:app.db.repo" for e in edges)
    assert any(e.kind == "CALL" and e.target == "symbol:app.db.repo.save" and e.resolution == "EXACT" for e in edges)


def test_dynamic_signals_resolve_aliases_and_ignore_literal_getattr(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text(
        "from importlib import import_module as load\nimport subprocess as sp\n\ndef run(name,obj):\n    load(name)\n    sp.run(['x'])\n    getattr(obj,'known')\n",
        encoding="utf-8",
    )
    signals = StrawberryCore(tmp_path).map().dynamic_signals
    kinds = {x["signal"] for x in signals}
    assert "DYNAMIC_IMPORT" in kinds
    assert "PROCESS_CREATION" in kinds
    assert "REFLECTIVE_ACCESS" not in kinds


def test_heuristic_call_resolution_is_marked(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("def run(obj):\n    obj.go()\n", encoding="utf-8")
    (tmp_path / "app/b.py").write_text("def go():\n    pass\n", encoding="utf-8")
    calls = [e for e in StrawberryCore(tmp_path).map().edges if e.kind == "CALL"]
    assert any(e.target == "symbol:app.b.go" and e.resolution == "HEURISTIC" for e in calls)


def test_compile_check_does_not_create_pycache(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("x=1\n", encoding="utf-8")
    result = StrawberryCore(tmp_path).verify()
    assert result["build"]["status"] == "PASS"
    assert not list(tmp_path.rglob("__pycache__"))


def test_claude_session_context_uses_additional_context(tmp_path: Path) -> None:
    from strawberryme.claude_hook import session_context
    (tmp_path / "app").mkdir(); (tmp_path / "app/a.py").write_text("x=1\n", encoding="utf-8")
    result = session_context(StrawberryCore(tmp_path))
    assert "systemMessage" not in result
    assert "additionalContext" in result["hookSpecificOutput"]


def test_claude_stop_pass_omits_approve_and_recursion_guard(tmp_path: Path) -> None:
    from strawberryme.claude_hook import stop
    (tmp_path / "app").mkdir(); (tmp_path / "app/a.py").write_text("x=1\n", encoding="utf-8")
    core = StrawberryCore(tmp_path)
    passed = stop(core, {})
    assert "decision" not in passed
    guarded = stop(core, {"stop_hook_active": True})
    assert "decision" not in guarded


def test_envelope_blocks_remove_and_rename(tmp_path: Path) -> None:
    import sys
    (tmp_path / "app").mkdir()
    victim = tmp_path / "victim.txt"; victim.write_text("keep", encoding="utf-8")
    (tmp_path / "app/a.py").write_text(
        "import os\n\ndef run():\n    os.rename('victim.txt','moved.txt')\n",
        encoding="utf-8",
    )
    core = StrawberryCore(tmp_path)
    plan = core.probe_plan([sys.executable, "-c", "from app.a import run; run()"], paths=["app/a.py"])
    result = core.probe_run(plan["plan"]["plan_id"])
    assert result["results"][0]["evidence_result"] == "ENVELOPE_EXCEEDED"
    assert victim.exists() and not (tmp_path / "moved.txt").exists()


def test_no_architecture_config_is_orientation_only_not_pass(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    core = StrawberryCore(tmp_path)
    status = core.status()
    assert status["architecture"]["mode"] == "ORIENTATION_ONLY"
    assert status["architecture"]["conformance"] == "NOT_CONFIGURED"
    verified = core.verify()
    assert verified["boundary"]["status"] == "NOT_EVALUATED"
    assert verified["boundary"]["conformance"] == "NOT_CONFIGURED"
    assert verified["drift"] == "UNKNOWN"


def test_partial_architecture_config_is_not_evaluated(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "strawberry.toml").write_text(
        '[boundaries.application]\npaths=["app/**"]\n', encoding="utf-8"
    )
    verified = StrawberryCore(tmp_path).verify()
    assert verified["boundary"]["status"] == "NOT_EVALUATED"
    assert verified["boundary"]["conformance"] == "INCOMPLETE_CONFIG"


def test_runtime_boundary_without_declared_policy_is_not_evaluated(tmp_path: Path) -> None:
    import sys
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("from app.b import work\n\ndef run():\n    work()\n", encoding="utf-8")
    (tmp_path / "app/b.py").write_text("def work():\n    return None\n", encoding="utf-8")
    edge = "module:app.a|CALL|module:app.b"
    observed = StrawberryCore(tmp_path).observe(
        [sys.executable, "-c", "from app.a import run; run()"],
        expected_runtime_edges=[edge],
    )
    assert observed["runtime_boundary"]["status"] == "NOT_EVALUATED"
    assert observed["runtime_boundary"]["conformance"] == "NOT_CONFIGURED"
    assert observed["assertions"]["expected_runtime_edges"]["status"] == "PASS"


def test_skill_compatibility_copy_is_byte_identical() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "SKILL.md").read_bytes() == (root / "skill/SKILL.md").read_bytes()
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "strawberry_probe_approve" in text


def test_readme_documents_complete_probe_mcp_flow() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "strawberry_probe_plan(" in readme
    assert "strawberry_probe_approve(" in readme
    assert "strawberry_probe_run(plan_id)" in readme
