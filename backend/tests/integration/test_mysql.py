import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.mark.mysql
def test_readiness_with_live_mysql():
    url = os.environ.get("MYSQL_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MYSQL_TEST_DATABASE_URL is required for the live MySQL test")
    config = Settings(_env_file=None, database_url=url, database_required=True)

    with TestClient(create_app(config)) as client:
        response = client.get("/health/db")
        assert response.status_code == 200, response.json()
        assert response.json() == {"status": "ok"}
