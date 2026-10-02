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
