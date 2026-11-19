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


class SubmitIn(BaseModel):
    problem_id: int
    language: LanguageKey
    source_code: str = Field(min_length=1)


class SubmissionOut(ORM):
    id: int
    user_id: int
    kind: str
    problem_id: int | None
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
