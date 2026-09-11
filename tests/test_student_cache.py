from unittest.mock import MagicMock, patch

import pytest
from app.crud.student import (
    create_student,
    delete_student,
    link_student_to_user,
    update_student,
)
from app.database import Base
from app.models import College, Department, User
from app.models.user import UserRole
from app.schemas.student import StudentCreate, StudentUpdate
from app.security.password import hash_password
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


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Create college & department
    college = College(name="Engineering", code="ENG")
    db.add(college)
    db.commit()
    db.refresh(college)

    department = Department(name="Computer Science", code="CS", college_id=college.id)
    db.add(department)
    db.commit()
    db.refresh(department)

    yield db, department

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_update_student_invalidates_cache(db_session):
    db, department = db_session

    student = create_student(
        db,
        StudentCreate(
            name="John Doe",
            email="john@example.com",
            age=20,
            department_id=department.id,
        ),
    )

    mock_redis = MagicMock()
    with patch("app.crud.student.get_redis_client", return_value=mock_redis):
        update_data = StudentUpdate(name="John Updated")
        updated = update_student(db, update_data, student.id)
        assert updated.name == "John Updated"
        mock_redis.delete.assert_called_once_with(f"student:{student.id}")


def test_delete_student_invalidates_cache(db_session):
    db, department = db_session

    student = create_student(
        db,
        StudentCreate(
            name="Jane Doe",
            email="jane@example.com",
            age=22,
            department_id=department.id,
        ),
    )

    mock_redis = MagicMock()
    with patch("app.crud.student.get_redis_client", return_value=mock_redis):
        result = delete_student(db, student.id)
        assert result == {"message": "Student deleted successfully"}
        mock_redis.delete.assert_called_once_with(f"student:{student.id}")


def test_link_student_to_user_invalidates_cache(db_session):
    db, department = db_session

    student = create_student(
        db,
        StudentCreate(
            name="Alice",
            email="alice@example.com",
            age=21,
            department_id=department.id,
        ),
    )
    user = User(
        username="alice_user",
        email="alice@user.com",
        password_hash=hash_password("secret123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    mock_redis = MagicMock()
    with patch("app.crud.student.get_redis_client", return_value=mock_redis):
        linked = link_student_to_user(db, student.id, user.id)
        assert linked.user_id == user.id
        mock_redis.delete.assert_called_once_with(f"student:{student.id}")


def test_student_mutations_work_when_redis_unavailable(db_session):
    db, department = db_session

    student = create_student(
        db,
        StudentCreate(
            name="Bob",
            email="bob@example.com",
            age=23,
            department_id=department.id,
        ),
    )

    with patch("app.crud.student.get_redis_client", return_value=None):
        updated = update_student(db, StudentUpdate(name="Bob Modified"), student.id)
        assert updated.name == "Bob Modified"

        result = delete_student(db, student.id)
        assert result == {"message": "Student deleted successfully"}
