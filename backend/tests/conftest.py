import os

# Use a throwaway in-memory database for tests, before the app is imported.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["BCRYPT_ROUNDS"] = "4"  # fast hashing, tests only
os.environ["SUBMIT_COOLDOWN_SECONDS"] = "0"  # tests that need the cooldown turn it on themselves
os.environ["RUN_COOLDOWN_SECONDS"] = "0"

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401,E402
from app.core.database import Base, enable_sqlite_foreign_keys, get_db, get_session_factory  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import College, Role, User  # noqa: E402
from app.routers.submissions import judge_dependency  # noqa: E402
from app.services.finalizer import optional_judge  # noqa: E402
from app.services.judge.base import JudgeJob, JudgeOutcome, RunStatus  # noqa: E402

PASSWORD = "password123"


class ScriptedJudge:
    """A fake judge for tests. Set .respond to decide what every job returns."""

    def __init__(self):
        self.jobs: list[JudgeJob] = []
        self.respond = lambda job: JudgeOutcome(status=RunStatus.ok, stdout="OK\n", time_ms=5, memory_kb=100)

    def run_jobs(self, jobs):
        self.jobs.extend(jobs)
        return [self.respond(job) for job in jobs]


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(engine)  # same rules as PostgreSQL
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def fake_judge():
    return ScriptedJudge()


@pytest.fixture()
def client(db_session, session_factory, fake_judge):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[judge_dependency] = lambda: fake_judge
    app.dependency_overrides[optional_judge] = lambda: fake_judge
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def make_college(db_session):
    def _make(code="COL1", name="Test Polytechnic"):
        college = College(name=name, city="Ranchi", state="Jharkhand", code=code)
        db_session.add(college)
        db_session.commit()
        return college

    return _make


@pytest.fixture()
def make_user(db_session):
    def _make(email, role, college=None, name=None, active=True):
        user = User(
            name=name or email.split("@")[0],
            email=email,
            password_hash=hash_password(PASSWORD),
            role=role.value if isinstance(role, Role) else role,
            college_id=college.id if college else None,
            is_active=active,
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _make


@pytest.fixture()
def login(client):
    """login(user_or_email) -> headers with a valid token."""

    def _login(user, password=PASSWORD):
        email = user if isinstance(user, str) else user.email
        res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    return _login


@pytest.fixture()
def world(make_college, make_user):
    """Two colleges, each with an admin, a teacher and a student, plus a super admin."""
    c1, c2 = make_college("COL1", "College One"), make_college("COL2", "College Two")
    return {
        "c1": c1,
        "c2": c2,
        "super": make_user("super@x.com", Role.super_admin),
        "admin1": make_user("admin1@x.com", Role.admin, c1),
        "teacher1": make_user("teacher1@x.com", Role.teacher, c1),
        "teacher1b": make_user("teacher1b@x.com", Role.teacher, c1),
        "student1": make_user("student1@x.com", Role.student, c1),
        "admin2": make_user("admin2@x.com", Role.admin, c2),
        "teacher2": make_user("teacher2@x.com", Role.teacher, c2),
        "student2": make_user("student2@x.com", Role.student, c2),
    }


class FakeClock:
    """Lets a test move through time: clock.advance(minutes=30)."""

    def __init__(self):
        self.now = datetime.now(timezone.utc).replace(microsecond=0)

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)

    def at(self, **kwargs):
        """A moment relative to now: clock.at(minutes=+90)."""
        return self.now + timedelta(**kwargs)


@pytest.fixture()
def clock(monkeypatch):
    from app.core import clock as clock_module

    fake = FakeClock()
    monkeypatch.setattr(clock_module, "utc_now", lambda: fake.now)
    return fake


@pytest.fixture()
def school(client, world, login, make_user, clock):
    """teacher1's batch (with student1 in it), a classmate NOT in the batch, and two problems."""
    from tests.helpers import create_problem

    teacher = login(world["teacher1"])
    batch = client.post("/api/v1/batches", headers=teacher, json={"name": "CSE Sem 3"}).json()
    client.post(f"/api/v1/batches/{batch['id']}/members", headers=teacher, json={"user_ids": [world["student1"].id]})
    outsider = make_user("outsider@x.com", Role.student, world["c1"], name="Olga Outsider")
    return {
        "world": world, "batch": batch, "teacher": teacher,
        "student": login(world["student1"]), "student_user": world["student1"],
        "outsider": login(outsider), "outsider_user": outsider,
        "admin": login(world["admin1"]),
        "p1": create_problem(client, teacher, title="Add two numbers"),
        "p2": create_problem(client, teacher, title="Add again"),
    }
