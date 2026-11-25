from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- colleges ----------
class CollegeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    code: str = Field(min_length=2, max_length=30)

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: str) -> str:
        return v.strip().upper()


class CollegeOut(ORM):
    id: int
    name: str
    city: str | None
    state: str | None
    code: str


# ---------- users ----------
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: Role
    college_id: int | None = None  # only used by super_admin
    batch_id: int | None = None  # optional: add a new student to a batch

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class BulkStudent(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class BulkStudentsCreate(BaseModel):
    students: list[BulkStudent] = Field(min_length=1, max_length=200)
    batch_id: int | None = None
    college_id: int | None = None  # only used by super_admin


class BulkStudentResult(BaseModel):
    name: str
    email: str
    temp_password: str | None = None
    error: str | None = None


class UserOut(ORM):
    id: int
    name: str
    email: str
    role: Role
    college_id: int | None
    college_name: str | None
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)


class PasswordResetOut(BaseModel):
    temp_password: str


# ---------- auth ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- batches ----------
class BatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    year: int | None = Field(default=None, ge=2000, le=2100)
    branch: str | None = Field(default=None, max_length=60)


class BatchOut(ORM):
    id: int
    college_id: int
    created_by: int
    name: str
    year: int | None
    branch: str | None


class MembersAdd(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=500)


# ---------- problems ----------
Difficulty = Literal["easy", "medium", "hard"]
LanguageKey = Literal["c", "cpp", "java", "python"]


class TestCaseIn(BaseModel):
    __test__ = False
    input: str = Field(default="", max_length=100_000)
    expected_output: str = Field(max_length=100_000)
    is_hidden: bool = False
    weight: int = Field(default=1, ge=1, le=100)


class TestCaseOut(ORM):
    __test__ = False
    position: int
    input: str
    expected_output: str
    is_hidden: bool
    weight: int


class ProblemIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    statement_md: str = Field(min_length=1, max_length=20_000)
    difficulty: Difficulty = "easy"
    tags: list[str] = Field(default_factory=list, max_length=10)
    time_limit_ms: int = Field(default=1000, ge=100, le=10_000)
    memory_limit_mb: int = Field(default=256, ge=16, le=512)
    is_public: bool = False
    test_cases: list[TestCaseIn] = Field(min_length=1, max_length=50)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, tags: list[str]) -> list[str]:
        cleaned = []
        for tag in tags:
            tag = tag.strip().lower()
            if not tag or len(tag) > 30:
                raise ValueError("Each tag must be 1 to 30 characters.")
            if tag not in cleaned:
                cleaned.append(tag)
        return cleaned

    @field_validator("test_cases")
    @classmethod
    def need_a_sample(cls, tests: list[TestCaseIn]) -> list[TestCaseIn]:
        if all(t.is_hidden for t in tests):
            raise ValueError("Add at least one sample test case that students can see.")
        return tests


class ProblemSummary(ORM):
    id: int
    title: str
    difficulty: str
    tags: list[str]
    is_public: bool
    solved: bool = False


class ProblemOut(ORM):
    id: int
    college_id: int | None
    created_by: int
    title: str
    statement_md: str
    difficulty: str
    tags: list[str]
    time_limit_ms: int
    memory_limit_mb: int
    is_public: bool
    can_edit: bool
    test_cases: list[TestCaseOut]  # students get sample tests only


# ---------- running and submitting code ----------
class LanguageOut(BaseModel):
    key: str
    label: str


class RunIn(BaseModel):
    language: LanguageKey
    source_code: str = Field(min_length=1)
    stdin: str = Field(default="", max_length=100_000)
    problem_id: int | None = None  # optional: use this problem's time and memory limits
    assessment_id: int | None = None  # set when running code inside an assignment or exam


class SubmitIn(BaseModel):
    problem_id: int
    language: LanguageKey
    source_code: str = Field(min_length=1)
    assessment_id: int | None = None  # set when the answer counts for an assignment or exam


class SubmissionOut(ORM):
    id: int
    user_id: int
    kind: str
    problem_id: int | None
    assessment_id: int | None = None
    hidden: bool = False  # True: this is an exam answer and results are not published yet
    language: str
    source_code: str
    status: str
    verdict: str | None
    passed_count: int | None
    total_count: int | None
    runtime_ms: int | None
    memory_kb: int | None
    stdout: str | None
    stderr: str | None
    compile_output: str | None
    message: str | None
    results: list[dict] | None
    created_at: datetime
    finished_at: datetime | None


class SubmissionBrief(ORM):
    id: int
    language: str
    status: str
    verdict: str | None
    passed_count: int | None
    total_count: int | None
    runtime_ms: int | None
    created_at: datetime
    hidden: bool = False


# ---------- courses ----------
class CourseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    language: LanguageKey = "c"


class CoursePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    language: LanguageKey | None = None
    is_published: bool | None = None


class CourseSummary(BaseModel):
    id: int
    title: str
    description: str
    language: str
    is_published: bool
    is_shared: bool  # made by the platform owner, read-only for colleges (duplicate it to change it)
    can_edit: bool
    total_lessons: int
    completed_lessons: int


