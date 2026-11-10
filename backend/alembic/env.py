from alembic import context
from sqlalchemy import create_engine, pool

from app.config import Settings
from app.db import Base


def run_migrations() -> None:
    url = Settings().mysql_url()
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(url, poolclass=pool.NullPool, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
