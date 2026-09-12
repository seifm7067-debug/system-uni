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


def test_cache_is_invalidated_only_after_commit(db_session):
    """A rollback (409) must not clear a still-valid cache entry."""
    db, department = db_session

    student = create_student(
        db,
        StudentCreate(
            name="Carol",
            email="carol@example.com",
            age=20,
            department_id=department.id,
        ),
    )
    other = create_student(
        db,
        StudentCreate(
            name="Erin",
            email="erin@example.com",
            age=21,
            department_id=department.id,
        ),
    )

    mock_redis = MagicMock()
    with patch("app.crud.student.get_redis_client", return_value=mock_redis):
        from fastapi import HTTPException

        update = StudentUpdate(email=other.email)  # duplicate email -> 409
        with pytest.raises(HTTPException) as exc_info:
            update_student(db, update, student.id)
        assert exc_info.value.status_code == 409

        # The failed update must not have touched the cache.
        mock_redis.delete.assert_not_called()


def test_read_student_survives_redis_dying_mid_request(db_session):
    """Redis failing after startup must degrade to a direct DB read, not a 500."""
    from app.crud.student import read_student
    from app.schemas.student import StudentResponseSchema

    db, department = db_session
    student = create_student(
        db,
        StudentCreate(
            name="Dave",
            email="dave@example.com",
            age=20,
            department_id=department.id,
        ),
    )
    admin = User(
        username="dave_admin",
        email="dave_admin@example.com",
        password_hash=hash_password("secret123"),
        role=UserRole.ADMIN,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    broken_redis = MagicMock()
    broken_redis.get.side_effect = ConnectionError("redis went away")
    broken_redis.set.side_effect = ConnectionError("redis went away")

    with patch("app.crud.student.get_redis_client", return_value=broken_redis):
        response = read_student(db, student.id, admin)

    assert isinstance(response, StudentResponseSchema)
    assert response.name == "Dave"
