from sqlalchemy.orm import Session

from app.models import College


def test_health_ok(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["app"] == "Sankalp AI"


def test_health_reports_database_error(client):
    from app.core.database import get_db
    from app.main import app

    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("database is down")

    def broken_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "degraded"
    assert res.json()["database"] == "error"


def test_cors_allows_frontend_origin(client):
    res = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_can_save_and_read_a_college(db_session: Session):
    db_session.add(College(name="Test Polytechnic", city="Ranchi", state="Jharkhand", code="TP01"))
    db_session.commit()
    saved = db_session.query(College).filter_by(code="TP01").one()
    assert saved.name == "Test Polytechnic"
    assert saved.created_at is not None
