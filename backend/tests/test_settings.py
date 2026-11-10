import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


def test_mysql_settings_read_environment_without_disclosing_password(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://test:p%40ss%25@localhost:3306/neuroknot")
    monkeypatch.setenv("DATABASE_REQUIRED", "true")
    settings = Settings(_env_file=None)
    url = settings.mysql_url()

    assert settings.database_required is True
    assert url.drivername == "mysql+pymysql"
    assert (url.host, url.port, url.database, url.password) == ("localhost", 3306, "neuroknot", "p@ss%")
    assert url.query["charset"] == "utf8mb4"
    assert "p%40ss" not in repr(settings)
    assert "p@ss" not in repr(url)


def test_database_required_without_url_fails_startup(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_REQUIRED", "true")
    monkeypatch.setattr("app.main.Settings", lambda: Settings(_env_file=None))

    with pytest.raises(ValidationError, match="DATABASE_URL is required"):
        with TestClient(create_app()):
            pass


def test_environment_overrides_dotenv_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=mysql://test@localhost/from_file\nDATABASE_REQUIRED=true\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "mysql://test@localhost/from_process")
    monkeypatch.delenv("DATABASE_REQUIRED", raising=False)

    settings = Settings(_env_file=env_file)
    assert settings.database_required is True
    assert settings.mysql_url().database == "from_process"


@pytest.mark.parametrize(
    "url",
    ["postgresql://test:dummy-secret@localhost/db", "mysql://test:dummy-secret@localhost:bad/db", "mysql://test@localhost"],
)
def test_invalid_database_url_has_safe_diagnostic(url):
    with pytest.raises(ValidationError, match="DATABASE_URL") as error:
        Settings(_env_file=None, database_url=url)
    assert "dummy-secret" not in str(error.value)
