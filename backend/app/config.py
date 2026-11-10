from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


def _mysql_url(value: SecretStr) -> URL:
    try:
        url = make_url(value.get_secret_value())
    except (ArgumentError, ValueError):
        raise ValueError("DATABASE_URL must be a valid MySQL URL") from None
    if url.drivername not in {"mysql", "mysql+pymysql"}:
        raise ValueError("DATABASE_URL must use mysql or mysql+pymysql")
    if not (url.username and url.host and url.database) or (url.port is not None and not 1 <= url.port <= 65535):
        raise ValueError("DATABASE_URL must include a username, host and database, with a valid port if set")
    url = url.set(drivername="mysql+pymysql")
    if "charset" not in url.query:
        url = url.update_query_dict({"charset": "utf8mb4"})
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: SecretStr | None = None
    database_required: bool = False

    @field_validator("database_url")
    @classmethod
    def validate_mysql_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            _mysql_url(value)
        return value

    @model_validator(mode="after")
    def validate_required_database(self) -> "Settings":
        if self.database_required and self.database_url is None:
            raise ValueError("DATABASE_URL is required when DATABASE_REQUIRED is enabled")
        return self

    def mysql_url(self) -> URL:
        if self.database_url is None:
            raise ValueError("DATABASE_URL is required for database operations")
        return _mysql_url(self.database_url)
