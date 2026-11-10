from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import DeclarativeBase, Session

from .errors import AppError


class Base(DeclarativeBase):
    pass


def create_database_engine(url: URL) -> Engine:
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


def get_session(request: Request) -> Iterator[Session]:
    factory = request.app.state.session_factory
    if factory is None:
        raise AppError(503, "database_not_configured", "Database is not configured.")
    with factory() as session:
        # The caller owns commit. Closing rolls back any unfinished transaction.
        yield session


DatabaseSession = Annotated[Session, Depends(get_session)]
