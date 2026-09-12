import pytest
from app.database import Base, get_db
from app.main import app
from app.models.job import Job
from app.models.report import Report
from app.models.user import User, UserRole
from app.security.jwt import create_access_token
from app.security.password import hash_password
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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


def create_enrollment_authorization_data(db):
    """Create real related records used by Enrollment authorization API tests."""
    from app.models.college import College
    from app.models.course import Course
    from app.models.courseoffering import CourseOffering
    from app.models.department import Department
    from app.models.enrollment import Enrollment
    from app.models.student import Student
    from app.models.teacher import Teacher

    user = User(
        username="enrollment_user",
        email="enrollment_user@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    other_user = User(
        username="enrollment_other_user",
        email="enrollment_other_user@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    guest = User(
        username="enrollment_guest",
        email="enrollment_guest@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.GUEST,
    )
    college = College(name="Enrollment College", code="ENR_COL")
    db.add_all([user, other_user, guest, college])
    db.commit()

    department = Department(
        name="Enrollment Department", code="ENR_DEP", college_id=college.id
    )
    db.add(department)
    db.commit()

    own_student = Student(
        name="Enrollment Own Student",
        email="enrollment_own_student@test.com",
        age=20,
        department_id=department.id,
        user_id=user.id,
    )
    other_student = Student(
        name="Enrollment Other Student",
        email="enrollment_other_student@test.com",
        age=21,
        department_id=department.id,
        user_id=other_user.id,
    )
    teacher = Teacher(name="Enrollment Teacher", department_id=department.id)
    course = Course(
        name="Enrollment Course", code="ENR101", department_id=department.id
    )
    db.add_all([own_student, other_student, teacher, course])
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

    own_enrollment = Enrollment(
        student_id=own_student.id,
        course_offering_id=offering.id,
        enrollment_code="ENR-OWN-001",
    )
    other_enrollment = Enrollment(
        student_id=other_student.id,
        course_offering_id=offering.id,
        enrollment_code="ENR-OTHER-001",
    )
    db.add_all([own_enrollment, other_enrollment])
    db.commit()
    db.refresh(own_enrollment)
    db.refresh(other_enrollment)

    return {
        "user": user,
        "guest": guest,
        "own_student": own_student,
        "own_enrollment": own_enrollment,
        "other_enrollment": other_enrollment,
        "offering": offering,
    }


def enrollment_headers(user):
    token = create_access_token(user_id=user.id)
    return {"Authorization": f"Bearer {token}"}


def test_enrollment_user_cannot_read_another_students_enrollment(setup_db):
    data = create_enrollment_authorization_data(setup_db)

    response = client.get(
        f"/enrollments/{data['other_enrollment'].id}",
        headers=enrollment_headers(data["user"]),
    )

    assert response.status_code == 404


