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
