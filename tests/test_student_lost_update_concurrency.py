"""Concurrency & Consistency Integration Tests for Optimistic Locking & Lost Update Prevention.

This module tests that the system_uni project is now protected against the Lost Update
concurrency anomaly on the Student entity via SQLAlchemy Optimistic Locking (version_id_col).
"""

import threading

import pytest
from app.crud.student import update_student
from app.database import Base, SessionLocal, engine, get_db
from app.main import app
from app.models import (
    College,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Student,
    Teacher,
    User,
)
from app.models.user import UserRole
from app.schemas import StudentUpdate
from app.security.jwt import create_access_token
from app.security.password import hash_password
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError


def override_concurrency_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def student_optimistic_locking_setup():
    """Set up clean database tables and a student record with initial name 'Ahmed' and version_id 1."""
    prev_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_concurrency_get_db
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Clean existing test data in reverse foreign-key order
        db.query(Enrollment).delete()
        db.query(CourseOffering).delete()
        db.query(Course).delete()
        db.query(Student).delete()
        db.query(Teacher).delete()
        db.query(Department).delete()
        db.query(College).delete()
        db.query(User).delete()
        db.commit()

        admin = User(
            username="admin_opt_lock_test",
            email="admin_opt_lock@test.com",
            password_hash=hash_password("adminpass123"),
            role=UserRole.ADMIN,
        )
        college = College(name="Engineering College", code="ENG_OPT")
        db.add_all([admin, college])
        db.commit()

        department = Department(
            name="Computer Science", code="CS_OPT", college_id=college.id
        )
        db.add(department)
        db.commit()

        # Initial student with name "Ahmed" and initial version_id = 1
        student = Student(
            name="Ahmed",
            email="ahmed_opt@test.com",
            age=20,
            department_id=department.id,
            version_id=1,
        )
        db.add(student)
        db.commit()
        db.refresh(student)

        token = create_access_token(admin.id)

        data = {
            "admin": admin,
            "college": college,
            "department": department,
            "student_id": student.id,
            "initial_name": "Ahmed",
            "initial_version": student.version_id,
            "token": token,
        }
        yield data
    finally:
        # Teardown: clean up created data and restore dependency overrides
        try:
            db.query(Enrollment).delete()
            db.query(CourseOffering).delete()
            db.query(Course).delete()
            db.query(Student).delete()
            db.query(Teacher).delete()
            db.query(Department).delete()
            db.query(College).delete()
            db.query(User).delete()
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        finally:
            db.close()
            if prev_override is not None:
                app.dependency_overrides[get_db] = prev_override
            else:
                app.dependency_overrides.pop(get_db, None)


def test_interleaved_transactions_optimistic_locking_prevents_lost_update(
    student_optimistic_locking_setup,
):
    """Demonstrate that Optimistic Locking prevents the Lost Update anomaly.

    Scenario:
    1. Initial DB state: Student.name == "Ahmed", Student.version_id == 1
    2. Session A reads Student (observes version_id == 1, name == "Ahmed")
    3. Session B reads Student (observes version_id == 1, name == "Ahmed")
    4. Session A modifies name to "Ali" and commits -> SUCCESS (version_id becomes 2)
    5. Session B modifies name to "Omar" (holding stale version_id == 1) and attempts commit
    6. StaleDataError is raised on Session B because the version in DB is now 2
    7. Final DB state: Student.name == "Ali", Student.version_id == 2 (Lost Update is PREVENTED).
    """
    student_id = student_optimistic_locking_setup["student_id"]

    session_a = SessionLocal()
    session_b = SessionLocal()

    try:
        # Step 1: Session A reads the student
        stmt_a = select(Student).where(Student.id == student_id)
        student_a = session_a.execute(stmt_a).scalar_one()
        read_by_a = student_a.name
        version_a = student_a.version_id

        # Step 2: Session B reads the same student before any commit
        stmt_b = select(Student).where(Student.id == student_id)
        student_b = session_b.execute(stmt_b).scalar_one()
        read_by_b = student_b.name
        version_b = student_b.version_id

        assert read_by_a == "Ahmed" and version_a == 1
        assert read_by_b == "Ahmed" and version_b == 1

        # Step 3: Session A updates name to "Ali" and commits
        student_a.name = "Ali"
        session_a.commit()
        session_a.refresh(student_a)

        # Version incremented from 1 to 2
        assert student_a.version_id == 2
        assert student_a.name == "Ali"

        # Step 4: Session B updates name to "Omar" (based on stale version 1) and attempts commit
        student_b.name = "Omar"

        # Session B commit MUST raise StaleDataError because DB version is now 2
        with pytest.raises(StaleDataError):
            session_b.commit()

        session_b.rollback()

        # Step 5: Verify final database state: Transaction A's update is PRESERVED
        verify_session = SessionLocal()
        try:
            final_student = verify_session.execute(
                select(Student).where(Student.id == student_id)
            ).scalar_one()

            # The final name in the database remains "Ali" with version_id = 2
            assert final_student.name == "Ali"
            assert final_student.version_id == 2
        finally:
            verify_session.close()

    finally:
        session_a.close()
        session_b.close()


