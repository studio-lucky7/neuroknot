from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from .config import Settings
from .db import create_database_engine
from .errors import register_error_handlers
from .routers.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        config = settings if settings is not None else Settings()
        engine = create_database_engine(config.mysql_url()) if config.database_url is not None else None
        application.state.session_factory = sessionmaker(bind=engine) if engine is not None else None
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    application = FastAPI(title="NeuroKnot API", lifespan=lifespan)
    register_error_handlers(application)
    application.include_router(health_router)
    return application


app = create_app()
