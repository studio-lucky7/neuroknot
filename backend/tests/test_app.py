import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import DatabaseSession
from app.errors import ErrorResponse
from app.main import create_app


def offline_app():
    return create_app(Settings(_env_file=None, database_url=None, database_required=False))


@pytest.mark.parametrize("extra_router", [False, True], ids=["foundation", "with-slice-router"])
def test_health_and_openapi_work_without_mysql(extra_router):
    application = offline_app()
    if extra_router:
        router = APIRouter()

        @router.get("/router-test")
        def additional_health() -> dict:
            return {"status": "test-router"}

        application.include_router(router)

    with TestClient(application) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
        assert {"/health", "/health/db"} <= set(schema["paths"])
        if extra_router:
            assert "/router-test" in schema["paths"]
            assert client.get("/router-test").json() == {"status": "test-router"}
        assert schema["paths"]["/health/db"]["get"]["responses"]["503"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse",
        }
        response = client.get("/health/db")
        assert response.status_code == 503
        assert response.json()["code"] == "database_not_configured"


def test_http_and_pydantic_errors_use_common_shape_without_echoing_inputs():
    application = offline_app()

    class Payload(BaseModel):
        count: int

    @application.post("/validation-test", response_model=Payload, responses={422: {"model": ErrorResponse}})
    def validate(payload: Payload) -> Payload:
        return payload

    with TestClient(application) as client:
        assert client.post("/validation-test", json={"count": 2}).json() == {"count": 2}
        invalid = client.post("/validation-test", json={"count": "private-input"})
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "validation_error"
        assert invalid.json()["issues"][0]["location"] == ["body", "count"]
        assert "private-input" not in invalid.text
        not_found = client.get("/missing")
        assert not_found.status_code == 404
        assert not_found.json()["code"] == "http_error"
        method_error = client.post("/health")
        assert method_error.status_code == 405
        assert method_error.headers["allow"] == "GET"


def test_database_errors_return_safe_readiness_status():
    class UnavailableSession(Session):
        def execute(self, *args, **kwargs):
            raise SQLAlchemyError("private-driver-detail")

    application = offline_app()
    with TestClient(application) as client:
        application.state.session_factory = sessionmaker(class_=UnavailableSession)
        response = client.get("/health/db")
        assert response.status_code == 503
        assert response.json()["code"] == "database_unavailable"
        assert "private-driver-detail" not in response.text


def test_invalid_response_uses_safe_internal_error():
    application = offline_app()

    class Payload(BaseModel):
        count: int

    @application.get("/response-test", response_model=Payload)
    def invalid_response() -> dict:
        return {"count": "private-response"}

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/response-test")
        assert response.status_code == 500
        assert response.json() == {"code": "internal_error", "message": "Internal server error."}


def test_request_sessions_close_and_roll_back_uncommitted_work():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    application = offline_app()
    closed_sessions = []

    class TrackedSession(Session):
        def close(self):
            closed_sessions.append(self)
            super().close()

    @application.post("/session-test")
    def insert(session: DatabaseSession) -> dict:
        session.execute(text("INSERT INTO sample VALUES (1)"))
        return {"inside_transaction": session.execute(text("SELECT COUNT(*) FROM sample")).scalar_one()}

    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE sample (value INTEGER)"))
        with TestClient(application) as client:
            application.state.session_factory = sessionmaker(bind=engine, class_=TrackedSession)
            assert client.post("/session-test").json() == {"inside_transaction": 1}
            assert client.get("/health/db").json() == {"status": "ok"}
        assert len(closed_sessions) == 2
        assert closed_sessions[0] is not closed_sessions[1]
        with engine.connect() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM sample")).scalar_one() == 0
    finally:
        engine.dispose()