def test_concurrent_threads_crud_update_barrier_optimistic_locking(
    student_optimistic_locking_setup,
):
    """Test concurrent execution of update_student CRUD function protected by Optimistic Locking.

    Uses threading.Barrier to ensure both threads load the Student record before either
    thread commits.

    Proves:
    - Thread-A reads version 1 and commits "Ali" -> SUCCESS (version becomes 2).
    - Thread-B reads version 1, attempts to commit "Omar" -> catches StaleDataError -> returns HTTPException(409).
    - Database retains "Ali" (version 2), preventing silent overwrite.
    """
    student_id = student_optimistic_locking_setup["student_id"]

    barrier_read = threading.Barrier(2)
    event_a_committed = threading.Event()
    observed_reads = {}
    thread_outcomes = {}

    def worker_a():
        session = SessionLocal()
        try:
            # Read initial record
            st = session.execute(
                select(Student).where(Student.id == student_id)
            ).scalar_one()
            observed_reads["Thread-A"] = (st.name, st.version_id)

            # Wait for Thread-B to also read before proceeding
            barrier_read.wait(timeout=10)

            # Update student via CRUD logic
            payload = StudentUpdate(name="Ali")
            updated = update_student(session, payload, student_id)
            thread_outcomes["Thread-A"] = {
                "status": "SUCCESS",
                "saved_name": updated.name,
                "version_id": updated.version_id,
            }
            # Signal that Thread-A has completed its commit
            event_a_committed.set()
        except HTTPException as exc:
            thread_outcomes["Thread-A"] = {
                "status": "HTTP_EXCEPTION",
                "status_code": exc.status_code,
                "detail": exc.detail,
            }
        except Exception as exc:  # noqa: BLE001
            thread_outcomes["Thread-A"] = {
                "status": "ERROR",
                "detail": str(exc),
            }
        finally:
            session.close()

    def worker_b():
        session = SessionLocal()
        try:
            # Read initial record
            st = session.execute(
                select(Student).where(Student.id == student_id)
            ).scalar_one()
            observed_reads["Thread-B"] = (st.name, st.version_id)

            # Wait for Thread-A to also read before proceeding
            barrier_read.wait(timeout=10)

            # Wait until Thread-A commits to ensure sequential commit ordering
            event_a_committed.wait(timeout=10)

            # Update student based on stale read (session loaded version 1)
            payload = StudentUpdate(name="Omar")
            updated = update_student(session, payload, student_id)
            thread_outcomes["Thread-B"] = {
                "status": "SUCCESS",
                "saved_name": updated.name,
                "version_id": updated.version_id,
            }
        except HTTPException as exc:
            thread_outcomes["Thread-B"] = {
                "status": "HTTP_EXCEPTION",
                "status_code": exc.status_code,
                "detail": exc.detail,
            }
        except Exception as exc:  # noqa: BLE001
            thread_outcomes["Thread-B"] = {
                "status": "ERROR",
                "detail": str(exc),
            }
        finally:
            session.close()

    t1 = threading.Thread(target=worker_a, name="Thread-A")
    t2 = threading.Thread(target=worker_b, name="Thread-B")

    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    assert not t1.is_alive()
    assert not t2.is_alive()

    # Both threads read initial version 1
    assert observed_reads["Thread-A"] == ("Ahmed", 1)
    assert observed_reads["Thread-B"] == ("Ahmed", 1)

    # Thread-A succeeded
    assert thread_outcomes["Thread-A"]["status"] == "SUCCESS"
    assert thread_outcomes["Thread-A"]["saved_name"] == "Ali"
    assert thread_outcomes["Thread-A"]["version_id"] == 2

    # Thread-B failed with 409 Conflict due to StaleDataError
    assert thread_outcomes["Thread-B"]["status"] == "HTTP_EXCEPTION"
    assert thread_outcomes["Thread-B"]["status_code"] == 409
    assert "modified by another transaction" in thread_outcomes["Thread-B"]["detail"]

    # Final DB check confirms "Ali" is preserved
    verify_session = SessionLocal()
    try:
        final_st = verify_session.execute(
            select(Student).where(Student.id == student_id)
        ).scalar_one()
        assert final_st.name == "Ali"
        assert final_st.version_id == 2
    finally:
        verify_session.close()


