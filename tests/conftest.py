import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def tmp_workspace(monkeypatch):
    """A throwaway workspace root — for engine tests that read/write settings."""
    with tempfile.TemporaryDirectory() as home:
        monkeypatch.setenv("AZIMUT_HOME", home)
        yield home


@pytest.fixture()
def client(monkeypatch):
    """API client backed by a throwaway workspace root."""
    with tempfile.TemporaryDirectory() as home:
        monkeypatch.setenv("AZIMUT_HOME", home)
        from azimut.server import create_app

        with TestClient(create_app()) as c:
            yield c
