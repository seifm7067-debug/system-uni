from app.schemas.college import CollegeCreate, CollegeResponseSchema, CollegeUpdate
from app.schemas.course import CourseCreate, CourseResponseSchema, CourseUpdate
from app.schemas.courseoffering import (
    CourseOfferingCreate,
    CourseOfferingResponseSchema,
    CourseOfferingUpdate,
)
from app.schemas.courseschedule import (
    CourseScheduleCreate,
    CourseScheduleResponseSchema,
    CourseScheduleUpdate,
)
from app.schemas.department import (
    DepartmentCreate,
    DepartmentResponseSchema,
    DepartmentUpdate,
)
from app.schemas.enrollment import (
    EnrollmentCreate,
    EnrollmentResponseSchema,
    EnrollmentUpdate,
)
from app.schemas.student import StudentCreate, StudentResponseSchema, StudentUpdate
from app.schemas.teacher import TeacherCreate, TeacherResponseSchema, TeacherUpdate
from app.schemas.tokenresponse import TokenResponse
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserRegister,
    UserResponse,
    UserSelfUpdate,
    UserUpdate,
)

__all__ = [
    "CollegeCreate",
    "CollegeResponseSchema",
    "CollegeUpdate",
    "CourseCreate",
    "CourseOfferingCreate",
    "CourseOfferingResponseSchema",
    "CourseOfferingUpdate",
    "CourseResponseSchema",
    "CourseScheduleCreate",
    "CourseScheduleResponseSchema",
    "CourseScheduleUpdate",
    "CourseUpdate",
    "DepartmentCreate",
    "DepartmentResponseSchema",
    "DepartmentUpdate",
    "EnrollmentCreate",
    "EnrollmentResponseSchema",
    "EnrollmentUpdate",
    "StudentCreate",
    "StudentResponseSchema",
    "StudentUpdate",
    "TeacherCreate",
    "TeacherResponseSchema",
    "TeacherUpdate",
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserRegister",
    "UserResponse",
    "UserSelfUpdate",
    "UserUpdate",
]
