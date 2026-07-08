import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    """API client backed by a throwaway workspace root."""
    with tempfile.TemporaryDirectory() as home:
        monkeypatch.setenv("OZIMUT_HOME", home)
        from ozimut.server import create_app

        with TestClient(create_app()) as c:
            yield c
