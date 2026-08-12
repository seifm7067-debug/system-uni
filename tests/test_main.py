import pytest
from app.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole
from app.security.jwt import create_access_token
from app.security.password import hash_password
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    admin = User(
        username="admin_test",
        email="admin@test.com",
        password_hash=hash_password("adminpass123"),
        role=UserRole.ADMIN,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    yield db
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["components"]["postgres"] == "healthy"


def test_register_and_login():
    reg_resp = client.post(
        "/users/register",
        json={
            "username": "student1",
            "email": "student1@test.com",
            "password": "password123",
        },
    )
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    assert data["username"] == "student1"
    assert data["role"] == "guest"

    login_resp = client.post(
        "/users/login",
        json={"email": "student1@test.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data


def test_get_current_user_me():
    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = client.get("/users/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@test.com"


def test_colleges_pagination():
    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/colleges/",
        json={"name": "Engineering College", "code": "ENG"},
        headers=headers,
    )
    assert create_resp.status_code == 201

    get_resp = client.get("/colleges/?skip=0&limit=10", headers=headers)
    assert get_resp.status_code == 200
    colleges = get_resp.json()
    assert len(colleges) == 1
    assert colleges[0]["code"] == "ENG"


def test_unauthenticated_access():
    resp = client.get("/colleges/")
    assert resp.status_code == 401
