from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db import Base


def test_alembic_has_one_head_and_generates_mysql_sql_offline(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://example:placeholder@127.0.0.1/neuroknot")
    monkeypatch.setenv("DATABASE_REQUIRED", "false")
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)

    assert ScriptDirectory.from_config(config).get_heads() == ["0001_foundation"]
    assert not Base.metadata.tables
    command.upgrade(config, "head", sql=True)

    sql = output.getvalue()
    assert "CREATE TABLE alembic_version" in sql
    assert "0001_foundation" in sql
    assert sql.count("CREATE TABLE") == 1
