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
