import pytest
from app.database import Base
from app.models.college import College
from app.models.course import Course
from app.models.courseoffering import CourseOffering
from app.models.department import Department
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.teacher import Teacher
from app.services.reports import calculate_gpa, generate_student_transcript
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
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


# ============================================================================
# calculate_gpa Unit Tests
# ============================================================================


def test_calculate_gpa_empty_list_returns_zero():
    assert calculate_gpa([]) == 0.0


@pytest.mark.parametrize(
    "grade,expected_gpa",
    [
        (100, 4.0),
        (95, 4.0),
        (90, 4.0),
        (89, 3.7),
        (85, 3.7),
        (84, 3.3),
        (80, 3.3),
        (79, 3.0),
        (75, 3.0),
        (74, 2.7),
        (70, 2.7),
        (69, 2.3),
        (65, 2.3),
        (64, 2.0),
        (60, 2.0),
        (59, 0.0),
        (50, 0.0),
        (0, 0.0),
    ],
)
def test_calculate_gpa_individual_grade_thresholds(grade, expected_gpa):
    assert calculate_gpa([grade]) == expected_gpa


def test_calculate_gpa_multiple_grades_calculation_and_rounding():
    # 90 (4.0), 85 (3.7), 80 (3.3) -> sum=11.0 / 3 = 3.6666... -> round(2)=3.67
    assert calculate_gpa([90, 85, 80]) == 3.67

    # 100 (4.0), 50 (0.0) -> sum=4.0 / 2 = 2.0
    assert calculate_gpa([100, 50]) == 2.0

    # 70 (2.7), 75 (3.0) -> sum=5.7 / 2 = 2.85
    assert calculate_gpa([70, 75]) == 2.85

    # 95 (4.0), 88 (3.7), 76 (3.0), 68 (2.3), 59 (0.0) -> sum=13.0 / 5 = 2.6
    assert calculate_gpa([95, 88, 76, 68, 59]) == 2.6


def test_calculate_gpa_all_failing_grades():
    assert calculate_gpa([59, 45, 30, 0]) == 0.0


# ============================================================================
# generate_student_transcript Integration Tests (Real DB)
# ============================================================================


def create_base_entities(db):
    college = College(name="Engineering College", code="ENG_REP")
    db.add(college)
    db.commit()
    db.refresh(college)

    dept = Department(name="Software Engineering", code="SE_REP", college_id=college.id)
    db.add(dept)
    db.commit()
    db.refresh(dept)

    teacher = Teacher(name="Dr. Alan", department_id=dept.id)
    db.add(teacher)
    db.commit()
    db.refresh(teacher)

    c1 = Course(name="Algorithms", code="CS201", department_id=dept.id)
    c2 = Course(name="Databases", code="CS202", department_id=dept.id)
    c3 = Course(name="Networks", code="CS203", department_id=dept.id)
    db.add_all([c1, c2, c3])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)
    db.refresh(c3)

    off1 = CourseOffering(
        course_id=c1.id,
        teacher_id=teacher.id,
        semester="Fall",
        academic_year=2026,
        section="A",
    )
    off2 = CourseOffering(
        course_id=c2.id,
        teacher_id=teacher.id,
        semester="Fall",
        academic_year=2026,
        section="A",
    )
    off3 = CourseOffering(
        course_id=c3.id,
        teacher_id=teacher.id,
        semester="Fall",
        academic_year=2026,
        section="A",
    )
    db.add_all([off1, off2, off3])
    db.commit()
    db.refresh(off1)
    db.refresh(off2)
    db.refresh(off3)

    return {
        "college": college,
        "department": dept,
        "teacher": teacher,
        "courses": [c1, c2, c3],
        "offerings": [off1, off2, off3],
    }


def test_generate_student_transcript_nonexistent_student_returns_none(db_session):
    result = generate_student_transcript(db_session, 999999)
    assert result is None