def test_concurrent_api_put_requests_with_version_id_optimistic_locking(
    student_optimistic_locking_setup,
):
    """Test Lost Update protection through the HTTP API PUT /students/{student_id} using version_id.

    Demonstrates that:
    1. Client A and Client B both observe the student via GET /students/{id} (version_id == 1, name == "Ahmed").
    2. Client A submits PUT with {"name": "Ali", "version_id": 1} -> 200 OK (version_id becomes 2).
    3. Client B submits PUT with {"name": "Omar", "version_id": 1} (stale version) -> 409 Conflict.
    4. Database retains "Ali", and Client A's change is NOT lost.
    """
    student_id = student_optimistic_locking_setup["student_id"]
    token = student_optimistic_locking_setup["token"]

    client = TestClient(app)

    # 1. Both clients GET the student (reads version 1)
    resp_get_a = client.get(
        f"/students/{student_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_get_a.status_code == 200
    data_a = resp_get_a.json()
    assert data_a["name"] == "Ahmed"
    assert data_a["version_id"] == 1

    resp_get_b = client.get(
        f"/students/{student_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_get_b.status_code == 200
    data_b = resp_get_b.json()
    assert data_b["name"] == "Ahmed"
    assert data_b["version_id"] == 1

    # 2. Client A updates name to "Ali" sending version_id: 1 -> SUCCESS (200 OK)
    resp_put_a = client.put(
        f"/students/{student_id}",
        json={"name": "Ali", "version_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_put_a.status_code == 200
    assert resp_put_a.json()["name"] == "Ali"
    assert resp_put_a.json()["version_id"] == 2

    # 3. Client B attempts to update to "Omar" sending stale version_id: 1 -> 409 Conflict
    resp_put_b = client.put(
        f"/students/{student_id}",
        json={"name": "Omar", "version_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_put_b.status_code == 409
    assert "modified by another transaction" in resp_put_b.json()["detail"]

    # 4. Verify database state: "Ali" (version 2) is preserved!
    verify_session = SessionLocal()
    try:
        final_st = verify_session.execute(
            select(Student).where(Student.id == student_id)
        ).scalar_one()
        assert final_st.name == "Ali"
        assert final_st.version_id == 2
    finally:
        verify_session.close()


def test_sequential_updates_increment_version_id(
    student_optimistic_locking_setup,
):
    """Test sequential updates properly increment version_id when correct version is provided."""
    student_id = student_optimistic_locking_setup["student_id"]
    token = student_optimistic_locking_setup["token"]

    client = TestClient(app)

    # Update 1: version 1 -> 2
    resp_1 = client.put(
        f"/students/{student_id}",
        json={"name": "First Update", "version_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_1.status_code == 200
    assert resp_1.json()["version_id"] == 2

    # Update 2: version 2 -> 3
    resp_2 = client.put(
        f"/students/{student_id}",
        json={"name": "Second Update", "version_id": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_2.status_code == 200
    assert resp_2.json()["version_id"] == 3

    # Final DB check
    verify_session = SessionLocal()
    try:
        final_st = verify_session.execute(
            select(Student).where(Student.id == student_id)
        ).scalar_one()
        assert final_st.name == "Second Update"
        assert final_st.version_id == 3
    finally:
        verify_session.close()
