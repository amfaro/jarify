"""pytest configuration and shared fixtures."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-fixtures",
        action="store_true",
        default=False,
        help="Regenerate all .expected.sql snapshot files.",
    )


@pytest.fixture
def update_snapshots(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-fixtures"))
