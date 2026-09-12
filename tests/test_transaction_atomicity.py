"""Transaction Safety & Consistency Integration Tests for system_uni.

This test module verifies the Atomicity and Transaction Safety of business
operations across PostgreSQL database sessions in system_uni, ensuring that:
1. Multi-step operations either commit completely or roll back completely.
2. Exceptions midway through an operation leave zero persistent side-effects in the DB.
3. SQLAlchemy session lifecycle and explicit rollback handlers prevent Partial Commits.
"""

import pytest
from app.crud.enrollment import create_enrollment
from app.crud.student import link_student_to_user
from app.crud.user import delete_user, update_user
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
from app.schemas import EnrollmentCreate, UserUpdate
from app.security.password import hash_password
from fastapi import HTTPException
from sqlalchemy import select


def override_atomicity_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def atomicity_db_setup():
    """Set up clean database tables with known initial relational state."""
    prev_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_atomicity_get_db
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

        # Seed initial relational fixtures (codes <= 10 characters)
        college = College(name="Engineering College", code="ENG_ATM")
        db.add(college)
        db.flush()

        dept = Department(name="Computer Science", code="CS_ATM", college_id=college.id)
        db.add(dept)
        db.flush()

        teacher = Teacher(name="Dr. Tarek", department_id=dept.id)
        db.add(teacher)
        db.flush()

        course = Course(
            name="Database Systems", code="CS301_ATM", department_id=dept.id
        )
        db.add(course)
        db.flush()

        offering = CourseOffering(
            course_id=course.id,
            teacher_id=teacher.id,
            semester="Fall",
            academic_year=2026,
            section="A",
        )
        db.add(offering)
        db.flush()

        admin_user = User(
            username="admin_atomic",
            email="admin_atomic@example.com",
            password_hash=hash_password("AdminPass123!"),
            role=UserRole.ADMIN,
        )
        db.add(admin_user)

        regular_user = User(
            username="student_user_atomic",
            email="student_user_atomic@example.com",
            password_hash=hash_password("UserPass123!"),
            role=UserRole.USER,
        )
        db.add(regular_user)

        student = Student(
            name="Seif",
            email="seif_atomic@example.com",
            age=22,
            department_id=dept.id,
        )
        db.add(student)

        db.commit()

        yield {
            "college_id": college.id,
            "department_id": dept.id,
            "teacher_id": teacher.id,
            "course_id": course.id,
            "offering_id": offering.id,
            "admin_user_id": admin_user.id,
            "regular_user_id": regular_user.id,
            "student_id": student.id,
        }
    finally:
        db.close()
        app.dependency_overrides[get_db] = prev_override


def test_link_student_to_user_successful_atomic_commit(atomicity_db_setup):
    """Verify that a successful student-user link atomically updates FK and increments version_id."""
    student_id = atomicity_db_setup["student_id"]
    user_id = atomicity_db_setup["regular_user_id"]

    # Initial state verification
    db_verify = SessionLocal()
    try:
        s_initial = db_verify.get(Student, student_id)
        assert s_initial is not None
        assert s_initial.user_id is None
        assert s_initial.version_id == 1
    finally:
        db_verify.close()

    # Execute linking operation
    db = SessionLocal()
    try:
        updated_student = link_student_to_user(db, student_id, user_id)
        assert updated_student.user_id == user_id
    finally:
        db.close()

    # Verify atomic persistence in fresh session
    db_after = SessionLocal()
    try:
        s_after = db_after.get(Student, student_id)
        u_after = db_after.get(User, user_id)
        assert s_after.user_id == user_id
        assert s_after.version_id == 2  # Optimistic version incremented atomically
        assert u_after.student is not None
        assert u_after.student.id == student_id
    finally:
        db_after.close()