def test_enrollment_user_can_read_own_students_enrollment(setup_db):
    data = create_enrollment_authorization_data(setup_db)

    response = client.get(
        f"/enrollments/{data['own_enrollment'].id}",
        headers=enrollment_headers(data["user"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == data["own_enrollment"].id


def test_enrollment_user_cannot_create_enrollment(setup_db):
    data = create_enrollment_authorization_data(setup_db)
    payload = {
        "student_id": data["own_student"].id,
        "course_offering_id": data["offering"].id,
        "enrollment_code": "ENR-USER-CREATE",
    }

    response = client.post(
        "/enrollments/", json=payload, headers=enrollment_headers(data["user"])
    )

    assert response.status_code == 403


def test_enrollment_guest_cannot_create_enrollment(setup_db):
    data = create_enrollment_authorization_data(setup_db)
    payload = {
        "student_id": data["own_student"].id,
        "course_offering_id": data["offering"].id,
        "enrollment_code": "ENR-GUEST-CREATE",
    }

    response = client.post(
        "/enrollments/", json=payload, headers=enrollment_headers(data["guest"])
    )

    assert response.status_code == 403


def test_enrollment_user_cannot_update_enrollment(setup_db):
    data = create_enrollment_authorization_data(setup_db)

    response = client.put(
        f"/enrollments/{data['own_enrollment'].id}",
        json={"grade": 95},
        headers=enrollment_headers(data["user"]),
    )

    assert response.status_code == 403


def test_enrollment_user_cannot_delete_enrollment(setup_db):
    data = create_enrollment_authorization_data(setup_db)

    response = client.delete(
        f"/enrollments/{data['own_enrollment'].id}",
        headers=enrollment_headers(data["user"]),
    )

    assert response.status_code == 403


def test_enrollment_guest_cannot_read_enrollment(setup_db):
    data = create_enrollment_authorization_data(setup_db)

    response = client.get(
        f"/enrollments/{data['own_enrollment'].id}",
        headers=enrollment_headers(data["guest"]),
    )

    assert response.status_code == 403


def test_enrollment_user_list_contains_only_own_students_enrollments(setup_db):
    data = create_enrollment_authorization_data(setup_db)

    response = client.get("/enrollments/", headers=enrollment_headers(data["user"]))

    assert response.status_code == 200
    enrollment_ids = {enrollment["id"] for enrollment in response.json()}
    assert enrollment_ids == {data["own_enrollment"].id}
    assert data["other_enrollment"].id not in enrollment_ids


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/enrollments/", None),
        ("get", "/enrollments/{enrollment_id}", None),
        ("post", "/enrollments/", {"enrollment_code": "ENR-UNAUTH"}),
        ("put", "/enrollments/{enrollment_id}", {"grade": 90}),
        ("delete", "/enrollments/{enrollment_id}", None),
    ],
)
def test_enrollment_protected_endpoints_require_authentication(
    setup_db, method, path, payload
):
    data = create_enrollment_authorization_data(setup_db)
    endpoint = path.format(enrollment_id=data["own_enrollment"].id)

    request = getattr(client, method)
    response = (
        request(endpoint, json=payload) if payload is not None else request(endpoint)
    )

    assert response.status_code == 401


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


def test_job_status_endpoints(setup_db):
    db = setup_db
    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    # Test unauthenticated access to job status
    resp = client.get("/reports/jobs/some-uuid")
    assert resp.status_code == 401

    job_id = "test-job-123"
    report_result = {"student_id": 10, "gpa": 3.9}
    db.add(
        Job(
            job_id=job_id,
            status="completed",
            owner_id=1,
            report_type="transcript",
            target_id=10,
            job_version=1,
        )
    )
    db.add(Report(job_id=job_id, result=report_result))
    db.commit()

    resp = client.get(f"/reports/jobs/{job_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "job_id": job_id,
        "status": "completed",
        "owner_id": 1,
        "report_type": "transcript",
        "target_id": 10,
        "result": report_result,
    }

    resp = client.get("/reports/jobs/non-existent-job-id", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


def test_job_status_forbidden_for_non_owner_user(setup_db):
    db = setup_db
    # Create regular user (UserRole.USER)
    regular_user = User(
        username="regular_student",
        email="student_reg@test.com",
        password_hash=hash_password("studentpass123"),
        role=UserRole.USER,
    )
    db.add(regular_user)
    db.commit()
    db.refresh(regular_user)

    token = create_access_token(user_id=regular_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    job_id = "test-job-456"
    db.add(
        Job(
            job_id=job_id,
            status="processing",
            owner_id=1,
            report_type="transcript",
            target_id=10,
            job_version=1,
        )
    )
    db.commit()

    resp = client.get(f"/reports/jobs/{job_id}", headers=headers)
    # Uniform 404 so job IDs of other users cannot be enumerated.
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Job not found"}


def test_export_transcript_student_not_found():
    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/reports/export/99999", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Student not found"


def test_export_transcript_persists_job_for_worker(setup_db):
    from app.models.college import College
    from app.models.department import Department
    from app.models.student import Student

    db = setup_db
    college = College(name="Science", code="SCI")
    db.add(college)
    db.commit()
    db.refresh(college)

    department = Department(name="Physics", code="PHYS", college_id=college.id)
    db.add(department)
    db.commit()
    db.refresh(department)

    student = Student(
        name="Test Student",
        email="test_student@example.com",
        age=20,
        department_id=department.id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(f"/reports/export/{student.id}", headers=headers)
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    db_job = db.get(Job, job_id)
    assert db_job is not None
    assert db_job.status == "queued"
    assert db_job.owner_id == 1
    assert db_job.attempt_count == 0


def test_export_transcript_starts_with_no_retry_delay(setup_db):
    from app.models.college import College
    from app.models.department import Department
    from app.models.student import Student

    db = setup_db
    college = College(name="Engineering", code="ENG2")
    db.add(college)
    db.commit()
    db.refresh(college)

    department = Department(name="Mechanical", code="MECH", college_id=college.id)
    db.add(department)
    db.commit()
    db.refresh(department)

    student = Student(
        name="Jane Student",
        email="jane_student@example.com",
        age=21,
        department_id=department.id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(f"/reports/export/{student.id}", headers=headers)
    assert resp.status_code == 202
    db_job = db.get(Job, resp.json()["job_id"])
    assert db_job is not None
    assert db_job.status == "queued"
    assert db_job.retry_at is None


def test_export_transcript_success_queues_job(setup_db):
    from app.models.college import College
    from app.models.department import Department
    from app.models.student import Student

    db = setup_db

    # 1. Create authenticated user (UserRole.USER)
    user = User(
        username="export_user",
        email="export_user@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create existing student
    college = College(name="Engineering College", code="ENG_EXP")
    db.add(college)
    db.commit()
    db.refresh(college)

    department = Department(name="Computer Eng", code="CE", college_id=college.id)
    db.add(department)
    db.commit()
    db.refresh(department)

    student = Student(
        name="Alex Student",
        email="alex@example.com",
        age=22,
        department_id=department.id,
        user_id=user.id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    resp = client.post(f"/reports/export/{student.id}", headers=headers)
    assert resp.status_code == 202
    data = resp.json()
    assert data["message"] == "Report generation queued successfully"
    assert data["student_id"] == student.id
    assert data["status"] == "queued"
    job = db.get(Job, data["job_id"])
    assert job is not None
    assert job.owner_id == user.id
    assert job.report_type == "transcript"


def test_get_transcript_regular_user_can_view_own_student(setup_db):
    """1. USER can read transcript of their own linked student -> 200"""
    from app.models.college import College
    from app.models.department import Department
    from app.models.student import Student

    db = setup_db
    user = User(
        username="transcript_user_own",
        email="transcript_own@test.com",
        password_hash=hash_password("pass123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    college = College(name="College A", code="COL_A")
    db.add(college)
    db.commit()
    db.refresh(college)

    department = Department(name="Dept A", code="DPT_A", college_id=college.id)
    db.add(department)
    db.commit()
    db.refresh(department)

    student = Student(
        name="Own Student",
        email="own_student@test.com",
        age=20,
        department_id=department.id,
        user_id=user.id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get(f"/reports/transcript/{student.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == student.id


def test_get_transcript_regular_user_forbidden_for_other_student(setup_db):
    """2. USER cannot read transcript of another student -> 403"""
    from app.models.college import College
    from app.models.department import Department
    from app.models.student import Student

    db = setup_db
    user1 = User(
        username="user1_req",
        email="user1_req@test.com",
        password_hash=hash_password("pass123"),
        role=UserRole.USER,
    )
    user2 = User(
        username="user2_owner",
        email="user2_owner@test.com",
        password_hash=hash_password("pass123"),
        role=UserRole.USER,
    )
    db.add_all([user1, user2])
    db.commit()
    db.refresh(user1)
    db.refresh(user2)

    college = College(name="College B", code="COL_B")
    db.add(college)
    db.commit()
    db.refresh(college)

    department = Department(name="Dept B", code="DPT_B", college_id=college.id)
    db.add(department)
    db.commit()
    db.refresh(department)

    # Student belongs to user2
    student = Student(
        name="User2 Student",
        email="user2_student@test.com",
        age=21,
        department_id=department.id,
        user_id=user2.id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    # user1 tries to access user2's student
    token = create_access_token(user_id=user1.id)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get(f"/reports/transcript/{student.id}", headers=headers)
    # Uniform 404 so other students' IDs cannot be enumerated.
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Student not found"}


def test_get_transcript_admin_can_view_any_student(setup_db):
    """3. ADMIN can read transcript of any student -> 200"""
    from app.models.college import College
    from app.models.department import Department
    from app.models.student import Student

    db = setup_db
    college = College(name="College C", code="COL_C")
    db.add(college)
    db.commit()
    db.refresh(college)

    department = Department(name="Dept C", code="DPT_C", college_id=college.id)
    db.add(department)
    db.commit()
    db.refresh(department)

    student = Student(
        name="Any Student",
        email="any_student@test.com",
        age=22,
        department_id=department.id,
        user_id=999,  # Unrelated user
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    # Admin user id=1 from setup_db
    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get(f"/reports/transcript/{student.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["student_id"] == student.id


def test_export_transcript_regular_user_forbidden_for_other_student(setup_db):
    """5. USER cannot export transcript of another student -> 403"""
    from app.models.college import College
    from app.models.department import Department
    from app.models.student import Student

    db = setup_db
    user1 = User(
        username="user1_exporter",
        email="user1_exp@test.com",
        password_hash=hash_password("pass123"),
        role=UserRole.USER,
    )
    user2 = User(
        username="user2_target",
        email="user2_tgt@test.com",
        password_hash=hash_password("pass123"),
        role=UserRole.USER,
    )
    db.add_all([user1, user2])
    db.commit()
    db.refresh(user1)
    db.refresh(user2)

    college = College(name="College D", code="COL_D")
    db.add(college)
    db.commit()
    db.refresh(college)

    department = Department(name="Dept D", code="DPT_D", college_id=college.id)
    db.add(department)
    db.commit()
    db.refresh(department)

    # Student belongs to user2
    student = Student(
        name="Other Student",
        email="other_student@test.com",
        age=23,
        department_id=department.id,
        user_id=user2.id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    # user1 tries to export user2's student
    token = create_access_token(user_id=user1.id)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(f"/reports/export/{student.id}", headers=headers)
    # Uniform 404 so other students' IDs cannot be enumerated.
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Student not found"}


def test_export_transcript_admin_can_export_any_student(setup_db):
    """6. ADMIN can export any student's transcript -> 202"""
    from app.models.college import College
    from app.models.department import Department
    from app.models.student import Student

    db = setup_db
    college = College(name="College E", code="COL_E")
    db.add(college)
    db.commit()
    db.refresh(college)

    department = Department(name="Dept E", code="DPT_E", college_id=college.id)
    db.add(department)
    db.commit()
    db.refresh(department)

    student = Student(
        name="Admin Target Student",
        email="admin_tgt@test.com",
        age=24,
        department_id=department.id,
        user_id=888,  # Not admin's student
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    # Admin user id=1
    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(f"/reports/export/{student.id}", headers=headers)
    assert resp.status_code == 202
    data = resp.json()
    assert data["student_id"] == student.id
    assert data["status"] == "queued"


def test_job_status_is_read_from_postgresql(setup_db):
    """Job status and result come directly from PostgreSQL."""

    db = setup_db
    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    job_id = "job-redis-error"
    report_result = {"student_id": 11, "gpa": 3.7}
    db.add(
        Job(
            job_id=job_id,
            status="completed",
            owner_id=1,
            report_type="transcript",
            target_id=11,
            job_version=1,
        )
    )
    db.add(Report(job_id=job_id, result=report_result))
    db.commit()

    resp = client.get(f"/reports/jobs/{job_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["owner_id"] == 1
    assert resp.json()["result"] == report_result


def test_job_status_admin_can_view_other_users_job(setup_db):
    """Scenario 6: Admin user (not owner) can view any job -> 200 OK"""
    db = setup_db
    # User 1 is Admin from setup_db
    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    job_id = "test-job-admin-view"
    report_result = "some transcript"
    db.add(
        Job(
            job_id=job_id,
            status="completed",
            owner_id=888,
            report_type="transcript",
            target_id=12,
            job_version=1,
        )
    )
    db.add(Report(job_id=job_id, result=report_result))
    db.commit()

    resp = client.get(f"/reports/jobs/{job_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "job_id": job_id,
        "status": "completed",
        "owner_id": 888,
        "report_type": "transcript",
        "target_id": 12,
        "result": report_result,
    }


def test_job_status_regular_user_owner_can_view_own_job(setup_db):
    """Scenario 5: Regular user (UserRole.USER) who is the owner can view own job -> 200 OK"""
    db = setup_db
    regular_user = User(
        username="owner_student",
        email="owner_student@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(regular_user)
    db.commit()
    db.refresh(regular_user)

    token = create_access_token(user_id=regular_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    job_id = "test-job-user-owner"
    report_result = "my transcript"
    db.add(
        Job(
            job_id=job_id,
            status="completed",
            owner_id=regular_user.id,
            report_type="transcript",
            target_id=13,
            job_version=1,
        )
    )
    db.add(Report(job_id=job_id, result=report_result))
    db.commit()

    resp = client.get(f"/reports/jobs/{job_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "job_id": job_id,
        "status": "completed",
        "owner_id": regular_user.id,
        "report_type": "transcript",
        "target_id": 13,
        "result": report_result,
    }


def test_job_status_returns_queued_job_from_postgresql(setup_db):
    """A queued job is returned directly from PostgreSQL."""
    db = setup_db
    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    job_id = "job-invalid-redis-data"
    db.add(
        Job(
            job_id=job_id,
            status="queued",
            owner_id=1,
            report_type="transcript",
            target_id=14,
            job_version=1,
        )
    )
    db.commit()

    resp = client.get(f"/reports/jobs/{job_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    assert resp.json()["owner_id"] == 1
    assert resp.json()["result"] is None


def test_job_status_uses_database_owner_for_authorization(setup_db):
    """Authorization is based on the persisted Job owner."""
    db = setup_db
    regular_user = User(
        username="other_student",
        email="other_student@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(regular_user)
    db.commit()
    db.refresh(regular_user)

    job_id = "test-job-no-owner"
    db.add(
        Job(
            job_id=job_id,
            status="processing",
            owner_id=1,
            report_type="transcript",
            target_id=15,
            job_version=1,
        )
    )
    db.commit()

    # Admin access -> 200
    admin_token = create_access_token(user_id=1)
    resp = client.get(
        f"/reports/jobs/{job_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["owner_id"] == 1

    # Regular user access -> uniform 404 (no job-id enumeration)
    user_token = create_access_token(user_id=regular_user.id)
    resp = client.get(
        f"/reports/jobs/{job_id}", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


# ============================================================================
# Enrollment Data Integrity Tests
# ============================================================================


def test_enrollment_integrity_duplicate_student_and_offering_returns_409(setup_db):
    """
    Scenario 1: ADMIN creates an enrollment for a student in a course offering -> 201.
    Then attempts to create the same enrollment again with identical student_id and course_offering_id.
    Expected: 409 Conflict with detail message:
    "Student is already enrolled in this course offering"
    """
    db = setup_db
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    data = create_enrollment_authorization_data(db)

    from app.models.courseoffering import CourseOffering

    new_offering = CourseOffering(
        course_id=data["offering"].course_id,
        teacher_id=data["offering"].teacher_id,
        semester="Spring",
        academic_year=2026,
        section="SEC-DUP-TEST",
    )
    db.add(new_offering)
    db.commit()
    db.refresh(new_offering)

    # 1. Admin creates first enrollment -> 201 Created
    first_payload = {
        "student_id": data["own_student"].id,
        "course_offering_id": new_offering.id,
        "enrollment_code": "ENR-DUP-TEST-001",
    }
    first_resp = client.post("/enrollments/", json=first_payload, headers=admin_headers)
    assert first_resp.status_code == 201
    first_enrollment_id = first_resp.json()["id"]

    # 2. Admin attempts to enroll the same student in the same course offering with a different code -> 409 Conflict
    duplicate_payload = {
        "student_id": data["own_student"].id,
        "course_offering_id": new_offering.id,
        "enrollment_code": "ENR-DUP-TEST-002",
    }
    dup_resp = client.post(
        "/enrollments/", json=duplicate_payload, headers=admin_headers
    )
    assert dup_resp.status_code == 409
    assert (
        dup_resp.json()["detail"]
        == "Student is already enrolled in this course offering"
    )

    # 3. Verify session health & rollback: subsequent valid enrollment succeeds
    valid_payload = {
        "student_id": data["other_enrollment"].student_id,
        "course_offering_id": new_offering.id,
        "enrollment_code": "ENR-DUP-TEST-003",
    }
    valid_resp = client.post("/enrollments/", json=valid_payload, headers=admin_headers)
    assert valid_resp.status_code == 201
    assert valid_resp.json()["id"] != first_enrollment_id


def test_enrollment_integrity_duplicate_enrollment_code_returns_409(setup_db):
    """
    Scenario 2: ADMIN creates an enrollment, then creates another enrollment
    using an enrollment_code that is already used by another enrollment.
    Expected: 409 Conflict with detail message:
    "Enrollment code duplicate"
    """
    db = setup_db
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    data = create_enrollment_authorization_data(db)

    from app.models.courseoffering import CourseOffering

    offering_1 = CourseOffering(
        course_id=data["offering"].course_id,
        teacher_id=data["offering"].teacher_id,
        semester="Fall",
        academic_year=2026,
        section="SEC-CODE-1",
    )
    offering_2 = CourseOffering(
        course_id=data["offering"].course_id,
        teacher_id=data["offering"].teacher_id,
        semester="Fall",
        academic_year=2026,
        section="SEC-CODE-2",
    )
    db.add_all([offering_1, offering_2])
    db.commit()
    db.refresh(offering_1)
    db.refresh(offering_2)

    # 1. Admin creates first enrollment with unique code -> 201 Created
    shared_code = "ENR-SHARED-CODE-UNIQUE"
    first_payload = {
        "student_id": data["own_student"].id,
        "course_offering_id": offering_1.id,
        "enrollment_code": shared_code,
    }
    first_resp = client.post("/enrollments/", json=first_payload, headers=admin_headers)
    assert first_resp.status_code == 201

    # 2. Admin creates second enrollment for different student and offering, but duplicate code -> 409 Conflict
    dup_code_payload = {
        "student_id": data["other_enrollment"].student_id,
        "course_offering_id": offering_2.id,
        "enrollment_code": shared_code,
    }
    dup_resp = client.post(
        "/enrollments/", json=dup_code_payload, headers=admin_headers
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["detail"] == "Enrollment code duplicate"

    # 3. Verify session health & rollback: subsequent enrollment with unique code succeeds
    valid_payload = {
        "student_id": data["other_enrollment"].student_id,
        "course_offering_id": offering_2.id,
        "enrollment_code": "ENR-NEW-NON-DUPLICATE-CODE",
    }
    valid_resp = client.post("/enrollments/", json=valid_payload, headers=admin_headers)
    assert valid_resp.status_code == 201


def test_enrollment_integrity_nonexistent_student_id(setup_db):
    """
    Scenario 3: ADMIN attempts to create an enrollment with a non-existent student_id.
    Expected: 404 Not Found ("Student not found") as per POST /enrollments flowchart.
    """
    db = setup_db
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    data = create_enrollment_authorization_data(db)

    nonexistent_student_id = 999999
    payload = {
        "student_id": nonexistent_student_id,
        "course_offering_id": data["offering"].id,
        "enrollment_code": "ENR-NONEXISTENT-STUDENT-001",
    }

    response = client.post("/enrollments/", json=payload, headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"


def test_enrollment_integrity_nonexistent_course_offering_id(setup_db):
    """
    Scenario 4: ADMIN attempts to create an enrollment with a non-existent course_offering_id.
    Expected: 404 Not Found ("Course offering not found") as per POST /enrollments flowchart.
    """
    db = setup_db
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    data = create_enrollment_authorization_data(db)

    nonexistent_offering_id = 999999
    payload = {
        "student_id": data["own_student"].id,
        "course_offering_id": nonexistent_offering_id,
        "enrollment_code": "ENR-NONEXISTENT-OFFERING-001",
    }

    response = client.post("/enrollments/", json=payload, headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Course offering not found"


def test_enrollment_integrity_session_healthy_and_rollback_verified_after_integrity_error(
    setup_db,
):
    """
    Scenario 5: Ensures that after an IntegrityError occurs during create_enrollment,
    the database transaction is cleanly rolled back and the database session remains
    healthy for subsequent operations (no broken transaction state or uncommitted records).
    """
    from app.models.enrollment import Enrollment
    from sqlalchemy import select

    db = setup_db
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    data = create_enrollment_authorization_data(db)

    # Initial count of enrollments in DB
    initial_count = len(db.execute(select(Enrollment)).scalars().all())

    # Trigger an IntegrityError via duplicate student_id & course_offering_id
    duplicate_payload = {
        "student_id": data["own_student"].id,
        "course_offering_id": data["offering"].id,
        "enrollment_code": "ENR-ROLLBACK-TEST-DUP",
    }
    response = client.post(
        "/enrollments/", json=duplicate_payload, headers=admin_headers
    )
    assert response.status_code == 409

    # 1. Verify that the failed enrollment was NOT persisted to DB (proper rollback)
    count_after_failure = len(db.execute(select(Enrollment)).scalars().all())
    assert count_after_failure == initial_count

    # 2. Verify direct DB session operations work cleanly
    session_check_enrollment = db.execute(
        select(Enrollment).where(Enrollment.id == data["own_enrollment"].id)
    ).scalar_one_or_none()
    assert session_check_enrollment is not None

    # 3. Verify subsequent API creation request succeeds on the healthy session
    from app.models.courseoffering import CourseOffering

    new_offering = CourseOffering(
        course_id=data["offering"].course_id,
        teacher_id=data["offering"].teacher_id,
        semester="Spring",
        academic_year=2026,
        section="SEC-RECOVERY",
    )
    db.add(new_offering)
    db.commit()
    db.refresh(new_offering)

    success_payload = {
        "student_id": data["own_student"].id,
        "course_offering_id": new_offering.id,
        "enrollment_code": "ENR-ROLLBACK-RECOVERY-001",
    }
    success_resp = client.post(
        "/enrollments/", json=success_payload, headers=admin_headers
    )
    assert success_resp.status_code == 201

    # 4. Final count should be initial_count + 1
    final_count = len(db.execute(select(Enrollment)).scalars().all())
    assert final_count == initial_count + 1


def test_enrollment_post_flowchart_all_branches(setup_db):
    """
    Validates all branches of the POST /enrollments decision flowchart:
    1. Student does NOT exist -> 404 Not Found ('Student not found')
    2. Student exists, CourseOffering does NOT exist -> 404 Not Found ('Course offering not found')
    3. Student exists, CourseOffering exists, Enrollment already exists -> 409 Conflict ('Student is already enrolled in this course offering')
    4. Student exists, CourseOffering exists, Enrollment does not exist, code duplicated -> 409 Conflict ('Enrollment code duplicate')
    5. Student exists, CourseOffering exists, Enrollment does not exist, code unique -> 201 Created (INSERT)
    """
    db = setup_db
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    data = create_enrollment_authorization_data(db)

    from app.models.courseoffering import CourseOffering

    # Branch 1: هل Student موجود؟ -> لا -> 404
    resp_no_student = client.post(
        "/enrollments/",
        json={
            "student_id": 999999,
            "course_offering_id": data["offering"].id,
            "enrollment_code": "FLOW-TEST-001",
        },
        headers=admin_headers,
    )
    assert resp_no_student.status_code == 404
    assert resp_no_student.json()["detail"] == "Student not found"

    # Branch 2: هل Student موجود؟ -> نعم | هل CourseOffering موجود؟ -> لا -> 404
    resp_no_offering = client.post(
        "/enrollments/",
        json={
            "student_id": data["own_student"].id,
            "course_offering_id": 999999,
            "enrollment_code": "FLOW-TEST-002",
        },
        headers=admin_headers,
    )
    assert resp_no_offering.status_code == 404
    assert resp_no_offering.json()["detail"] == "Course offering not found"

    # Branch 3: هل Student موجود؟ -> نعم | هل CourseOffering موجود؟ -> نعم | هل التسجيل موجود؟ -> نعم -> 409
    resp_existing_enrollment = client.post(
        "/enrollments/",
        json={
            "student_id": data["own_enrollment"].student_id,
            "course_offering_id": data["own_enrollment"].course_offering_id,
            "enrollment_code": "FLOW-TEST-NEW-CODE",
        },
        headers=admin_headers,
    )
    assert resp_existing_enrollment.status_code == 409
    assert (
        resp_existing_enrollment.json()["detail"]
        == "Student is already enrolled in this course offering"
    )

    # Branch 4: هل Student موجود؟ -> نعم | هل CourseOffering موجود؟ -> نعم | هل التسجيل موجود؟ -> لا | هل code مكرر؟ -> نعم -> 409
    new_offering = CourseOffering(
        course_id=data["offering"].course_id,
        teacher_id=data["offering"].teacher_id,
        semester="Summer",
        academic_year=2026,
        section="SEC-FLOW",
    )
    db.add(new_offering)
    db.commit()
    db.refresh(new_offering)

    resp_duplicate_code = client.post(
        "/enrollments/",
        json={
            "student_id": data["own_student"].id,
            "course_offering_id": new_offering.id,
            "enrollment_code": data["own_enrollment"].enrollment_code,
        },
        headers=admin_headers,
    )
    assert resp_duplicate_code.status_code == 409
    assert resp_duplicate_code.json()["detail"] == "Enrollment code duplicate"

    # Branch 5: هل Student موجود؟ -> نعم | هل CourseOffering موجود؟ -> نعم | هل التسجيل موجود؟ -> لا | هل code مكرر؟ -> لا -> INSERT -> 201
    resp_success = client.post(
        "/enrollments/",
        json={
            "student_id": data["own_student"].id,
            "course_offering_id": new_offering.id,
            "enrollment_code": "FLOW-SUCCESS-UNIQUE-001",
        },
        headers=admin_headers,
    )
    assert resp_success.status_code == 201
    assert resp_success.json()["enrollment_code"] == "FLOW-SUCCESS-UNIQUE-001"
    assert resp_success.json()["student_id"] == data["own_student"].id
    assert resp_success.json()["course_offering_id"] == new_offering.id


# ============================================================================
# Course API Tests
# ============================================================================


def create_course_test_environment(db):
    """Helper to create real College, Department, and Course in test DB."""
    from app.models.college import College
    from app.models.course import Course
    from app.models.department import Department

    college = College(name="Engineering College Course Test", code="ENG_CRS_T")
    db.add(college)
    db.commit()
    db.refresh(college)

    department = Department(
        name="Computer Science Course Test",
        code="CS_CRS_T",
        college_id=college.id,
    )
    db.add(department)
    db.commit()
    db.refresh(department)

    course = Course(
        name="Introduction to Computer Science",
        code="CS101_T",
        department_id=department.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    return {
        "college": college,
        "department": department,
        "course": course,
    }


def create_course_test_user(db):
    """Helper to create a real regular User in test DB."""
    user = User(
        username="course_test_user",
        email="course_user@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ----------------------------------------------------------------------------
# Authentication Tests (1-5)
# ----------------------------------------------------------------------------


def test_course_get_by_id_unauthenticated_returns_401(setup_db):
    """1. GET /courses/{course_id} without Authentication -> 401"""
    env = create_course_test_environment(setup_db)
    response = client.get(f"/courses/{env['course'].id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "not authenticated"


def test_course_get_all_unauthenticated_returns_401(setup_db):
    """2. GET /courses/ without Authentication -> 401"""
    create_course_test_environment(setup_db)
    response = client.get("/courses/")
    assert response.status_code == 401
    assert response.json()["detail"] == "not authenticated"


def test_course_post_unauthenticated_returns_401(setup_db):
    """3. POST /courses/ without Authentication -> 401"""
    env = create_course_test_environment(setup_db)
    payload = {
        "name": "Database Systems",
        "code": "CS202_T",
        "department_id": env["department"].id,
    }
    response = client.post("/courses/", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "not authenticated"


def test_course_put_unauthenticated_returns_401(setup_db):
    """4. PUT /courses/{course_id} without Authentication -> 401"""
    env = create_course_test_environment(setup_db)
    payload = {"name": "Updated Course Name"}
    response = client.put(f"/courses/{env['course'].id}", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "not authenticated"


def test_course_delete_unauthenticated_returns_401(setup_db):
    """5. DELETE /courses/{course_id} without Authentication -> 401"""
    env = create_course_test_environment(setup_db)
    response = client.delete(f"/courses/{env['course'].id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "not authenticated"


# ----------------------------------------------------------------------------
# Authorization Tests (6-8)
# ----------------------------------------------------------------------------


def test_course_user_cannot_create_course_returns_403(setup_db):
    """6. USER role attempts POST /courses/ -> 403"""
    env = create_course_test_environment(setup_db)
    user = create_course_test_user(setup_db)
    user_token = create_access_token(user_id=user.id)
    user_headers = {"Authorization": f"Bearer {user_token}"}

    payload = {
        "name": "Software Engineering",
        "code": "CS303_T",
        "department_id": env["department"].id,
    }
    response = client.post("/courses/", json=payload, headers=user_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden"


def test_course_user_cannot_update_course_returns_403(setup_db):
    """7. USER role attempts PUT /courses/{course_id} -> 403"""
    env = create_course_test_environment(setup_db)
    user = create_course_test_user(setup_db)
    user_token = create_access_token(user_id=user.id)
    user_headers = {"Authorization": f"Bearer {user_token}"}

    payload = {"name": "Unauthorized Update"}
    response = client.put(
        f"/courses/{env['course'].id}", json=payload, headers=user_headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden"


def test_course_user_cannot_delete_course_returns_403(setup_db):
    """8. USER role attempts DELETE /courses/{course_id} -> 403"""
    env = create_course_test_environment(setup_db)
    user = create_course_test_user(setup_db)
    user_token = create_access_token(user_id=user.id)
    user_headers = {"Authorization": f"Bearer {user_token}"}

    response = client.delete(f"/courses/{env['course'].id}", headers=user_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden"


# ----------------------------------------------------------------------------
# Happy Paths & Functional Tests (9-15)
# ----------------------------------------------------------------------------


def test_course_admin_creates_course_returns_201_and_persists_in_db(setup_db):
    """9. ADMIN creates a new Course -> 201, verify persisted in real DB"""
    from app.models.course import Course

    db = setup_db
    env = create_course_test_environment(db)
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {
        "name": "Algorithms & Complexity",
        "code": "CS204_T",
        "department_id": env["department"].id,
    }
    response = client.post("/courses/", json=payload, headers=admin_headers)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Algorithms & Complexity"
    assert data["code"] == "CS204_T"
    assert data["department_id"] == env["department"].id
    assert "id" in data
    assert "created_at" in data

    # Verify directly in real database
    created_course_id = data["id"]
    db.expire_all()
    db_course = db.get(Course, created_course_id)
    assert db_course is not None
    assert db_course.name == "Algorithms & Complexity"
    assert db_course.code == "CS204_T"
    assert db_course.department_id == env["department"].id


def test_course_user_can_get_existing_course_returns_200_with_valid_data(setup_db):
    """10. USER can GET /courses/{course_id} for existing Course -> 200, verify data accuracy"""
    db = setup_db
    env = create_course_test_environment(db)
    user = create_course_test_user(db)
    user_token = create_access_token(user_id=user.id)
    user_headers = {"Authorization": f"Bearer {user_token}"}

    response = client.get(f"/courses/{env['course'].id}", headers=user_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == env["course"].id
    assert data["name"] == env["course"].name
    assert data["code"] == env["course"].code
    assert data["department_id"] == env["course"].department_id
    assert "created_at" in data


def test_course_admin_can_get_existing_course_returns_200(setup_db):
    """11. ADMIN can GET /courses/{course_id} for existing Course -> 200"""
    db = setup_db
    env = create_course_test_environment(db)
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.get(f"/courses/{env['course'].id}", headers=admin_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == env["course"].id
    assert data["name"] == env["course"].name
    assert data["code"] == env["course"].code
    assert data["department_id"] == env["course"].department_id


def test_course_get_nonexistent_course_returns_404(setup_db):
    """12. GET /courses/{course_id} for non-existent Course -> 404"""
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    non_existent_id = 999999
    response = client.get(f"/courses/{non_existent_id}", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found"


def test_course_get_all_courses_returns_200_with_expected_list(setup_db):
    """13. GET /courses/ -> 200, verify list contains existing courses"""
    from app.models.course import Course

    db = setup_db
    env = create_course_test_environment(db)

    # Add another course to the department
    extra_course = Course(
        name="Discrete Mathematics",
        code="MATH201_T",
        department_id=env["department"].id,
    )
    db.add(extra_course)
    db.commit()
    db.refresh(extra_course)

    user = create_course_test_user(db)
    user_token = create_access_token(user_id=user.id)
    user_headers = {"Authorization": f"Bearer {user_token}"}

    response = client.get("/courses/", headers=user_headers)
    assert response.status_code == 200

    courses_list = response.json()
    assert isinstance(courses_list, list)
    retrieved_ids = {c["id"] for c in courses_list}
    assert env["course"].id in retrieved_ids
    assert extra_course.id in retrieved_ids

    # Verify matching fields
    course_map = {c["id"]: c for c in courses_list}
    assert course_map[env["course"].id]["name"] == env["course"].name
    assert course_map[env["course"].id]["code"] == env["course"].code
    assert course_map[extra_course.id]["name"] == "Discrete Mathematics"
    assert course_map[extra_course.id]["code"] == "MATH201_T"


def test_course_admin_updates_existing_course_returns_200_and_updates_db(setup_db):
    """14. ADMIN updates existing Course -> 200, verify changes persisted in real DB"""
    from app.models.course import Course

    db = setup_db
    env = create_course_test_environment(db)
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    update_payload = {
        "name": "Advanced Programming & Design",
        "code": "CS102_T",
    }
    response = client.put(
        f"/courses/{env['course'].id}", json=update_payload, headers=admin_headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == env["course"].id
    assert data["name"] == "Advanced Programming & Design"
    assert data["code"] == "CS102_T"
    assert data["department_id"] == env["course"].department_id

    # Verify directly in real database
    db.expire_all()
    db_course = db.get(Course, env["course"].id)
    assert db_course is not None
    assert db_course.name == "Advanced Programming & Design"
    assert db_course.code == "CS102_T"


def test_course_admin_deletes_existing_course_returns_200_and_removes_from_db(setup_db):
    """15. ADMIN deletes existing Course without dependencies -> 200, verify removed from DB"""
    from app.models.course import Course

    db = setup_db
    env = create_course_test_environment(db)
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    course_to_delete_id = env["course"].id

    # Verify course exists in DB before deletion
    assert db.get(Course, course_to_delete_id) is not None

    response = client.delete(f"/courses/{course_to_delete_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {"message": "Course deleted successfully"}

    # Verify course no longer exists in DB
    db.expire_all()
    db_course = db.get(Course, course_to_delete_id)
    assert db_course is None


# ============================================================================
# College API Tests
# ============================================================================


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/colleges/", None),
        ("get", "/colleges/1", None),
        ("post", "/colleges/", {"name": "College of Arts", "code": "ART"}),
        ("put", "/colleges/1", {"name": "Updated College"}),
        ("delete", "/colleges/1", None),
    ],
)
def test_college_endpoints_require_authentication(setup_db, method, path, payload):
    request_fn = getattr(client, method)
    resp = request_fn(path, json=payload) if payload else request_fn(path)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "not authenticated"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/colleges/", {"name": "College of Music", "code": "MUS"}),
        ("put", "/colleges/1", {"name": "Updated College"}),
        ("delete", "/colleges/1", None),
    ],
)
def test_college_admin_endpoints_forbidden_for_user(setup_db, method, path, payload):
    db = setup_db
    user = User(
        username="college_user",
        email="college_user@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    user_token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {user_token}"}

    request_fn = getattr(client, method)
    resp = (
        request_fn(path, json=payload, headers=headers)
        if payload
        else request_fn(path, headers=headers)
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "forbidden"


def test_college_admin_creates_college_returns_201_and_persists_in_db(setup_db):
    db = setup_db
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {"name": "Faculty of Medicine", "code": "MED"}
    resp = client.post("/colleges/", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Faculty of Medicine"
    assert data["code"] == "MED"
    assert "id" in data

    from app.models.college import College

    db.expire_all()
    db_college = db.get(College, data["id"])
    assert db_college is not None
    assert db_college.name == "Faculty of Medicine"
    assert db_college.code == "MED"


def test_college_create_duplicate_code_returns_409_and_rolls_back(setup_db):
    db = setup_db
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.college import College

    college = College(name="Existing College", code="EXIST")
    db.add(college)
    db.commit()

    resp = client.post(
        "/colleges/",
        json={"name": "Duplicate Code College", "code": "EXIST"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "College code or constraint conflict"

    # Verify session remains healthy
    db.expire_all()
    assert len(db.execute(select(College)).scalars().all()) == 1


def test_college_get_by_id_returns_200_and_404_for_nonexistent(setup_db):
    db = setup_db
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.college import College

    college = College(name="Science College", code="SCI_COL")
    db.add(college)
    db.commit()
    db.refresh(college)

    resp = client.get(f"/colleges/{college.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Science College"

    resp_404 = client.get("/colleges/999999", headers=headers)
    assert resp_404.status_code == 404
    assert resp_404.json()["detail"] == "College not found"


@pytest.mark.parametrize("skip,limit", [(-1, 10), (0, 0), (0, 101)])
def test_college_pagination_validation_limits(setup_db, skip, limit):
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = client.get(f"/colleges/?skip={skip}&limit={limit}", headers=headers)
    assert resp.status_code == 422


def test_college_admin_updates_college_returns_200_and_updates_db(setup_db):
    db = setup_db
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.college import College

    college = College(name="Old College Name", code="OLD_C")
    db.add(college)
    db.commit()
    db.refresh(college)

    resp = client.put(
        f"/colleges/{college.id}",
        json={"name": "New College Name", "code": "NEW_C"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New College Name"
    assert resp.json()["code"] == "NEW_C"

    db.expire_all()
    updated = db.get(College, college.id)
    assert updated.name == "New College Name"
    assert updated.code == "NEW_C"


def test_college_admin_deletes_college_returns_200_and_removes_from_db(setup_db):
    db = setup_db
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.college import College

    college = College(name="College To Delete", code="DEL_C")
    db.add(college)
    db.commit()
    db.refresh(college)
    college_id = college.id

    resp = client.delete(f"/colleges/{college_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"message": "College deleted successfully"}

    db.expire_all()
    assert db.get(College, college_id) is None


# ============================================================================
# Department API Tests
# ============================================================================


def create_department_test_setup(db):
    from app.models.college import College

    college1 = College(name="Engineering Dept College 1", code="D_COL1")
    college2 = College(name="Science Dept College 2", code="D_COL2")
    db.add_all([college1, college2])
    db.commit()
    db.refresh(college1)
    db.refresh(college2)
    return {"college1": college1, "college2": college2}


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/departments/", None),
        ("get", "/departments/1", None),
        (
            "post",
            "/departments/",
            {"name": "Electrical", "code": "EE", "college_id": 1},
        ),
        ("put", "/departments/1", {"name": "Updated EE"}),
        ("delete", "/departments/1", None),
    ],
)
def test_department_endpoints_require_authentication(setup_db, method, path, payload):
    request_fn = getattr(client, method)
    resp = request_fn(path, json=payload) if payload else request_fn(path)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "not authenticated"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "post",
            "/departments/",
            {"name": "Electrical", "code": "EE", "college_id": 1},
        ),
        ("put", "/departments/1", {"name": "Updated EE"}),
        ("delete", "/departments/1", None),
    ],
)
def test_department_admin_endpoints_forbidden_for_user(setup_db, method, path, payload):
    db = setup_db
    user = User(
        username="dept_user",
        email="dept_user@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    user_token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {user_token}"}

    request_fn = getattr(client, method)
    resp = (
        request_fn(path, json=payload, headers=headers)
        if payload
        else request_fn(path, headers=headers)
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "forbidden"


def test_department_admin_creates_department_returns_201_and_persists_in_db(setup_db):
    db = setup_db
    data = create_department_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {
        "name": "Computer Systems",
        "code": "CSYS",
        "college_id": data["college1"].id,
    }
    resp = client.post("/departments/", json=payload, headers=headers)
    assert resp.status_code == 201
    res_data = resp.json()
    assert res_data["name"] == "Computer Systems"
    assert res_data["code"] == "CSYS"
    assert res_data["college_id"] == data["college1"].id

    from app.models.department import Department

    db.expire_all()
    db_dept = db.get(Department, res_data["id"])
    assert db_dept is not None
    assert db_dept.name == "Computer Systems"
    assert db_dept.code == "CSYS"


def test_department_unique_constraint_per_college_and_cross_college_allowed(setup_db):
    """
    Department has composite unique constraints: (college_id, name) and (college_id, code).
    Same code in same college -> 409 Conflict.
    Same code in DIFFERENT college -> 201 Allowed.
    """
    db = setup_db
    data = create_department_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create first department in College 1
    resp1 = client.post(
        "/departments/",
        json={
            "name": "Civil Engineering",
            "code": "CIV",
            "college_id": data["college1"].id,
        },
        headers=headers,
    )
    assert resp1.status_code == 201

    # 2. Duplicate code in SAME college -> 409 Conflict
    resp_dup = client.post(
        "/departments/",
        json={"name": "Civil Tech", "code": "CIV", "college_id": data["college1"].id},
        headers=headers,
    )
    assert resp_dup.status_code == 409
    assert (
        resp_dup.json()["detail"] == "Department code or name conflict in this college"
    )

    # 3. Same code in DIFFERENT college -> 201 Created
    resp_diff_college = client.post(
        "/departments/",
        json={
            "name": "Civil Science",
            "code": "CIV",
            "college_id": data["college2"].id,
        },
        headers=headers,
    )
    assert resp_diff_college.status_code == 201


def test_department_get_by_id_returns_200_and_404_for_nonexistent(setup_db):
    db = setup_db
    data = create_department_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.department import Department

    dept = Department(
        name="Mechanical Eng", code="MECH", college_id=data["college1"].id
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)

    resp = client.get(f"/departments/{dept.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Mechanical Eng"

    resp_404 = client.get("/departments/999999", headers=headers)
    assert resp_404.status_code == 404
    assert resp_404.json()["detail"] == "Department not found"


def test_department_admin_updates_and_deletes_department(setup_db):
    db = setup_db
    data = create_department_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.department import Department

    dept = Department(
        name="Old Dept Name", code="OLD_D", college_id=data["college1"].id
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    dept_id = dept.id

    # Update -> 200
    update_resp = client.put(
        f"/departments/{dept_id}",
        json={"name": "Updated Dept Name", "code": "NEW_D"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Dept Name"

    db.expire_all()
    updated = db.get(Department, dept_id)
    assert updated.name == "Updated Dept Name"

    # Delete -> 200
    del_resp = client.delete(f"/departments/{dept_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json() == {"message": "Department deleted successfully"}

    db.expire_all()
    assert db.get(Department, dept_id) is None


# ============================================================================
# Teacher API Tests
# ============================================================================


def create_teacher_test_setup(db):
    from app.models.college import College
    from app.models.department import Department

    college = College(name="Teacher Test College", code="T_COL")
    db.add(college)
    db.commit()
    db.refresh(college)

    dept = Department(name="Teacher Test Dept", code="T_DEP", college_id=college.id)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return {"college": college, "department": dept}


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/teachers/", None),
        ("get", "/teachers/1", None),
        ("post", "/teachers/", {"name": "Dr. Smith", "department_id": 1}),
        ("put", "/teachers/1", {"name": "Dr. Updated"}),
        ("delete", "/teachers/1", None),
    ],
)
def test_teacher_endpoints_require_authentication(setup_db, method, path, payload):
    request_fn = getattr(client, method)
    resp = request_fn(path, json=payload) if payload else request_fn(path)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "not authenticated"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/teachers/", {"name": "Dr. Alan", "department_id": 1}),
        ("put", "/teachers/1", {"name": "Dr. Alan Updated"}),
        ("delete", "/teachers/1", None),
    ],
)
def test_teacher_admin_endpoints_forbidden_for_user(setup_db, method, path, payload):
    db = setup_db
    user = User(
        username="teacher_user",
        email="teacher_user@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    user_token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {user_token}"}

    request_fn = getattr(client, method)
    resp = (
        request_fn(path, json=payload, headers=headers)
        if payload
        else request_fn(path, headers=headers)
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "forbidden"


def test_teacher_admin_creates_teacher_returns_201_and_persists_in_db(setup_db):
    db = setup_db
    data = create_teacher_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {"name": "Dr. Alan Turing", "department_id": data["department"].id}
    resp = client.post("/teachers/", json=payload, headers=headers)
    assert resp.status_code == 201
    res_data = resp.json()
    assert res_data["name"] == "Dr. Alan Turing"
    assert res_data["department_id"] == data["department"].id

    from app.models.teacher import Teacher

    db.expire_all()
    db_teacher = db.get(Teacher, res_data["id"])
    assert db_teacher is not None
    assert db_teacher.name == "Dr. Alan Turing"


def test_teacher_get_by_id_and_all_returns_200_and_404(setup_db):
    db = setup_db
    data = create_teacher_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.teacher import Teacher

    t1 = Teacher(name="Prof. Donald Knuth", department_id=data["department"].id)
    t2 = Teacher(name="Prof. Claude Shannon", department_id=data["department"].id)
    db.add_all([t1, t2])
    db.commit()
    db.refresh(t1)
    db.refresh(t2)

    # Get single -> 200
    resp_single = client.get(f"/teachers/{t1.id}", headers=headers)
    assert resp_single.status_code == 200
    assert resp_single.json()["name"] == "Prof. Donald Knuth"

    # Get list -> 200
    resp_list = client.get("/teachers/", headers=headers)
    assert resp_list.status_code == 200
    retrieved_ids = {t["id"] for t in resp_list.json()}
    assert t1.id in retrieved_ids
    assert t2.id in retrieved_ids

    # 404 for non-existent
    resp_404 = client.get("/teachers/999999", headers=headers)
    assert resp_404.status_code == 404
    assert resp_404.json()["detail"] == "Teacher not found"


def test_teacher_admin_updates_and_deletes_teacher(setup_db):
    db = setup_db
    data = create_teacher_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.teacher import Teacher

    teacher = Teacher(name="Prof. Barbara Liskov", department_id=data["department"].id)
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    teacher_id = teacher.id

    # Update -> 200
    resp_up = client.put(
        f"/teachers/{teacher_id}", json={"name": "Prof. B. Liskov"}, headers=headers
    )
    assert resp_up.status_code == 200
    assert resp_up.json()["name"] == "Prof. B. Liskov"

    db.expire_all()
    assert db.get(Teacher, teacher_id).name == "Prof. B. Liskov"

    # Delete -> 200
    resp_del = client.delete(f"/teachers/{teacher_id}", headers=headers)
    assert resp_del.status_code == 200
    assert resp_del.json() == {"message": "Teacher deleted successfully"}

    db.expire_all()
    assert db.get(Teacher, teacher_id) is None


# ============================================================================
# CourseOffering API Tests
# ============================================================================


def create_offering_test_setup(db):
    from app.models.college import College
    from app.models.course import Course
    from app.models.department import Department
    from app.models.teacher import Teacher

    college = College(name="Offering Test College", code="OFF_COL")
    db.add(college)
    db.commit()
    db.refresh(college)

    dept = Department(name="Offering Test Dept", code="OFF_DEP", college_id=college.id)
    db.add(dept)
    db.commit()
    db.refresh(dept)

    teacher = Teacher(name="Offering Prof", department_id=dept.id)
    course = Course(name="Offering Course", code="OFF101", department_id=dept.id)
    db.add_all([teacher, course])
    db.commit()
    db.refresh(teacher)
    db.refresh(course)

    return {
        "college": college,
        "department": dept,
        "teacher": teacher,
        "course": course,
    }


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/course-offerings/", None),
        ("get", "/course-offerings/1", None),
        (
            "post",
            "/course-offerings/",
            {
                "course_id": 1,
                "teacher_id": 1,
                "semester": "Fall",
                "academic_year": 2026,
                "section": "A",
            },
        ),
        ("put", "/course-offerings/1", {"semester": "Spring"}),
        ("delete", "/course-offerings/1", None),
    ],
)
def test_course_offering_endpoints_require_authentication(
    setup_db, method, path, payload
):
    request_fn = getattr(client, method)
    resp = request_fn(path, json=payload) if payload else request_fn(path)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "not authenticated"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "post",
            "/course-offerings/",
            {
                "course_id": 1,
                "teacher_id": 1,
                "semester": "Fall",
                "academic_year": 2026,
                "section": "A",
            },
        ),
        ("put", "/course-offerings/1", {"semester": "Spring"}),
        ("delete", "/course-offerings/1", None),
    ],
)
def test_course_offering_admin_endpoints_forbidden_for_user(
    setup_db, method, path, payload
):
    db = setup_db
    user = User(
        username="offering_user",
        email="offering_user@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    user_token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {user_token}"}

    request_fn = getattr(client, method)
    resp = (
        request_fn(path, json=payload, headers=headers)
        if payload
        else request_fn(path, headers=headers)
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "forbidden"


def test_course_offering_admin_creates_and_handles_unique_constraint(setup_db):
    db = setup_db
    data = create_offering_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {
        "course_id": data["course"].id,
        "teacher_id": data["teacher"].id,
        "semester": "Fall",
        "academic_year": 2026,
        "section": "SEC-A",
    }
    # 1. Successful creation -> 201
    resp = client.post("/course-offerings/", json=payload, headers=headers)
    assert resp.status_code == 201
    offering_id = resp.json()["id"]

    from app.models.courseoffering import CourseOffering

    db.expire_all()
    db_offering = db.get(CourseOffering, offering_id)
    assert db_offering is not None
    assert db_offering.section == "SEC-A"

    # 2. Duplicate offering conflict -> 409
    resp_dup = client.post("/course-offerings/", json=payload, headers=headers)
    assert resp_dup.status_code == 409
    assert resp_dup.json()["detail"] == "Duplicate course offering constraint"

    # 3. Different section -> 201
    payload_sec_b = dict(payload, section="SEC-B")
    resp_b = client.post("/course-offerings/", json=payload_sec_b, headers=headers)
    assert resp_b.status_code == 201


def test_course_offering_get_update_delete_and_404(setup_db):
    db = setup_db
    data = create_offering_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.courseoffering import CourseOffering

    offering = CourseOffering(
        course_id=data["course"].id,
        teacher_id=data["teacher"].id,
        semester="Spring",
        academic_year=2026,
        section="SEC-1",
    )
    db.add(offering)
    db.commit()
    db.refresh(offering)
    offering_id = offering.id

    # Get by ID -> 200
    resp_get = client.get(f"/course-offerings/{offering_id}", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["section"] == "SEC-1"

    # Update -> 200
    resp_put = client.put(
        f"/course-offerings/{offering_id}",
        json={"section": "SEC-1-MOD"},
        headers=headers,
    )
    assert resp_put.status_code == 200
    assert resp_put.json()["section"] == "SEC-1-MOD"

    # Delete -> 200
    resp_del = client.delete(f"/course-offerings/{offering_id}", headers=headers)
    assert resp_del.status_code == 200
    assert resp_del.json() == {"message": "Course offering deleted successfully"}

    db.expire_all()
    assert db.get(CourseOffering, offering_id) is None

    # 404 for deleted
    resp_404 = client.get(f"/course-offerings/{offering_id}", headers=headers)
    assert resp_404.status_code == 404
    assert resp_404.json()["detail"] == "Course offering not found"


# ============================================================================
# CourseSchedule API Tests
# ============================================================================


def create_schedule_test_setup(db):
    from app.models.college import College
    from app.models.course import Course
    from app.models.courseoffering import CourseOffering
    from app.models.department import Department
    from app.models.teacher import Teacher

    college = College(name="Schedule Test College", code="SCH_COL")
    db.add(college)
    db.commit()
    db.refresh(college)

    dept = Department(name="Schedule Test Dept", code="SCH_DEP", college_id=college.id)
    db.add(dept)
    db.commit()
    db.refresh(dept)

    teacher = Teacher(name="Schedule Prof", department_id=dept.id)
    course = Course(name="Schedule Course", code="SCH101", department_id=dept.id)
    db.add_all([teacher, course])
    db.commit()
    db.refresh(teacher)
    db.refresh(course)

    offering = CourseOffering(
        course_id=course.id,
        teacher_id=teacher.id,
        semester="Fall",
        academic_year=2026,
        section="A",
    )
    db.add(offering)
    db.commit()
    db.refresh(offering)

    return {"offering": offering}


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/course-schedules/", None),
        ("get", "/course-schedules/1", None),
        (
            "post",
            "/course-schedules/",
            {
                "day": "Monday",
                "schedule_type": "Lecture",
                "start_time": "09:00:00",
                "end_time": "10:30:00",
                "room": "R101",
                "course_offering_id": 1,
            },
        ),
        ("put", "/course-schedules/1", {"room": "R102"}),
        ("delete", "/course-schedules/1", None),
    ],
)
def test_course_schedule_endpoints_require_authentication(
    setup_db, method, path, payload
):
    request_fn = getattr(client, method)
    resp = request_fn(path, json=payload) if payload else request_fn(path)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "not authenticated"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "post",
            "/course-schedules/",
            {
                "day": "Monday",
                "schedule_type": "Lecture",
                "start_time": "09:00:00",
                "end_time": "10:30:00",
                "room": "R101",
                "course_offering_id": 1,
            },
        ),
        ("put", "/course-schedules/1", {"room": "R102"}),
        ("delete", "/course-schedules/1", None),
    ],
)
def test_course_schedule_admin_endpoints_forbidden_for_user(
    setup_db, method, path, payload
):
    db = setup_db
    user = User(
        username="schedule_user",
        email="schedule_user@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    user_token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {user_token}"}

    request_fn = getattr(client, method)
    resp = (
        request_fn(path, json=payload, headers=headers)
        if payload
        else request_fn(path, headers=headers)
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "forbidden"


def test_course_schedule_time_validation_and_creation(setup_db):
    db = setup_db
    data = create_schedule_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Invalid time range: end_time <= start_time -> 422
    invalid_time_payload = {
        "day": "Monday",
        "schedule_type": "Lecture",
        "start_time": "11:00:00",
        "end_time": "10:00:00",
        "room": "Room-1",
        "course_offering_id": data["offering"].id,
    }
    resp_invalid = client.post(
        "/course-schedules/", json=invalid_time_payload, headers=headers
    )
    assert resp_invalid.status_code == 422

    # 1b. The DB CHECK constraint is the final arbiter even for raw inserts.
    from sqlalchemy import text as sa_text
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    with pytest.raises(SAIntegrityError):
        db.execute(
            sa_text(
                "INSERT INTO course_schedule (day, schedule_type, start_time, "
                "end_time, room, course_offering_id) "
                "VALUES ('Tuesday', 'Lab', '14:00', '13:00', 'R9', :offering_id)"
            ),
            {"offering_id": data["offering"].id},
        )
    db.rollback()


def test_enrollment_db_constraints_are_the_final_arbiter(setup_db):
    """Raw inserts bypassing Pydantic are still stopped by CHECK constraints."""
    from sqlalchemy import text as sa_text
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    db = setup_db
    data = create_enrollment_authorization_data(db)
    student_id = data["own_student"].id
    offering_id = data["offering"].id

    # grade out of range -> rejected by the DB, not just Pydantic.
    with pytest.raises(SAIntegrityError):
        db.execute(
            sa_text(
                "INSERT INTO enrollment (student_id, course_offering_id, "
                "enrollment_code, grade) VALUES (:s, :o, 'ENR-DB-1', 150)"
            ),
            {"s": student_id, "o": offering_id},
        )
    db.rollback()

    # active and withdrawn at once -> contradictory state rejected.
    with pytest.raises(SAIntegrityError):
        db.execute(
            sa_text(
                "INSERT INTO enrollment (student_id, course_offering_id, "
                "enrollment_code, is_active, is_withdrawn) "
                "VALUES (:s, :o, 'ENR-DB-2', true, true)"
            ),
            {"s": student_id, "o": offering_id},
        )
    db.rollback()


def test_course_schedule_valid_creation_and_duplicate_conflict(setup_db):
    # 2. Valid creation -> 201
    db = setup_db
    data = create_schedule_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}
    valid_payload = {
        "day": "Monday",
        "schedule_type": "Lecture",
        "start_time": "09:00:00",
        "end_time": "10:30:00",
        "room": "Room-1",
        "course_offering_id": data["offering"].id,
    }
    resp_valid = client.post("/course-schedules/", json=valid_payload, headers=headers)
    assert resp_valid.status_code == 201
    schedule_id = resp_valid.json()["id"]

    from app.models.courseschedule import CourseSchedule

    db.expire_all()
    db_schedule = db.get(CourseSchedule, schedule_id)
    assert db_schedule is not None
    assert db_schedule.room == "Room-1"

    # 3. Duplicate schedule on same offering/day/start/end -> 409
    resp_dup = client.post("/course-schedules/", json=valid_payload, headers=headers)
    assert resp_dup.status_code == 409
    assert resp_dup.json()["detail"] == "Schedule conflict or constraint violation"


def test_course_schedule_get_update_delete_and_404(setup_db):
    import datetime

    db = setup_db
    data = create_schedule_test_setup(db)
    admin_token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.courseschedule import CourseSchedule

    schedule = CourseSchedule(
        day="Tuesday",
        schedule_type="Lab",
        start_time=datetime.time(13, 0, 0),
        end_time=datetime.time(15, 0, 0),
        room="Lab-A",
        course_offering_id=data["offering"].id,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    schedule_id = schedule.id

    # Read -> 200
    resp_get = client.get(f"/course-schedules/{schedule_id}", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["room"] == "Lab-A"

    # Update invalid time -> 422
    resp_inv_update = client.put(
        f"/course-schedules/{schedule_id}",
        json={"start_time": "16:00:00"},
        headers=headers,
    )
    assert resp_inv_update.status_code == 422

    # Update valid -> 200
    resp_up = client.put(
        f"/course-schedules/{schedule_id}", json={"room": "Lab-B"}, headers=headers
    )
    assert resp_up.status_code == 200
    assert resp_up.json()["room"] == "Lab-B"

    # Delete -> 200
    resp_del = client.delete(f"/course-schedules/{schedule_id}", headers=headers)
    assert resp_del.status_code == 200
    assert resp_del.json() == {"message": "Course schedule deleted successfully"}

    db.expire_all()
    assert db.get(CourseSchedule, schedule_id) is None


# ============================================================================
# User API Tests
# ============================================================================


def test_user_register_and_duplicate_conflict():
    payload = {
        "username": "register_test_user",
        "email": "register_test@example.com",
        "password": "Password123!",
    }
    # 1. Register -> 201
    resp = client.post("/users/register", json=payload)
    assert resp.status_code == 201
    assert resp.json()["username"] == "register_test_user"
    assert resp.json()["role"] == "guest"

    # 2. Duplicate username/email -> 409
    dup_resp = client.post("/users/register", json=payload)
    assert dup_resp.status_code == 409
    assert dup_resp.json()["detail"] == "Username or email already exists"


def test_user_login_success_and_invalid_credentials(setup_db):
    db = setup_db
    user = User(
        username="login_test_user",
        email="login_test@example.com",
        password_hash=hash_password("ValidPassword123!"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()

    # Successful login -> 200 + token
    resp_ok = client.post(
        "/users/login",
        json={"email": "login_test@example.com", "password": "ValidPassword123!"},
    )
    assert resp_ok.status_code == 200
    assert "access_token" in resp_ok.json()

    # Wrong password -> 401
    resp_wrong_pw = client.post(
        "/users/login",
        json={"email": "login_test@example.com", "password": "WrongPassword!"},
    )
    assert resp_wrong_pw.status_code == 401
    assert resp_wrong_pw.json()["detail"] == "user or password incorrect"

    # Nonexistent email -> 401
    resp_nonexistent = client.post(
        "/users/login",
        json={"email": "nonexistent@example.com", "password": "ValidPassword123!"},
    )
    assert resp_nonexistent.status_code == 401
    assert resp_nonexistent.json()["detail"] == "user or password incorrect"


def test_user_self_update_me(setup_db):
    db = setup_db
    user = User(
        username="me_user",
        email="me_user@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.put(
        "/users/me", json={"username": "me_user_updated"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "me_user_updated"

    db.expire_all()
    assert db.get(User, user.id).username == "me_user_updated"


def test_password_change_invalidates_previously_issued_tokens(setup_db):
    """A token issued before a password change must stop working immediately."""
    db = setup_db
    user = User(
        username="stale_token_user",
        email="stale_token@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    old_token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {old_token}"}

    assert client.get("/users/me", headers=headers).status_code == 200

    resp = client.put(
        "/users/me", json={"password": "NewPassword456!"}, headers=headers
    )
    assert resp.status_code == 200

    # The pre-change token must now be rejected.
    resp_old = client.get("/users/me", headers=headers)
    assert resp_old.status_code == 401

    # Logging in with the new password returns a fresh, working token.
    resp_login = client.post(
        "/users/login",
        json={"email": "stale_token@example.com", "password": "NewPassword456!"},
    )
    assert resp_login.status_code == 200
    new_headers = {"Authorization": f"Bearer {resp_login.json()['access_token']}"}
    assert client.get("/users/me", headers=new_headers).status_code == 200


def test_email_normalization_on_register_and_login(setup_db):
    """Emails are stored lowercase; login is case-insensitive on the local part."""
    resp = client.post(
        "/users/register",
        json={
            "username": "case_user",
            "email": "Case.User@Example.COM",
            "password": "ValidPassword123!",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "case.user@example.com"

    # Login with different casing still finds the account.
    resp_login = client.post(
        "/users/login",
        json={"email": "CASE.USER@example.com", "password": "ValidPassword123!"},
    )
    assert resp_login.status_code == 200

    # Registering the same email in another casing is a duplicate.
    resp_dup = client.post(
        "/users/register",
        json={
            "username": "case_user2",
            "email": "case.user@example.com",
            "password": "ValidPassword123!",
        },
    )
    assert resp_dup.status_code == 409


def test_role_change_invalidates_previously_issued_tokens(setup_db):
    """Tokens issued under an old role must not keep the old privileges."""
    db = setup_db
    user = User(
        username="demoted_user",
        email="demoted@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    user_token = create_access_token(user_id=user.id)
    user_headers = {"Authorization": f"Bearer {user_token}"}
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Works before the role change.
    assert client.get("/users/me", headers=user_headers).status_code == 200

    resp = client.put(
        f"/users/{user.id}", json={"role": "guest"}, headers=admin_headers
    )
    assert resp.status_code == 200

    # Old token is rejected instead of silently downgrading.
    resp_old = client.get("/users/me", headers=user_headers)
    assert resp_old.status_code == 401


def test_user_me_student_endpoints_for_guest_and_user(setup_db):
    db = setup_db
    # 1. Guest access to /users/me/student -> 403
    guest = User(
        username="guest_me",
        email="guest_me@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.GUEST,
    )
    db.add(guest)
    db.commit()
    guest_token = create_access_token(user_id=guest.id)
    resp_guest = client.get(
        "/users/me/student", headers={"Authorization": f"Bearer {guest_token}"}
    )
    assert resp_guest.status_code == 403
    assert resp_guest.json()["detail"] == "forbidden"

    # 2. User with no linked student -> 404
    user_no_student = User(
        username="user_no_student",
        email="user_no_student@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user_no_student)
    db.commit()
    user_token = create_access_token(user_id=user_no_student.id)
    resp_no_student = client.get(
        "/users/me/student", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp_no_student.status_code == 404
    assert resp_no_student.json()["detail"] == "Student record not found"


def test_user_admin_management_and_cannot_remove_last_admin(setup_db):
    db = setup_db
    # Admin is user_id=1 from setup_db
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Admin creates secondary user
    second_user = User(
        username="second_user",
        email="second_user@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(second_user)
    db.commit()
    db.refresh(second_user)
    second_user_id = second_user.id

    # 2. Admin reads users list -> 200
    resp_list = client.get("/users/", headers=admin_headers)
    assert resp_list.status_code == 200
    assert len(resp_list.json()) >= 2

    # 3. Admin reads single user -> 200
    resp_single = client.get(f"/users/{second_user_id}", headers=admin_headers)
    assert resp_single.status_code == 200
    assert resp_single.json()["email"] == "second_user@example.com"

    # 4. Admin updates secondary user -> 200
    resp_update = client.put(
        f"/users/{second_user_id}",
        json={"username": "second_user_mod"},
        headers=admin_headers,
    )
    assert resp_update.status_code == 200
    assert resp_update.json()["username"] == "second_user_mod"

    # 5. Cannot remove or demote the ONLY admin account -> 400
    resp_demote_last_admin = client.put(
        "/users/1", json={"role": "user"}, headers=admin_headers
    )
    assert resp_demote_last_admin.status_code == 400
    assert (
        resp_demote_last_admin.json()["detail"]
        == "Cannot remove the last admin account"
    )

    # 6. Cannot delete the ONLY admin account -> 400
    resp_delete_last_admin = client.delete("/users/1", headers=admin_headers)
    assert resp_delete_last_admin.status_code == 400
    assert (
        resp_delete_last_admin.json()["detail"]
        == "Cannot remove the last admin account"
    )

    # 7. Admin deletes secondary user -> 200
    resp_del_second = client.delete(f"/users/{second_user_id}", headers=admin_headers)
    assert resp_del_second.status_code == 200
    assert resp_del_second.json() == {"message": "User deleted successfully"}

    db.expire_all()
    assert db.get(User, second_user_id) is None


# ============================================================================
# Student API Tests
# ============================================================================


def create_student_test_setup(db):
    from app.models.college import College
    from app.models.department import Department

    college = College(name="Student Test College", code="STU_COL")
    db.add(college)
    db.commit()
    db.refresh(college)

    dept = Department(name="Student Test Dept", code="STU_DEP", college_id=college.id)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return {"college": college, "department": dept}


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/students/", None),
        ("get", "/students/1", None),
        (
            "post",
            "/students/",
            {
                "name": "Student A",
                "email": "stua@test.com",
                "age": 20,
                "department_id": 1,
            },
        ),
        ("put", "/students/1", {"age": 21}),
        ("delete", "/students/1", None),
        ("post", "/students/1/link-user/1", None),
    ],
)
def test_student_endpoints_require_authentication(setup_db, method, path, payload):
    request_fn = getattr(client, method)
    resp = request_fn(path, json=payload) if payload else request_fn(path)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "not authenticated"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "post",
            "/students/",
            {
                "name": "Student B",
                "email": "stub@test.com",
                "age": 20,
                "department_id": 1,
            },
        ),
        ("put", "/students/1", {"age": 21}),
        ("delete", "/students/1", None),
        ("post", "/students/1/link-user/1", None),
    ],
)
def test_student_admin_endpoints_forbidden_for_user(setup_db, method, path, payload):
    db = setup_db
    user = User(
        username="student_regular_user",
        email="student_reg_user@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    user_token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {user_token}"}

    request_fn = getattr(client, method)
    resp = (
        request_fn(path, json=payload, headers=headers)
        if payload
        else request_fn(path, headers=headers)
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "forbidden"


def test_student_admin_creates_student_and_validates_email_duplicate(setup_db):
    db = setup_db
    data = create_student_test_setup(db)
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Successful creation -> 201
    payload = {
        "name": "Grace Hopper",
        "email": "grace.hopper@example.com",
        "age": 22,
        "department_id": data["department"].id,
    }
    resp = client.post("/students/", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    student_id = resp.json()["id"]

    from app.models.student import Student

    db.expire_all()
    db_student = db.get(Student, student_id)
    assert db_student is not None
    assert db_student.email == "grace.hopper@example.com"

    # 2. Duplicate email -> 409
    resp_dup = client.post("/students/", json=payload, headers=admin_headers)
    assert resp_dup.status_code == 409
    assert resp_dup.json()["detail"] == "Student email or constraint already exists"


def test_student_get_scoping_for_user_and_admin(setup_db):
    """
    USER role should only see their own linked student.
    ADMIN role can see all students.
    GUEST role is forbidden (403).
    """
    db = setup_db
    data = create_student_test_setup(db)
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Create 2 users and 2 students
    user1 = User(
        username="stu_u1",
        email="stu_u1@test.com",
        password_hash=hash_password("pw"),
        role=UserRole.USER,
    )
    user2 = User(
        username="stu_u2",
        email="stu_u2@test.com",
        password_hash=hash_password("pw"),
        role=UserRole.USER,
    )
    guest = User(
        username="stu_guest",
        email="stu_guest@test.com",
        password_hash=hash_password("pw"),
        role=UserRole.GUEST,
    )
    db.add_all([user1, user2, guest])
    db.commit()

    from app.models.student import Student

    s1 = Student(
        name="Student One",
        email="s1@test.com",
        age=20,
        department_id=data["department"].id,
        user_id=user1.id,
    )
    s2 = Student(
        name="Student Two",
        email="s2@test.com",
        age=21,
        department_id=data["department"].id,
        user_id=user2.id,
    )
    db.add_all([s1, s2])
    db.commit()
    db.refresh(s1)
    db.refresh(s2)

    u1_token = create_access_token(user_id=user1.id)
    u1_headers = {"Authorization": f"Bearer {u1_token}"}

    guest_token = create_access_token(user_id=guest.id)
    guest_headers = {"Authorization": f"Bearer {guest_token}"}

    # 1. Guest -> 403
    assert client.get(f"/students/{s1.id}", headers=guest_headers).status_code == 403
    assert client.get("/students/", headers=guest_headers).status_code == 403

    # 2. User1 gets own student (s1) -> 200
    resp_own = client.get(f"/students/{s1.id}", headers=u1_headers)
    assert resp_own.status_code == 200
    assert resp_own.json()["id"] == s1.id

    # 3. User1 gets other student (s2) -> 404 (Scoping enforcement)
    resp_other = client.get(f"/students/{s2.id}", headers=u1_headers)
    assert resp_other.status_code == 404
    assert resp_other.json()["detail"] == "Student not found"

    # 4. User1 list contains only own student
    resp_list_u1 = client.get("/students/", headers=u1_headers)
    assert resp_list_u1.status_code == 200
    retrieved_u1 = [s["id"] for s in resp_list_u1.json()]
    assert retrieved_u1 == [s1.id]

    # 5. Admin list contains both students
    resp_list_admin = client.get("/students/", headers=admin_headers)
    assert resp_list_admin.status_code == 200
    retrieved_admin = {s["id"] for s in resp_list_admin.json()}
    assert s1.id in retrieved_admin
    assert s2.id in retrieved_admin


def test_student_admin_link_user_endpoints_and_conflicts(setup_db):
    db = setup_db
    data = create_student_test_setup(db)
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.student import Student

    student = Student(
        name="Unlinked Student",
        email="unlinked@test.com",
        age=20,
        department_id=data["department"].id,
    )
    user = User(
        username="unlinked_user",
        email="unlinked_user@test.com",
        password_hash=hash_password("pw"),
        role=UserRole.USER,
    )
    db.add_all([student, user])
    db.commit()
    db.refresh(student)
    db.refresh(user)

    # 1. Successful linking -> 200
    resp_link = client.post(
        f"/students/{student.id}/link-user/{user.id}", headers=admin_headers
    )
    assert resp_link.status_code == 200
    assert resp_link.json()["user_id"] == user.id

    db.expire_all()
    assert db.get(Student, student.id).user_id == user.id

    # 2. Already linked student -> 409
    user_b = User(
        username="user_b",
        email="user_b@test.com",
        password_hash=hash_password("pw"),
        role=UserRole.USER,
    )
    db.add(user_b)
    db.commit()
    db.refresh(user_b)

    resp_already_linked = client.post(
        f"/students/{student.id}/link-user/{user_b.id}", headers=admin_headers
    )
    assert resp_already_linked.status_code == 409
    assert resp_already_linked.json()["detail"] == "student already linked to user"

    # 3. Non-existent student / user -> 404
    assert (
        client.post(
            f"/students/999999/link-user/{user_b.id}", headers=admin_headers
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/students/{student.id}/link-user/999999", headers=admin_headers
        ).status_code
        == 404
    )


def test_student_admin_updates_and_deletes_student(setup_db):
    db = setup_db
    data = create_student_test_setup(db)
    admin_token = create_access_token(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    from app.models.student import Student

    student = Student(
        name="Student To Delete",
        email="st_del@test.com",
        age=20,
        department_id=data["department"].id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    student_id = student.id

    # Update -> 200
    resp_up = client.put(
        f"/students/{student_id}",
        json={"name": "Student Renamed", "age": 25},
        headers=admin_headers,
    )
    assert resp_up.status_code == 200
    assert resp_up.json()["name"] == "Student Renamed"
    assert resp_up.json()["age"] == 25

    db.expire_all()
    assert db.get(Student, student_id).name == "Student Renamed"

    # Delete -> 200
    resp_del = client.delete(f"/students/{student_id}", headers=admin_headers)
    assert resp_del.status_code == 200
    assert resp_del.json() == {"message": "Student deleted successfully"}

    db.expire_all()
    assert db.get(Student, student_id) is None