def test_generate_student_transcript_student_with_zero_enrollments(db_session):
    data = create_base_entities(db_session)
    student = Student(
        name="Alice Smith",
        email="alice.report@test.com",
        age=20,
        department_id=data["department"].id,
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    transcript = generate_student_transcript(db_session, student.id)
    assert transcript is not None
    assert transcript["student_id"] == student.id
    assert transcript["name"] == "Alice Smith"
    assert transcript["email"] == "alice.report@test.com"
    assert transcript["department_id"] == data["department"].id
    assert transcript["gpa"] == 0.0
    assert transcript["total_courses"] == 0
    assert transcript["courses"] == []


def test_generate_student_transcript_student_with_multiple_graded_enrollments(
    db_session,
):
    data = create_base_entities(db_session)
    student = Student(
        name="Bob Jones",
        email="bob.report@test.com",
        age=21,
        department_id=data["department"].id,
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    # 3 Enrollments:
    # 1. Algorithms: grade 92 (4.0)
    # 2. Databases: grade 86 (3.7)
    # 3. Networks: grade 74 (2.7)
    # Expected GPA: (4.0 + 3.7 + 2.7) / 3 = 10.4 / 3 = 3.4666... -> 3.47
    e1 = Enrollment(
        student_id=student.id,
        course_offering_id=data["offerings"][0].id,
        enrollment_code="ENR-BOB-01",
        grade=92,
        is_active=True,
        is_withdrawn=False,
    )
    e2 = Enrollment(
        student_id=student.id,
        course_offering_id=data["offerings"][1].id,
        enrollment_code="ENR-BOB-02",
        grade=86,
        is_active=True,
        is_withdrawn=False,
    )
    e3 = Enrollment(
        student_id=student.id,
        course_offering_id=data["offerings"][2].id,
        enrollment_code="ENR-BOB-03",
        grade=74,
        is_active=True,
        is_withdrawn=False,
    )
    db_session.add_all([e1, e2, e3])
    db_session.commit()

    transcript = generate_student_transcript(db_session, student.id)
    assert transcript is not None
    assert transcript["student_id"] == student.id
    assert transcript["name"] == "Bob Jones"
    assert transcript["email"] == "bob.report@test.com"
    assert transcript["department_id"] == data["department"].id
    assert transcript["gpa"] == 3.47
    assert transcript["total_courses"] == 3
    assert len(transcript["courses"]) == 3

    # Check course records structure
    codes = {c["enrollment_code"] for c in transcript["courses"]}
    assert codes == {"ENR-BOB-01", "ENR-BOB-02", "ENR-BOB-03"}

    c1_rec = next(
        c for c in transcript["courses"] if c["enrollment_code"] == "ENR-BOB-01"
    )
    assert c1_rec["course_offering_id"] == data["offerings"][0].id
    assert c1_rec["grade"] == 92
    assert c1_rec["is_active"] is True
    assert c1_rec["is_withdrawn"] is False


def test_generate_student_transcript_handles_none_grades_and_status_flags(db_session):
    """
    If a course has grade=None (e.g. in progress), it should be included in total_courses
    and courses list, but excluded from GPA calculation.
    """
    data = create_base_entities(db_session)
    student = Student(
        name="Charlie Brown",
        email="charlie.report@test.com",
        age=22,
        department_id=data["department"].id,
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    # 1. Graded course (grade=90 -> 4.0)
    e1 = Enrollment(
        student_id=student.id,
        course_offering_id=data["offerings"][0].id,
        enrollment_code="ENR-CH-01",
        grade=90,
        is_active=True,
        is_withdrawn=False,
    )
    # 2. In progress course (grade=None)
    e2 = Enrollment(
        student_id=student.id,
        course_offering_id=data["offerings"][1].id,
        enrollment_code="ENR-CH-02",
        grade=None,
        is_active=True,
        is_withdrawn=False,
    )
    # 3. Withdrawn course (grade=None, is_withdrawn=True, is_active=False)
    e3 = Enrollment(
        student_id=student.id,
        course_offering_id=data["offerings"][2].id,
        enrollment_code="ENR-CH-03",
        grade=None,
        is_active=False,
        is_withdrawn=True,
    )
    db_session.add_all([e1, e2, e3])
    db_session.commit()

    transcript = generate_student_transcript(db_session, student.id)
    assert transcript is not None
    assert transcript["total_courses"] == 3
    # GPA should only be calculated from the 1 valid grade (90 -> 4.0)
    assert transcript["gpa"] == 4.0
    assert len(transcript["courses"]) == 3

    none_grade_courses = [c for c in transcript["courses"] if c["grade"] is None]
    assert len(none_grade_courses) == 2


def test_generate_student_transcript_enrollment_isolation_between_students(db_session):
    data = create_base_entities(db_session)
    s1 = Student(
        name="Student One",
        email="s1.iso@test.com",
        age=20,
        department_id=data["department"].id,
    )
    s2 = Student(
        name="Student Two",
        email="s2.iso@test.com",
        age=21,
        department_id=data["department"].id,
    )
    db_session.add_all([s1, s2])
    db_session.commit()
    db_session.refresh(s1)
    db_session.refresh(s2)

    e1 = Enrollment(
        student_id=s1.id,
        course_offering_id=data["offerings"][0].id,
        enrollment_code="S1-ENR",
        grade=95,
    )
    e2 = Enrollment(
        student_id=s2.id,
        course_offering_id=data["offerings"][1].id,
        enrollment_code="S2-ENR",
        grade=60,
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    t1 = generate_student_transcript(db_session, s1.id)
    assert t1["student_id"] == s1.id
    assert t1["total_courses"] == 1
    assert t1["gpa"] == 4.0
    assert t1["courses"][0]["enrollment_code"] == "S1-ENR"

    t2 = generate_student_transcript(db_session, s2.id)
    assert t2["student_id"] == s2.id
    assert t2["total_courses"] == 1
    assert t2["gpa"] == 2.0
    assert t2["courses"][0]["enrollment_code"] == "S2-ENR"
