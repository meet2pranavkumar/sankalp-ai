# Import every model here so Alembic can see them.
from app.models.assessment import (  # noqa: F401
    Assessment, AssessmentAttempt, AssessmentDraft, AssessmentProblem, AssessmentResult,
)
from app.models.batch import Batch, BatchMember  # noqa: F401
from app.models.college import College  # noqa: F401
from app.models.course import Course, Lesson, LessonProgress, Unit  # noqa: F401
from app.models.problem import Problem, TestCase  # noqa: F401
from app.models.submission import Submission  # noqa: F401
from app.models.user import Role, User  # noqa: F401
