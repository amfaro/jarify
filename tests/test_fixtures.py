"""Snapshot/fixture-based formatter tests.

Each subdirectory under tests/fixtures/ can contain pairs of:
  <name>.input.sql   — raw SQL to format
  <name>.expected.sql — the expected formatted output

Running pytest --snapshot-update will regenerate all expected files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarify.config import JarifyConfig
from jarify.formatter import format_sql

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _collect_fixture_pairs() -> list[tuple[str, Path, Path]]:
    """Find all (test_id, input_path, expected_path) tuples under fixtures/."""
    pairs: list[tuple[str, Path, Path]] = []
    for input_file in sorted(FIXTURES_DIR.rglob("*.input.sql")):
        stem = input_file.name[: -len(".input.sql")]
        expected_file = input_file.parent / f"{stem}.expected.sql"
        test_id = f"{input_file.parent.name}/{stem}"
        pairs.append((test_id, input_file, expected_file))
    return pairs


def _is_sqlmesh_fixture(path: Path) -> bool:
    return path.relative_to(FIXTURES_DIR).parts[0] == "sqlmesh"


@pytest.mark.parametrize(
    "test_id,input_path,expected_path",
    [pytest.param(tid, inp, exp, id=tid) for tid, inp, exp in _collect_fixture_pairs()],
)
def test_format_fixture(
    test_id: str,
    input_path: Path,
    expected_path: Path,
    update_snapshots: bool,
) -> None:
    """Format input SQL and compare to the expected snapshot."""
    config = JarifyConfig()
    sql = input_path.read_text()
    result, warnings = format_sql(sql, config)
    if _is_sqlmesh_fixture(input_path):
        assert not warnings, f"SQLMesh fixture emitted format warnings: {[str(w) for w in warnings]}"

    if update_snapshots:
        expected_path.write_text(result)
        pytest.skip(f"Snapshot updated: {expected_path.name}")

    if not expected_path.exists():
        pytest.fail(
            f"No expected file found: {expected_path}\n"
            f"Run with --snapshot-update to generate it.\n\n"
            f"Actual output:\n{result}"
        )

    expected = expected_path.read_text()
    assert result == expected, f"\n--- expected ({expected_path.name}) ---\n{expected}\n--- actual ---\n{result}"


def test_format_idempotent(request: pytest.FixtureRequest) -> None:
    """Formatting an already-formatted SQL string should be a no-op."""
    config = JarifyConfig()
    for _, _input_path, expected_path in _collect_fixture_pairs():
        if not expected_path.exists():
            continue
        already_formatted = expected_path.read_text().rstrip("\n") + "\n"
        result, warnings = format_sql(already_formatted, config)
        if _is_sqlmesh_fixture(expected_path):
            assert not warnings, f"SQLMesh fixture emitted format warnings: {[str(w) for w in warnings]}"
        assert result == already_formatted, (
            f"Idempotency failure for {expected_path.name}:\n"
            f"--- first pass output ---\n{already_formatted}"
            f"--- second pass output ---\n{result}"
        )