def test_link_student_to_user_atomicity_on_pre_commit_exception(atomicity_db_setup):
    """Verify that if an exception occurs midway before commit, no partial linkage or version bump occurs."""
    student_id = atomicity_db_setup["student_id"]
    user_id = atomicity_db_setup["regular_user_id"]

    # Initial state
    db_check = SessionLocal()
    try:
        s_before = db_check.get(Student, student_id)
        assert s_before.user_id is None
        assert s_before.version_id == 1
    finally:
        db_check.close()

    # Simulate multi-step operation where Step A (mutation) happens, but Step B throws an Exception before commit
    db = SessionLocal()
    try:
        student = db.get(Student, student_id)
        student.user_id = user_id  # Step A: In-memory stage mutation

        # Step B: Realistic mid-operation unexpected failure before commit
        raise RuntimeError(
            "Simulated network/service crash during linking operation before commit"
        )
    except RuntimeError:
        pass
    finally:
        db.close()  # Session closes without commit -> SQLAlchemy rolls back automatically

    # Verify Database State after failure: No Partial Commit occurred
    db_fresh = SessionLocal()
    try:
        s_fresh = db_fresh.get(Student, student_id)
        u_fresh = db_fresh.get(User, user_id)

        assert s_fresh.user_id is None, (
            "Student user_id must remain None after rollback"
        )
        assert s_fresh.version_id == 1, (
            "Student version_id must not increment on aborted transaction"
        )
        assert u_fresh.student is None, "User must not have any associated student"
    finally:
        db_fresh.close()


def test_link_student_to_user_atomicity_on_conflict_rollback(atomicity_db_setup):
    """Verify that when linking fails due to conflict, explicit rollback leaves state intact."""
    student_id = atomicity_db_setup["student_id"]
    user_id = atomicity_db_setup["regular_user_id"]

    # First, link successfully
    db1 = SessionLocal()
    try:
        link_student_to_user(db1, student_id, user_id)
    finally:
        db1.close()

    # Create a second student
    db_setup = SessionLocal()
    try:
        student2 = Student(
            name="Kareem",
            email="kareem_atomic@example.com",
            age=23,
            department_id=atomicity_db_setup["department_id"],
        )
        db_setup.add(student2)
        db_setup.commit()
        student2_id = student2.id
    finally:
        db_setup.close()

    # Attempt to link student2 to the already-linked user_id (Conflict)
    db2 = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            link_student_to_user(db2, student2_id, user_id)
        assert exc_info.value.status_code == 409
    finally:
        db2.close()

    # Verify database state after conflict: student2 remains unlinked and version_id unchanged
    db_verify = SessionLocal()
    try:
        s2 = db_verify.get(Student, student2_id)
        assert s2.user_id is None
        assert s2.version_id == 1

        s1 = db_verify.get(Student, student_id)
        assert s1.user_id == user_id
    finally:
        db_verify.close()


def test_admin_protection_transaction_atomicity_and_lock_release(atomicity_db_setup):
    """Verify that attempting to demote or delete the sole admin fails atomically without state mutation."""
    admin_id = atomicity_db_setup["admin_user_id"]

    # Initial state
    db_check = SessionLocal()
    try:
        admin_before = db_check.get(User, admin_id)
        assert admin_before.role == UserRole.ADMIN
    finally:
        db_check.close()

    # Attempt to demote sole admin to USER
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            update_user(db, UserUpdate(role=UserRole.USER), admin_id)
        assert exc_info.value.status_code == 400
        assert "Cannot remove the last admin account" in exc_info.value.detail
    finally:
        db.close()

    # Verify DB State: Admin role remains intact
    db_after = SessionLocal()
    try:
        admin_after = db_after.get(User, admin_id)
        assert admin_after is not None
        assert admin_after.role == UserRole.ADMIN, (
            "Admin role must not change on aborted transaction"
        )
    finally:
        db_after.close()

    # Attempt to delete sole admin
    db_del = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info_del:
            delete_user(db_del, admin_id)
        assert exc_info_del.value.status_code == 400
    finally:
        db_del.close()

    # Verify DB State: Admin still exists
    db_after_del = SessionLocal()
    try:
        admin_after_del = db_after_del.get(User, admin_id)
        assert admin_after_del is not None
        assert admin_after_del.role == UserRole.ADMIN
    finally:
        db_after_del.close()


def test_enrollment_creation_atomicity_on_duplicate_constraint(atomicity_db_setup):
    """Verify that enrollment creation fails atomically on duplicate constraint without orphan rows."""
    student_id = atomicity_db_setup["student_id"]
    offering_id = atomicity_db_setup["offering_id"]

    enrollment_data = EnrollmentCreate(
        student_id=student_id,
        course_offering_id=offering_id,
        enrollment_code="ENR-ATM-01",
        grade=95,
    )

    # Step 1: Successful creation
    db1 = SessionLocal()
    try:
        enr1 = create_enrollment(db1, enrollment_data)
        assert enr1.id is not None
    finally:
        db1.close()

    # Verify 1 enrollment exists
    db_check = SessionLocal()
    try:
        count_before = len(db_check.execute(select(Enrollment)).scalars().all())
        assert count_before == 1
    finally:
        db_check.close()

    # Step 2: Attempt duplicate creation (Same student and offering)
    duplicate_data = EnrollmentCreate(
        student_id=student_id,
        course_offering_id=offering_id,
        enrollment_code="ENR-ATM-02",
        grade=88,
    )

    db2 = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            create_enrollment(db2, duplicate_data)
        assert exc_info.value.status_code == 409
    finally:
        db2.close()

    # Verify Database State after failure: Total enrollments count is strictly 1
    db_verify = SessionLocal()
    try:
        all_enrollments = db_verify.execute(select(Enrollment)).scalars().all()
        assert len(all_enrollments) == 1
        assert all_enrollments[0].enrollment_code == "ENR-ATM-01"
    finally:
        db_verify.close()


