"""
Shared pytest fixtures.

Uses an in-memory SQLite database so no external services are needed.
The LLM and email services are mocked out entirely.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.role import Role, RoleKey
from app.models.user import User, UserStatus
from app.core.security import hash_password, create_access_token

SQLITE_URL = "sqlite://"  # pure in-memory

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Seed roles once per session via the fixture
    _seed_roles(session)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


def _seed_roles(session) -> None:
    for key, name in [(RoleKey.SUPER_ADMIN, "Super Admin"), (RoleKey.USER, "User")]:
        if not session.query(Role).filter(Role.key == key).one_or_none():
            session.add(Role(name=name, key=key))
    session.commit()


@pytest.fixture()
def client(db):
    """TestClient with the in-memory DB injected."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def make_user(db, *, email="user@example.com", name="Test User", role_key=RoleKey.USER, status=UserStatus.ACTIVE):
    role = db.query(Role).filter(Role.key == role_key).one()
    user = User(
        name=name,
        email=email,
        hashed_password=hash_password("Password1!"),
        status=status,
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_headers(user: User) -> dict:
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}
