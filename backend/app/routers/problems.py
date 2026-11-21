from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.problem_access import can_edit_problem, get_problem_or_404
from app.models import Assessment, Problem, Role, Submission, TestCase, User
from app.schemas import LanguageOut, ProblemIn, ProblemOut, ProblemSummary, TestCaseOut
from app.services.assessments import locked_problem_ids
from app.services.grading import ACCEPTED
from app.services.languages import LANGUAGES

router = APIRouter(tags=["problems"])
authors = require_roles(Role.super_admin, Role.admin, Role.teacher)


def present_problem(problem: Problem, user: User) -> ProblemOut:
    can_edit = can_edit_problem(user, problem)
    tests = [t for t in problem.test_cases if can_edit or not t.is_hidden]  # hidden tests never leave the server
    return ProblemOut(
        id=problem.id,
        college_id=problem.college_id,
        created_by=problem.created_by,
        title=problem.title,
        statement_md=problem.statement_md,
        difficulty=problem.difficulty,
        tags=problem.tags,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        is_public=problem.is_public,
        can_edit=can_edit,
        test_cases=[TestCaseOut.model_validate(t) for t in tests],
    )


def _fill_tests(problem: Problem, data: ProblemIn) -> None:
    problem.test_cases = [
        TestCase(
            position=i,
            input=t.input,
            expected_output=t.expected_output,
            is_hidden=t.is_hidden,
            weight=t.weight,
        )
        for i, t in enumerate(data.test_cases, start=1)
    ]


@router.get("/languages", response_model=list[LanguageOut])
def list_languages():
    return [LanguageOut(key=lang.key, label=lang.label) for lang in LANGUAGES.values()]


@router.get("/problems", response_model=list[ProblemSummary])
def list_problems(
    q: str | None = None,
    difficulty: str | None = None,
    tag: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Problem).order_by(Problem.created_at.desc(), Problem.id.desc())
    if user.role != Role.super_admin.value:
        visible = Problem.is_public.is_(True)
        if user.college_id is not None:
            visible = or_(visible, Problem.college_id == user.college_id)
        query = query.where(visible)
    if difficulty:
        query = query.where(Problem.difficulty == difficulty)
    if q:
        query = query.where(Problem.title.ilike(f"%{q.strip()}%"))
    problems = db.scalars(query).all()
    if user.role == Role.student.value:
        locked = locked_problem_ids(db, clock.utc_now())  # exam questions stay secret until the exam is over
        problems = [p for p in problems if p.id not in locked]
    if tag:
        wanted = tag.strip().lower()
        problems = [p for p in problems if wanted in p.tags]

    # An exam answer must not show a green tick before the teacher publishes the results.
    secret_assessments = set(
        db.scalars(select(Assessment.id).where(Assessment.type == "exam", Assessment.results_published.is_(False)))
    )
    solved_ids = {
        problem_id
        for problem_id, assessment_id in db.execute(
            select(Submission.problem_id, Submission.assessment_id).where(
                Submission.user_id == user.id,
                Submission.kind == "submit",
                Submission.verdict == ACCEPTED,
            )
        )
        if assessment_id not in secret_assessments
    }
    return [
        ProblemSummary(
            id=p.id, title=p.title, difficulty=p.difficulty, tags=p.tags,
            is_public=p.is_public, solved=p.id in solved_ids,
        )
        for p in problems
    ]


@router.post("/problems", response_model=ProblemOut, status_code=201)
def create_problem(data: ProblemIn, user: User = Depends(authors), db: Session = Depends(get_db)):
    is_super = user.role == Role.super_admin.value
    if data.is_public and not is_super:
        raise HTTPException(status_code=403, detail="Only the platform owner can add problems to the shared bank.")
    problem = Problem(
        college_id=None if is_super else user.college_id,
        created_by=user.id,
        title=data.title.strip(),
        statement_md=data.statement_md,
        difficulty=data.difficulty,
        tags=data.tags,
        time_limit_ms=data.time_limit_ms,
        memory_limit_mb=data.memory_limit_mb,
        is_public=True if is_super else False,  # the owner has no college, so the owner's problems are shared
    )
    _fill_tests(problem, data)
    db.add(problem)
    db.commit()
    db.refresh(problem)
    return present_problem(problem, user)


@router.get("/problems/{problem_id}", response_model=ProblemOut)
def get_problem(problem_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return present_problem(get_problem_or_404(user, problem_id, db), user)


@router.put("/problems/{problem_id}", response_model=ProblemOut)
def update_problem(
    problem_id: int, data: ProblemIn, user: User = Depends(authors), db: Session = Depends(get_db)
):
    problem = get_problem_or_404(user, problem_id, db)
    if not can_edit_problem(user, problem):
        raise HTTPException(status_code=403, detail="You cannot edit this problem.")
    if data.is_public != problem.is_public and user.role != Role.super_admin.value:
        raise HTTPException(status_code=403, detail="Only the platform owner can change sharing.")
    problem.title = data.title.strip()
    problem.statement_md = data.statement_md
    problem.difficulty = data.difficulty
    problem.tags = data.tags
    problem.time_limit_ms = data.time_limit_ms
    problem.memory_limit_mb = data.memory_limit_mb
    _fill_tests(problem, data)  # old tests are removed, new ones saved
    db.commit()
    db.refresh(problem)
    return present_problem(problem, user)
