"""Concurrency & Consistency Integration Tests for Enrollment Creation.

This test module verifies concurrent enrollment behavior against the real test database,
demonstrating the Time-of-Check to Time-of-Use (TOCTOU) race condition between:
1. Application-level pre-check (SELECT existing enrollment)
2. Database-level UniqueConstraint (uq_student_course_offering)
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.crud.enrollment import create_enrollment
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
from app.schemas import EnrollmentCreate
from app.security.jwt import create_access_token
from app.security.password import hash_password
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


def override_concurrency_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def concurrency_db_setup():
    """Set up clean database tables and valid relational test data for concurrency tests."""
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
            username="admin_concurrency_test",
            email="admin_concurrency@test.com",
            password_hash=hash_password("adminpass123"),
            role=UserRole.ADMIN,
        )
        college = College(name="Engineering College", code="ENG_CONC")
        db.add_all([admin, college])
        db.commit()

        department = Department(
            name="Computer Science", code="CS_CONC", college_id=college.id
        )
        db.add(department)
        db.commit()

        student_1 = Student(
            name="Concurrency Student 1",
            email="student_conc_1@test.com",
            age=20,
            department_id=department.id,
        )
        student_2 = Student(
            name="Concurrency Student 2",
            email="student_conc_2@test.com",
            age=21,
            department_id=department.id,
        )
        teacher = Teacher(name="Concurrency Teacher", department_id=department.id)
        course = Course(
            name="Distributed Systems",
            code="CS401",
            department_id=department.id,
        )
        db.add_all([student_1, student_2, teacher, course])
        db.commit()

        offering = CourseOffering(
            course_id=course.id,
            teacher_id=teacher.id,
            semester="Fall",
            academic_year=2026,
            section="A",
        )
        db.add(offering)
        db.commit()

        token = create_access_token(admin.id)

        data = {
            "admin": admin,
            "college": college,
            "department": department,
            "student_1": student_1,
            "student_2": student_2,
            "teacher": teacher,
            "course": course,
            "offering": offering,
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


def test_toctou_interleaved_transactions_distinguish_precheck_vs_db_constraint(
    concurrency_db_setup,
):
    """Demonstrate the TOCTOU race condition using interleaved transactions.

    Explicitly proves that:
    1. Transaction A performs application pre-check: SELECT existing enrollment -> returns None.
    2. Transaction B performs application pre-check: SELECT existing enrollment -> returns None.
    3. Both transactions observed that no enrollment exists (application-level check passed for both).
    4. Transaction A inserts and commits -> SUCCESS.
    5. Transaction B attempts to insert and commit -> FAILS with IntegrityError on uq_student_course_offering.
    6. Database ends in a consistent state with exactly 1 enrollment row.
    """
    student = concurrency_db_setup["student_1"]
    offering = concurrency_db_setup["offering"]

    session_a = SessionLocal()
    session_b = SessionLocal()

    try:
        # Step 1: Session A executes the application-level pre-check query
        stmt_check_a = select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.course_offering_id == offering.id,
        )
        existing_in_a = session_a.execute(stmt_check_a).scalar_one_or_none()

        # Step 2: Session B executes the same application-level pre-check query concurrently
        stmt_check_b = select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.course_offering_id == offering.id,
        )
        existing_in_b = session_b.execute(stmt_check_b).scalar_one_or_none()

        # Both sessions observed that NO enrollment exists
        assert existing_in_a is None, "Session A must observe no existing enrollment"
        assert existing_in_b is None, "Session B must observe no existing enrollment"

        # Step 3: Session A inserts and commits
        enrollment_a = Enrollment(
            student_id=student.id,
            course_offering_id=offering.id,
            enrollment_code="ENR-TOCTOU-001",
        )
        session_a.add(enrollment_a)
        session_a.commit()
        session_a.refresh(enrollment_a)
        assert enrollment_a.id is not None

        # Step 4: Session B attempts to insert duplicate (student_id, course_offering_id)
        enrollment_b = Enrollment(
            student_id=student.id,
            course_offering_id=offering.id,
            enrollment_code="ENR-TOCTOU-002",
        )
        session_b.add(enrollment_b)

        # Step 5: Session B commit must raise IntegrityError due to uq_student_course_offering
        with pytest.raises(IntegrityError) as exc_info:
            session_b.commit()

        # Verify the database-level UniqueConstraint triggered the failure
        assert (
            "uq_student_course_offering" in str(exc_info.value).lower()
            or "unique constraint" in str(exc_info.value).lower()
        )
        session_b.rollback()

        # Step 6: Verify final database state: exactly 1 enrollment row exists
        verify_session = SessionLocal()
        try:
            all_enrollments = (
                verify_session.execute(
                    select(Enrollment).where(
                        Enrollment.student_id == student.id,
                        Enrollment.course_offering_id == offering.id,
                    )
                )
                .scalars()
                .all()
            )
            assert len(all_enrollments) == 1
            assert all_enrollments[0].enrollment_code == "ENR-TOCTOU-001"
        finally:
            verify_session.close()

    finally:
        session_a.close()
        session_b.close()


def test_concurrent_create_enrollment_crud_barrier_synchronization(
    concurrency_db_setup,
):
    """Test genuine multithreaded concurrent execution of create_enrollment.

    Uses threading.Barrier to ensure both threads complete their SELECT existence checks
    before either thread attempts to INSERT / COMMIT.

    Proves:
    - Both threads pass the application pre-check.
    - One thread commits successfully (HTTP 201 equivalent).
    - The concurrent thread fails at commit time with IntegrityError, which create_enrollment
      catches and translates to HTTPException(409, "Student is already enrolled in this course offering or enrollment code duplicate").
    - Database contains exactly 1 row.
    """
    student = concurrency_db_setup["student_1"]
    offering = concurrency_db_setup["offering"]

    barrier = threading.Barrier(2)
    thread_outcomes = {}

    def run_enrollment_in_thread(thread_id: str, code: str):
        db_session = SessionLocal()
        # Synchronize both threads right after pre-check SELECT queries, on db_session.add
        orig_add = db_session.add

        def synchronized_add(instance):
            # Both threads wait here after finishing all SELECT checks
            barrier.wait(timeout=10)
            return orig_add(instance)

        db_session.add = synchronized_add

        payload = EnrollmentCreate(
            student_id=student.id,
            course_offering_id=offering.id,
            enrollment_code=code,
        )

        try:
            created = create_enrollment(db_session, payload)
            thread_outcomes[thread_id] = {
                "status": "SUCCESS",
                "enrollment_id": created.id,
                "code": created.enrollment_code,
            }
        except HTTPException as exc:
            thread_outcomes[thread_id] = {
                "status": "HTTP_EXCEPTION",
                "status_code": exc.status_code,
                "detail": exc.detail,
            }
        finally:
            db_session.close()

    t1 = threading.Thread(
        target=run_enrollment_in_thread, args=("Thread-1", "ENR-BARRIER-001")
    )
    t2 = threading.Thread(
        target=run_enrollment_in_thread, args=("Thread-2", "ENR-BARRIER-002")
    )

    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    assert not t1.is_alive(), "Thread-1 did not complete in time"
    assert not t2.is_alive(), "Thread-2 did not complete in time"

    # Exactly one thread must succeed, and exactly one must fail with 409
    statuses = [res["status"] for res in thread_outcomes.values()]
    assert "SUCCESS" in statuses, f"Expected one success, got: {thread_outcomes}"
    assert "HTTP_EXCEPTION" in statuses, (
        f"Expected one conflict, got: {thread_outcomes}"
    )

    successful_res = next(
        res for res in thread_outcomes.values() if res["status"] == "SUCCESS"
    )
    failed_res = next(
        res for res in thread_outcomes.values() if res["status"] == "HTTP_EXCEPTION"
    )

    assert failed_res["status_code"] == 409
    # The failed concurrent request hits the IntegrityError exception handler:
    assert (
        failed_res["detail"]
        == "Student is already enrolled in this course offering or enrollment code duplicate"
    )

    # Verify final database state: exactly 1 enrollment row exists
    verify_session = SessionLocal()
    try:
        db_rows = (
            verify_session.execute(
                select(Enrollment).where(
                    Enrollment.student_id == student.id,
                    Enrollment.course_offering_id == offering.id,
                )
            )
            .scalars()
            .all()
        )
        assert len(db_rows) == 1
        assert db_rows[0].id == successful_res["enrollment_id"]
        assert db_rows[0].enrollment_code == successful_res["code"]
    finally:
        verify_session.close()


def test_sequential_duplicate_enrollment_hits_application_precheck(
    concurrency_db_setup,
):
    """Contrast baseline: sequential duplicate enrollment hits the application-level pre-check.

    Demonstrates that in sequential execution:
    - The first request commits.
    - The second request performs SELECT existing enrollment -> finds the existing row.
    - The second request raises HTTPException(409, "Student is already enrolled in this course offering")
      BEFORE any INSERT or IntegrityError can happen.

    This contrasts with concurrent execution where both requests pass the SELECT pre-check
    and the second request fails at the database level with IntegrityError.
    """
    student = concurrency_db_setup["student_1"]
    offering = concurrency_db_setup["offering"]

    session_1 = SessionLocal()
    session_2 = SessionLocal()

    try:
        # Request 1: Succeeds
        payload_1 = EnrollmentCreate(
            student_id=student.id,
            course_offering_id=offering.id,
            enrollment_code="ENR-SEQ-001",
        )
        res_1 = create_enrollment(session_1, payload_1)
        assert res_1.id is not None

        # Request 2: Sequential duplicate attempt
        payload_2 = EnrollmentCreate(
            student_id=student.id,
            course_offering_id=offering.id,
            enrollment_code="ENR-SEQ-002",
        )
        with pytest.raises(HTTPException) as exc_info:
            create_enrollment(session_2, payload_2)

        assert exc_info.value.status_code == 409
        # Notice the exact detail string from line 37 of app/crud/enrollment.py:
        assert (
            exc_info.value.detail
            == "Student is already enrolled in this course offering"
        )

    finally:
        session_1.close()
        session_2.close()


def test_concurrent_same_enrollment_code_different_students(
    concurrency_db_setup,
):
    """Test concurrent race condition on the enrollment_code unique constraint.

    Two concurrent requests try to enroll TWO DIFFERENT students into the same offering
    using the SAME enrollment_code.

    Proves:
    - Both pass the application-level SELECT existing enrollment code pre-check.
    - One commits successfully.
    - The other fails on the enrollment_code unique constraint via IntegrityError.
    - Exactly 1 enrollment with that code exists in the database.
    """
    student_1 = concurrency_db_setup["student_1"]
    student_2 = concurrency_db_setup["student_2"]
    offering = concurrency_db_setup["offering"]
    shared_code = "ENR-SHARED-CODE-100"

    barrier = threading.Barrier(2)
    thread_outcomes = {}

    def run_same_code_enrollment(thread_id: str, student_id: int):
        db_session = SessionLocal()
        orig_add = db_session.add

        def synchronized_add(instance):
            barrier.wait(timeout=10)
            return orig_add(instance)

        db_session.add = synchronized_add

        payload = EnrollmentCreate(
            student_id=student_id,
            course_offering_id=offering.id,
            enrollment_code=shared_code,
        )

        try:
            created = create_enrollment(db_session, payload)
            thread_outcomes[thread_id] = {
                "status": "SUCCESS",
                "enrollment_id": created.id,
                "student_id": created.student_id,
            }
        except HTTPException as exc:
            thread_outcomes[thread_id] = {
                "status": "HTTP_EXCEPTION",
                "status_code": exc.status_code,
                "detail": exc.detail,
            }
        finally:
            db_session.close()

    t1 = threading.Thread(
        target=run_same_code_enrollment, args=("Thread-1", student_1.id)
    )
    t2 = threading.Thread(
        target=run_same_code_enrollment, args=("Thread-2", student_2.id)
    )

    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    assert not t1.is_alive()
    assert not t2.is_alive()

    statuses = [res["status"] for res in thread_outcomes.values()]
    assert "SUCCESS" in statuses
    assert "HTTP_EXCEPTION" in statuses

    failed_res = next(
        res for res in thread_outcomes.values() if res["status"] == "HTTP_EXCEPTION"
    )
    assert failed_res["status_code"] == 409
    assert (
        failed_res["detail"]
        == "Student is already enrolled in this course offering or enrollment code duplicate"
    )

    # Verify database has exactly 1 row with that enrollment code
    verify_session = SessionLocal()
    try:
        rows = (
            verify_session.execute(
                select(Enrollment).where(Enrollment.enrollment_code == shared_code)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
    finally:
        verify_session.close()


def test_concurrent_api_endpoint_barrier_synchronization(
    concurrency_db_setup,
):
    """Test concurrent API endpoint calls to POST /enrollments/ with barrier coordination.

    Exercises the full FastAPI dependency stack (get_db, require_admin, Pydantic validation)
    under concurrent execution.
    """
    student = concurrency_db_setup["student_1"]
    offering = concurrency_db_setup["offering"]
    token = concurrency_db_setup["token"]

    barrier = threading.Barrier(2)
    api_responses = []

    def make_api_call(code: str):
        client = TestClient(app)
        # Synchronize before sending request
        barrier.wait(timeout=10)
        response = client.post(
            "/enrollments/",
            json={
                "student_id": student.id,
                "course_offering_id": offering.id,
                "enrollment_code": code,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        api_responses.append((response.status_code, response.json()))

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(make_api_call, "ENR-API-BARRIER-001")
        f2 = executor.submit(make_api_call, "ENR-API-BARRIER-002")
        f1.result()
        f2.result()

    status_codes = [resp[0] for resp in api_responses]
    assert 201 in status_codes, f"Expected 201 Created, got: {status_codes}"
    assert 409 in status_codes, f"Expected 409 Conflict, got: {status_codes}"

    # Verify database row count
    verify_session = SessionLocal()
    try:
        rows = (
            verify_session.execute(
                select(Enrollment).where(
                    Enrollment.student_id == student.id,
                    Enrollment.course_offering_id == offering.id,
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
    finally:
        verify_session.close()
