"""pytest configuration and shared fixtures."""

from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-fixtures",
        action="store_true",
        default=False,
        help="Regenerate all .expected.sql snapshot files.",
    )


@pytest.fixture(autouse=True)
def isolated_global_config_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep developer-machine global Jarify config out of tests."""
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg-config"
    home.mkdir()
    xdg_config_home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_home))


@pytest.fixture
def update_snapshots(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-fixtures"))