class LessonBrief(BaseModel):
    id: int
    title: str
    position: int
    completed: bool


class UnitOut(BaseModel):
    id: int
    title: str
    position: int
    lessons: list[LessonBrief]


class CourseOut(CourseSummary):
    units: list[UnitOut]


class UnitIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class LessonIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content_md: str = Field(default="", max_length=50_000)
    video_url: str | None = Field(default=None, max_length=500)

    @field_validator("video_url")
    @classmethod
    def only_web_links(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("The video link must start with http:// or https://")
        return value


class LessonPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content_md: str | None = Field(default=None, max_length=50_000)
    video_url: str | None = Field(default=None, max_length=500)

    @field_validator("video_url")
    @classmethod
    def only_web_links(cls, value: str | None) -> str | None:
        return LessonIn.only_web_links(value)


class LessonOut(BaseModel):
    id: int
    unit_id: int
    unit_title: str
    course_id: int
    course_title: str
    title: str
    content_md: str
    video_url: str | None
    position: int
    completed: bool
    can_edit: bool
    prev_lesson_id: int | None
    next_lesson_id: int | None


class OrderIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


# ---------- assessments (assignments and exams) ----------
AssessmentType = Literal["assignment", "exam"]


class AssessmentProblemIn(BaseModel):
    problem_id: int
    marks: float = Field(gt=0, le=1000)


def _need_time_zone(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("Send the time with a time zone, for example 2026-12-01T09:00:00+05:30 or ...Z")
    return moment


class AssessmentIn(BaseModel):
    batch_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    type: AssessmentType
    starts_at: datetime
    ends_at: datetime
    duration_min: int | None = Field(default=None, ge=5, le=600)
    ai_hints_allowed: bool = True  # assignments only. The AI helper is always off in an exam.
    problems: list[AssessmentProblemIn] = Field(min_length=1, max_length=30)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def has_time_zone(cls, moment: datetime) -> datetime:
        return _need_time_zone(moment)

    @field_validator("problems")
    @classmethod
    def no_repeated_problems(cls, items: list[AssessmentProblemIn]) -> list[AssessmentProblemIn]:
        ids = [p.problem_id for p in items]
        if len(ids) != len(set(ids)):
            raise ValueError("A problem can be used only once in an assessment.")
        return items


class AssessmentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    duration_min: int | None = Field(default=None, ge=5, le=600)
    is_published: bool | None = None
    results_published: bool | None = None
    ai_hints_allowed: bool | None = None
    problems: list[AssessmentProblemIn] | None = Field(default=None, min_length=1, max_length=30)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def has_time_zone(cls, moment: datetime | None) -> datetime | None:
        return None if moment is None else _need_time_zone(moment)

    @field_validator("problems")
    @classmethod
    def no_repeated_problems(cls, items):
        return None if items is None else AssessmentIn.no_repeated_problems(items)


class ProblemScoreOut(BaseModel):
    problem_id: int
    marks: float  # earned
    possible: float
    passed: int
    total: int
    attempted: bool


class AssessmentProblemOut(BaseModel):
    problem_id: int
    title: str
    difficulty: str
    marks: float
    position: int
    score: ProblemScoreOut | None = None  # the student's own best result, when they may see it


class AttemptOut(BaseModel):
    started_at: datetime
    deadline_at: datetime
    finished_at: datetime | None


class AssessmentSummary(BaseModel):
    id: int
    title: str
    type: str
    batch_id: int
    batch_name: str
    starts_at: datetime
    ends_at: datetime
    duration_min: int | None
    is_published: bool
    results_published: bool
    total_marks: float
    problem_count: int
    status: str | None  # what it means for this student; None for teachers
    my_marks: float | None  # a student sees this only when allowed
    can_manage: bool


class AssessmentOut(AssessmentSummary):
    description: str
    ai_hints_allowed: bool
    server_now: datetime  # so the browser can show a countdown that matches the server's clock
    attempt: AttemptOut | None
    problems: list[AssessmentProblemOut] | None  # None = not visible yet
    has_activity: bool  # someone already started or submitted, so problems can no longer change


class DraftIn(BaseModel):
    language: LanguageKey
    source_code: str = Field(max_length=70_000)


class DraftOut(BaseModel):
    language: str
    source_code: str
    updated_at: datetime


class ResultRow(BaseModel):
    user_id: int
    name: str
    email: str
    status: str  # not_started, in_progress, finished (exam) or submitted / no_submission (assignment)
    tab_switches: int
    per_problem: list[ProblemScoreOut]
    auto_marks: float
    override_marks: float | None
    final_marks: float
    comment: str | None
    pending: int  # answers still being judged
    judge_errors: int  # answers the judge could not check, see "Judge again"


class ResultsOut(BaseModel):
    assessment_id: int
    title: str
    type: str
    results_published: bool
    total_marks: float
    problems: list[AssessmentProblemOut]
    rows: list[ResultRow]
    pending_total: int
    judge_errors_total: int


class OverrideIn(BaseModel):
    override_marks: float | None = Field(default=None, ge=0, le=100_000)
    comment: str | None = Field(default=None, max_length=1000)


class MyResultOut(BaseModel):
    visible: bool  # False = the teacher has not published results yet
    total_marks: float
    auto_marks: float | None
    final_marks: float | None
    comment: str | None
    per_problem: list[ProblemScoreOut]
    pending: int


# ---------- AI helper ----------
class HintIn(BaseModel):
    problem_id: int
    level: int = Field(ge=1, le=3)
    language: LanguageKey
    source_code: str = Field(default="", max_length=70_000)


class ExplainIn(BaseModel):
    problem_id: int
    language: LanguageKey
    source_code: str = Field(default="", max_length=70_000)
    error_text: str = Field(min_length=1, max_length=20_000)  # long compiler output is cut short on the server


class AIRecentOut(BaseModel):
    id: int
    kind: str
    level: int | None
    text: str
    created_at: datetime


class AIUsageOut(BaseModel):
    enabled: bool  # False: the student cannot ask right now. See blocked_reason.
    blocked_reason: str | None
    hints_used: int
    hints_limit: int
    explains_used: int
    explains_limit: int
    available_levels: list[int]  # level 2 opens after level 1 has been read, and so on
    retry_after_seconds: int  # the wait before the next hint for this problem
    recent: list[AIRecentOut]  # the answers from the last 24 hours, so a refresh loses nothing


class AIAnswerOut(BaseModel):
    id: int
    kind: str
    level: int | None
    text: str
    usage: AIUsageOut


class AIInsightRow(BaseModel):
    problem_id: int
    title: str
    students: int
    requests: int
    hints: int
    explains: int
    level3: int
    flagged: int  # times the AI tried to give a solution and the safety check stopped it
    errors: int
    last_at: datetime


class AIRequestRow(BaseModel):
    id: int
    student_name: str
    student_email: str
    kind: str
    level: int | None
    status: str
    flagged: bool
    text: str
    created_at: datetime


# ---------- reports ----------
class CourseProgressOut(BaseModel):
    course_id: int
    title: str
    completed_lessons: int
    total_lessons: int
    percent: float


class SolvedByLevel(BaseModel):
    difficulty: str
    solved: int
    total: int  # problems of this level the student can practise


class DayActivity(BaseModel):
    date: str  # YYYY-MM-DD in the college's time zone
    submissions: int  # runs and submits
    accepted: int
    lessons: int


class RecentSubmissionOut(BaseModel):
    id: int
    problem_id: int | None
    title: str
    language: str
    verdict: str | None
    passed_count: int | None
    total_count: int | None
    created_at: datetime
    hidden: bool = False  # an exam answer whose result is not published yet


class StudentReportOut(BaseModel):
    student_id: int
    name: str
    email: str
    courses: list[CourseProgressOut]
    problems: list[SolvedByLevel]
    streak_days: int
    active_days_30: int
    total_submissions: int  # all the "Submit" presses
    accepted_submissions: int
    last_active_at: datetime | None
    activity: list[DayActivity]  # the last 30 days, oldest first
    recent: list[RecentSubmissionOut]
    ai_requests_30d: int | None  # teachers see this, students do not need it


class BatchSummaryOut(BaseModel):
    batch_id: int
    name: str
    year: int | None
    branch: str | None
    student_count: int
    total_lessons: int  # lessons in the courses the batch can see
    avg_completion_percent: float
    avg_problems_solved: float
    inactive_count: int
    last_active_at: datetime | None


class StudentRowOut(BaseModel):
    user_id: int
    name: str
    email: str
    lessons_completed: int
    lessons_total: int
    completion_percent: float
    problems_solved: int
    submissions_30d: int
    ai_requests_30d: int
    last_active_at: datetime | None
    days_inactive: int | None  # None = never active
    status: str  # active, inactive, never_active


class TopicOut(BaseModel):
    topic: str
    students: int
    pairs_attempted: int  # (student, problem) pairs that were tried
    pairs_solved: int
    solve_rate_percent: float
    wrong_submissions: int
    hint_requests: int


class WeakProblemOut(BaseModel):
    problem_id: int
    title: str
    difficulty: str
    students_attempted: int
    students_solved: int
    solve_rate_percent: float
    wrong_submissions: int
    hint_requests: int


class CourseAverageOut(BaseModel):
    course_id: int
    title: str
    total_lessons: int
    avg_percent: float


class AssessmentAverageOut(BaseModel):
    assessment_id: int
    title: str
    type: str
    results_published: bool
    students: int
    participants: int
    avg_percent: float | None  # None while nobody took part


class BatchReportOut(BaseModel):
    summary: BatchSummaryOut
    inactive_days: int
    students: list[StudentRowOut]
    weak_topics: list[TopicOut]
    weak_problems: list[WeakProblemOut]
    courses: list[CourseAverageOut]
    assessments: list[AssessmentAverageOut]
