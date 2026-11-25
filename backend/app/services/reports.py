"""Progress numbers for students, classes and colleges.

Definitions, so every number means one clear thing:
- ACTIVE: the student made a submission or a Run, finished a lesson, or started an exam.
- STREAK: how many days in a row (counting back from today, or from yesterday if today has nothing yet) had activity.
  Days are counted in the college's own time zone (REPORT_UTC_OFFSET_MINUTES, India by default).
- SOLVED: the student has at least one Accepted Submit for the problem.
- WEAK TOPIC: of all the (student, problem) pairs that were tried under a topic tag, the share that were never solved.
A student's OWN numbers never reveal an exam result before the teacher publishes it. Teachers see the real numbers.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.models import (
    AIRequest, Assessment, AssessmentAttempt, AssessmentResult, Batch, BatchMember, Course, LessonProgress,
    Problem, Role, Submission, User,
)
from app.schemas import (
    AssessmentAverageOut, BatchReportOut, BatchSummaryOut, CourseAverageOut, CourseProgressOut, DayActivity,
    RecentSubmissionOut, SolvedByLevel, StudentReportOut, StudentRowOut, TopicOut, WeakProblemOut,
)
from app.services.assessments import compute_sheets, locked_problem_ids, total_marks
from app.services.grading import ACCEPTED

DIFFICULTIES = ("easy", "medium", "hard")
GRAPH_DAYS = 30
WEAK_DAYS = 90
MIN_STUDENTS_FOR_WEAK_PROBLEM = 2  # one student failing is not a pattern
MIN_PAIRS_FOR_WEAK_TOPIC = 3
LIST_LIMIT = 10
WRONG = {"wrong_answer", "runtime_error", "time_limit", "compile_error"}  # internal_error is the judge's fault, not the student's


def _percent(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def local_date(moment: datetime) -> date:
    return (clock.aware(moment) + timedelta(minutes=get_settings().report_utc_offset_minutes)).date()


# ---------------------------------------------------------------- reading the data
@dataclass
class SubRow:
    id: int
    problem_id: int | None
    kind: str
    status: str
    verdict: str | None
    passed: int | None
    total: int | None
    assessment_id: int | None
    language: str
    created_at: datetime


@dataclass
class Raw:
    subs: dict[int, list[SubRow]] = field(default_factory=lambda: defaultdict(list))
    lessons: dict[int, list[tuple[int, datetime]]] = field(default_factory=lambda: defaultdict(list))
    attempts: dict[int, list[datetime]] = field(default_factory=lambda: defaultdict(list))


def gather(db: Session, user_ids: list[int]) -> Raw:
    ids = list(user_ids) or [0]
    raw = Raw()
    for row in db.execute(
        select(
            Submission.id, Submission.user_id, Submission.problem_id, Submission.kind, Submission.status,
            Submission.verdict, Submission.passed_count, Submission.total_count, Submission.assessment_id,
            Submission.language, Submission.created_at,
        ).where(Submission.user_id.in_(ids))  # (the source code is not loaded: it is not needed and can be large)
    ):
        raw.subs[row.user_id].append(SubRow(row.id, row.problem_id, row.kind, row.status, row.verdict, row.passed_count,
                                            row.total_count, row.assessment_id, row.language, row.created_at))
    for user_id, lesson_id, done_at in db.execute(
        select(LessonProgress.user_id, LessonProgress.lesson_id, LessonProgress.completed_at).where(LessonProgress.user_id.in_(ids))
    ):
        raw.lessons[user_id].append((lesson_id, done_at))
    for user_id, started in db.execute(
        select(AssessmentAttempt.user_id, AssessmentAttempt.started_at).where(AssessmentAttempt.user_id.in_(ids))
    ):
        raw.attempts[user_id].append(started)
    return raw


def visible_courses(db: Session, college_id: int | None) -> list[tuple[Course, set[int]]]:
    """Published courses a college can read, each with the ids of its lessons. Empty courses are left out."""
    query = select(Course).where(Course.is_published.is_(True)).order_by(Course.title)
    query = query.where(or_(Course.college_id.is_(None), Course.college_id == college_id))
    out = []
    for course in db.scalars(query).unique():
        lesson_ids = {lesson.id for unit in course.units for lesson in unit.lessons}
        if lesson_ids:
            out.append((course, lesson_ids))
    return out


def secret_exam_ids(db: Session) -> set[int]:
    """Exams whose results the teacher has not published. Students must not learn their results from the dashboard."""
    return set(db.scalars(select(Assessment.id).where(Assessment.type == "exam", Assessment.results_published.is_(False))))


def _activity_moments(raw: Raw, user_id: int) -> list[datetime]:
    return (
        [s.created_at for s in raw.subs.get(user_id, [])]
        + [done for _, done in raw.lessons.get(user_id, [])]
        + list(raw.attempts.get(user_id, []))
    )


def last_active(raw: Raw, user_id: int) -> datetime | None:
    moments = [clock.aware(m) for m in _activity_moments(raw, user_id)]
    return max(moments) if moments else None


def streak(days: set[date], today: date) -> int:
    """Days in a row with activity. Today with nothing yet does not break it: the day is not over."""
    cursor = today if today in days else today - timedelta(days=1)
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def solved_problem_ids(raw: Raw, user_id: int, hidden: set[int] | None = None) -> set[int]:
    hidden = hidden or set()
    return {
        s.problem_id for s in raw.subs.get(user_id, [])
        if s.kind == "submit" and s.verdict == ACCEPTED and s.problem_id and s.assessment_id not in hidden
    }


# ---------------------------------------------------------------- one student
def student_report(db: Session, student: User, now: datetime, hide_secret: bool, raw: Raw | None = None) -> StudentReportOut:
    raw = raw or gather(db, [student.id])
    hidden = secret_exam_ids(db) if hide_secret else set()
    today = local_date(now)

    # courses
    done_ids = {lesson_id for lesson_id, _ in raw.lessons.get(student.id, [])}
    courses = [
        CourseProgressOut(
            course_id=c.id, title=c.title, completed_lessons=len(done_ids & lessons), total_lessons=len(lessons),
            percent=_percent(len(done_ids & lessons), len(lessons)),
        )
        for c, lessons in visible_courses(db, student.college_id)
    ]

    # problems solved, by level
    locked = locked_problem_ids(db, now)
    pool = db.scalars(
        select(Problem).where(or_(Problem.is_public.is_(True), Problem.college_id == student.college_id))
    ).all()
    pool = [p for p in pool if p.id not in locked]
    solved = solved_problem_ids(raw, student.id, hidden)
    problems = [
        SolvedByLevel(difficulty=level, solved=sum(1 for p in pool if p.difficulty == level and p.id in solved),
                      total=sum(1 for p in pool if p.difficulty == level))
        for level in DIFFICULTIES
    ]

    # days and streak
    subs = raw.subs.get(student.id, [])
    activity_days = {local_date(m) for m in _activity_moments(raw, student.id)}
    window = [today - timedelta(days=n) for n in range(GRAPH_DAYS - 1, -1, -1)]
    per_day = {d: [0, 0, 0] for d in window}  # submissions, accepted, lessons
    for s in subs:
        d = local_date(s.created_at)
        if d in per_day:
            per_day[d][0] += 1
            if s.kind == "submit" and s.verdict == ACCEPTED and s.assessment_id not in hidden:
                per_day[d][1] += 1
    for _, done in raw.lessons.get(student.id, []):
        d = local_date(done)
        if d in per_day:
            per_day[d][2] += 1

    # recent answers
    submits = sorted((s for s in subs if s.kind == "submit"), key=lambda s: (clock.aware(s.created_at), s.id), reverse=True)[:10]
    titles = {p.id: p.title for p in db.scalars(select(Problem).where(Problem.id.in_({s.problem_id for s in submits if s.problem_id} or {0})))}
    recent = []
    for s in submits:
        if s.assessment_id in hidden:
            recent.append(RecentSubmissionOut(id=s.id, problem_id=None, title="Exam answer (result hidden)", language=s.language,
                                              verdict=None, passed_count=None, total_count=None, created_at=s.created_at, hidden=True))
        else:
            recent.append(RecentSubmissionOut(id=s.id, problem_id=s.problem_id, title=titles.get(s.problem_id, "?"), language=s.language,
                                              verdict=s.verdict, passed_count=s.passed, total_count=s.total, created_at=s.created_at))

    return StudentReportOut(
        student_id=student.id, name=student.name, email=student.email, courses=courses, problems=problems,
        streak_days=streak(activity_days, today),
        active_days_30=sum(1 for d in window if d in activity_days),
        total_submissions=sum(1 for s in subs if s.kind == "submit"),
        accepted_submissions=sum(1 for s in subs if s.kind == "submit" and s.verdict == ACCEPTED and s.assessment_id not in hidden),
        last_active_at=last_active(raw, student.id),
        activity=[DayActivity(date=d.isoformat(), submissions=v[0], accepted=v[1], lessons=v[2]) for d, v in per_day.items()],
        recent=recent, ai_requests_30d=None,
    )


# ---------------------------------------------------------------- one class
def batch_students(db: Session, batch: Batch) -> list[User]:
    return db.scalars(
        select(User)
        .join(BatchMember, BatchMember.user_id == User.id)
        .where(BatchMember.batch_id == batch.id, User.role == Role.student.value, User.is_active.is_(True))
        .order_by(func.lower(User.name), User.id)
    ).unique().all()


def _ai_counts(db: Session, user_ids: list[int], since: datetime) -> dict[int, list[AIRequest]]:
    out: dict[int, list[AIRequest]] = defaultdict(list)
    for r in db.scalars(select(AIRequest).where(AIRequest.user_id.in_(user_ids or [0]), AIRequest.status != "error")):
        if clock.aware(r.created_at) >= since:
            out[r.user_id].append(r)
    return out


@dataclass
class Core:
    members: list[User]
    raw: Raw
    courses: list[tuple[Course, set[int]]]
    rows: list[StudentRowOut]


def _core(db: Session, batch: Batch, now: datetime, inactive_days: int) -> Core:
    members = batch_students(db, batch)
    ids = [m.id for m in members]
    raw = gather(db, ids)
    courses = visible_courses(db, batch.college_id)
    total_lessons = sum(len(lessons) for _, lessons in courses)
    all_lessons = set().union(*(lessons for _, lessons in courses)) if courses else set()
    today = local_date(now)
    since = now - timedelta(days=GRAPH_DAYS)
    ai = _ai_counts(db, ids, since)

    rows = []
    for m in members:
        done = {lid for lid, _ in raw.lessons.get(m.id, [])} & all_lessons
        last = last_active(raw, m.id)
        days_inactive = None if last is None else max(0, (today - local_date(last)).days)
        status = "never_active" if last is None else "inactive" if days_inactive >= inactive_days else "active"
        rows.append(StudentRowOut(
            user_id=m.id, name=m.name, email=m.email, lessons_completed=len(done), lessons_total=total_lessons,
            completion_percent=_percent(len(done), total_lessons), problems_solved=len(solved_problem_ids(raw, m.id)),
            submissions_30d=sum(1 for s in raw.subs.get(m.id, []) if clock.aware(s.created_at) >= since),
            ai_requests_30d=len(ai.get(m.id, [])), last_active_at=last, days_inactive=days_inactive, status=status,
        ))
    return Core(members, raw, courses, rows)


def _summary(batch: Batch, core: Core) -> BatchSummaryOut:
    n = len(core.rows)
    lasts = [r.last_active_at for r in core.rows if r.last_active_at]
    return BatchSummaryOut(
        batch_id=batch.id, name=batch.name, year=batch.year, branch=batch.branch, student_count=n,
        total_lessons=core.rows[0].lessons_total if core.rows else sum(len(l) for _, l in core.courses),
        avg_completion_percent=round(sum(r.completion_percent for r in core.rows) / n, 1) if n else 0.0,
        avg_problems_solved=round(sum(r.problems_solved for r in core.rows) / n, 1) if n else 0.0,
        inactive_count=sum(1 for r in core.rows if r.status != "active"),
        last_active_at=max(lasts) if lasts else None,
    )


def batch_summary(db: Session, batch: Batch, now: datetime, inactive_days: int) -> BatchSummaryOut:
    return _summary(batch, _core(db, batch, now, inactive_days))


def _weak(db: Session, core: Core, now: datetime) -> tuple[list[WeakProblemOut], list[TopicOut]]:
    since = now - timedelta(days=WEAK_DAYS)
    ids = [m.id for m in core.members]
    attempted: dict[int, set[int]] = defaultdict(set)  # problem -> students who tried
    solved: dict[int, set[int]] = defaultdict(set)
    wrong: dict[int, int] = defaultdict(int)
    for uid in ids:
        for s in core.raw.subs.get(uid, []):
            # Only answers that were really judged. If the judge failed or has not finished, it says nothing about the student.
            if s.kind != "submit" or not s.problem_id or s.status != "done" or clock.aware(s.created_at) < since:
                continue
            attempted[s.problem_id].add(uid)
            if s.verdict == ACCEPTED:
                solved[s.problem_id].add(uid)
            elif s.verdict in WRONG:
                wrong[s.problem_id] += 1
    hints: dict[int, int] = defaultdict(int)
    for requests in _ai_counts(db, ids, since).values():
        for r in requests:
            if r.kind == "hint":
                hints[r.problem_id] += 1

    problems = {p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_(set(attempted) | set(hints) or {0})))}
    weak_problems = []
    for pid, students in attempted.items():
        p = problems.get(pid)
        if p is None or len(students) < MIN_STUDENTS_FOR_WEAK_PROBLEM or len(solved[pid]) >= len(students):
            continue
        weak_problems.append(WeakProblemOut(
            problem_id=pid, title=p.title, difficulty=p.difficulty, students_attempted=len(students),
            students_solved=len(solved[pid]), solve_rate_percent=_percent(len(solved[pid]), len(students)),
            wrong_submissions=wrong[pid], hint_requests=hints[pid],
        ))
    weak_problems.sort(key=lambda w: (w.solve_rate_percent, -w.hint_requests, -w.wrong_submissions, w.title.lower()))

    by_topic: dict[str, dict] = defaultdict(lambda: {"students": set(), "pairs": 0, "solved": 0, "wrong": 0, "hints": 0})
    for pid, students in attempted.items():
        p = problems.get(pid)
        for tag in (p.tags if p else []):
            t = by_topic[tag]
            t["students"] |= students
            t["pairs"] += len(students)
            t["solved"] += len(solved[pid])
            t["wrong"] += wrong[pid]
    for pid, count in hints.items():
        p = problems.get(pid)
        for tag in (p.tags if p else []):
            by_topic[tag]["hints"] += count
    weak_topics = [
        TopicOut(topic=tag, students=len(t["students"]), pairs_attempted=t["pairs"], pairs_solved=t["solved"],
                 solve_rate_percent=_percent(t["solved"], t["pairs"]), wrong_submissions=t["wrong"], hint_requests=t["hints"])
        for tag, t in by_topic.items() if t["pairs"] >= MIN_PAIRS_FOR_WEAK_TOPIC and t["solved"] < t["pairs"]
    ]
    weak_topics.sort(key=lambda t: (t.solve_rate_percent, -t.hint_requests, t.topic))
    return weak_problems[:LIST_LIMIT], weak_topics[:LIST_LIMIT]


def _assessment_averages(db: Session, batch: Batch, core: Core) -> list[AssessmentAverageOut]:
    ids = [m.id for m in core.members]
    out = []
    for a in db.scalars(
        select(Assessment).where(Assessment.batch_id == batch.id, Assessment.is_published.is_(True)).order_by(Assessment.starts_at.desc()).limit(20)
    ).unique():
        sheets = compute_sheets(db, a, ids)
        manual = {r.user_id: r.override_marks for r in db.scalars(select(AssessmentResult).where(AssessmentResult.assessment_id == a.id))}
        started = set(db.scalars(select(AssessmentAttempt.user_id).where(AssessmentAttempt.assessment_id == a.id)))
        percents = []
        for uid, sheet in sheets.items():
            if uid in started or any(p.attempted for p in sheet.per_problem):
                final = manual[uid] if manual.get(uid) is not None else sheet.auto_marks
                percents.append(_percent(final, total_marks(a)))
        out.append(AssessmentAverageOut(
            assessment_id=a.id, title=a.title, type=a.type, results_published=a.results_published, students=len(ids),
            participants=len(percents), avg_percent=round(sum(percents) / len(percents), 1) if percents else None,
        ))
    return out


def batch_report(db: Session, batch: Batch, now: datetime, inactive_days: int) -> BatchReportOut:
    core = _core(db, batch, now, inactive_days)
    weak_problems, weak_topics = _weak(db, core, now)
    n = len(core.rows)
    done_by_user = {m.id: {lid for lid, _ in core.raw.lessons.get(m.id, [])} for m in core.members}
    course_avgs = [
        CourseAverageOut(
            course_id=c.id, title=c.title, total_lessons=len(lessons),
            avg_percent=round(sum(_percent(len(done_by_user[m.id] & lessons), len(lessons)) for m in core.members) / n, 1) if n else 0.0,
        )
        for c, lessons in core.courses
    ]
    return BatchReportOut(
        summary=_summary(batch, core), inactive_days=inactive_days, students=core.rows,
        weak_topics=weak_topics, weak_problems=weak_problems, courses=course_avgs,
        assessments=_assessment_averages(db, batch, core),
    )


def ai_requests_in_last_30_days(db: Session, user_id: int, now: datetime) -> int:
    return len(_ai_counts(db, [user_id], now - timedelta(days=GRAPH_DAYS)).get(user_id, []))
