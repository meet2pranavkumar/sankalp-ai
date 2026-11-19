from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Course, Role, User


def can_edit_course(user: User, course: Course) -> bool:
    if user.role == Role.super_admin.value:
        return True
    if course.college_id is None or course.college_id != user.college_id:
        return False  # only the platform owner changes shared courses
    if user.role == Role.admin.value:
        return True
    return user.role == Role.teacher.value and course.created_by == user.id


def can_view_course(user: User, course: Course) -> bool:
    if user.role == Role.super_admin.value:
        return True
    if course.college_id is not None and course.college_id != user.college_id:
        return False
    if course.is_published:
        return True
    return can_edit_course(user, course)  # drafts are only for their authors


def get_course_or_404(user: User, course_id: int, db: Session) -> Course:
    course = db.get(Course, course_id)
    if course is None or not can_view_course(user, course):
        raise HTTPException(status_code=404, detail="Course not found.")
    return course


def get_editable_course(user: User, course_id: int, db: Session) -> Course:
    course = get_course_or_404(user, course_id, db)
    if not can_edit_course(user, course):
        raise HTTPException(status_code=403, detail="You cannot change this course.")
    return course
