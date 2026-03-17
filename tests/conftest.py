from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption("--base-url", action="store", default="http://localhost:8000")


@pytest.fixture(scope="session")
def base_url(pytestconfig):
    return pytestconfig.getoption("base_url").rstrip("/")
