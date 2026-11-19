from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Problem, Role, User


def can_view_problem(user: User, problem: Problem) -> bool:
    if user.role == Role.super_admin.value or problem.is_public:
        return True
    return problem.college_id is not None and problem.college_id == user.college_id


def can_edit_problem(user: User, problem: Problem) -> bool:
    if user.role == Role.super_admin.value:
        return True
    if user.role not in (Role.teacher.value, Role.admin.value):
        return False
    if problem.college_id is None or problem.college_id != user.college_id:
        return False  # nobody but the platform owner edits the shared bank
    return user.role == Role.admin.value or problem.created_by == user.id


def get_problem_or_404(user: User, problem_id: int, db: Session) -> Problem:
    problem = db.get(Problem, problem_id)
    if problem is None or not can_view_problem(user, problem):
        raise HTTPException(status_code=404, detail="Problem not found.")
    return problem