def test_multi_table_composite_sequence_atomicity_and_rollback():
    """Verify that a multi-table insertion sequence rolls back 100% when an unhandled exception occurs."""
    db_check = SessionLocal()
    try:
        colleges_before = len(
            db_check.execute(select(College).where(College.code == "ROL_COL"))
            .scalars()
            .all()
        )
        departments_before = len(
            db_check.execute(select(Department).where(Department.code == "ROL_DEP"))
            .scalars()
            .all()
        )
        assert colleges_before == 0
        assert departments_before == 0
    finally:
        db_check.close()

    # Multi-step operation: Step A (Add College) -> Step B (Add Department) -> Step C (Crash before commit)
    db = SessionLocal()
    try:
        # Step A: Insert College
        college = College(name="Rollback Test College", code="ROL_COL")
        db.add(college)
        db.flush()  # Flushes SQL to DB within transaction, acquiring DB-generated ID

        # Step B: Insert Department with College ID
        dept = Department(
            name="Rollback Test Dept", code="ROL_DEP", college_id=college.id
        )
        db.add(dept)
        db.flush()

        # Step C: Failure midway
        raise ValueError("Simulated unexpected exception before transaction commit")
    except ValueError:
        # Simulate exception handler or transaction abort
        db.rollback()
    finally:
        db.close()

    # Verify Database State in fresh session: Neither College nor Department was committed
    db_verify = SessionLocal()
    try:
        colleges_after = (
            db_verify.execute(select(College).where(College.code == "ROL_COL"))
            .scalars()
            .all()
        )
        departments_after = (
            db_verify.execute(select(Department).where(Department.code == "ROL_DEP"))
            .scalars()
            .all()
        )

        assert len(colleges_after) == 0, "College must be rolled back"
        assert len(departments_after) == 0, "Department must be rolled back"
    finally:
        db_verify.close()


def test_postgres_check_constraints_reject_invalid_rows(atomicity_db_setup):
    """CHECK constraints are enforced by PostgreSQL itself, even for raw SQL."""
    from sqlalchemy import text as sa_text
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    student_id = atomicity_db_setup["student_id"]
    offering_id = atomicity_db_setup["offering_id"]

    db = SessionLocal()
    try:
        # grade out of range
        with pytest.raises(SAIntegrityError) as exc_info:
            db.execute(
                sa_text(
                    "INSERT INTO enrollment (student_id, course_offering_id, "
                    "enrollment_code, grade) "
                    "VALUES (:s, :o, 'ENR-CHECK-1', 150)"
                ),
                {"s": student_id, "o": offering_id},
            )
        assert "ck_enrollment_grade_range" in str(exc_info.value.orig)
        db.rollback()

        # contradictory active/withdrawn state
        with pytest.raises(SAIntegrityError) as exc_info:
            db.execute(
                sa_text(
                    "INSERT INTO enrollment (student_id, course_offering_id, "
                    "enrollment_code, is_active, is_withdrawn) "
                    "VALUES (:s, :o, 'ENR-CHECK-2', true, true)"
                ),
                {"s": student_id, "o": offering_id},
            )
        assert "ck_enrollment_active_xor_withdrawn" in str(exc_info.value.orig)
        db.rollback()

        # inverted schedule times
        with pytest.raises(SAIntegrityError) as exc_info:
            db.execute(
                sa_text(
                    "INSERT INTO course_schedule (day, schedule_type, start_time, "
                    "end_time, room, course_offering_id) "
                    "VALUES ('Monday', 'Lab', '15:00', '14:00', 'R1', :o)"
                ),
                {"o": offering_id},
            )
        assert "ck_course_schedule_time_order" in str(exc_info.value.orig)
        db.rollback()
    finally:
        db.close()
