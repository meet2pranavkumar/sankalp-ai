from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.course_access import can_edit_course, can_view_course
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models import Course, Lesson, LessonProgress, Role, Unit, User
from app.routers.courses import completed_ids, present, renumber
from app.schemas import CourseOut, LessonOut, LessonPatch

router = APIRouter(tags=["lessons"])
authors = require_roles(Role.super_admin, Role.admin, Role.teacher)


def _load(user: User, lesson_id: int, db: Session) -> tuple[Lesson, Unit, Course]:
    lesson = db.get(Lesson, lesson_id)
    unit = db.get(Unit, lesson.unit_id) if lesson else None
    course = db.get(Course, unit.course_id) if unit else None
    if course is None or not can_view_course(user, course):
        raise HTTPException(status_code=404, detail="Lesson not found.")
    return lesson, unit, course


@router.get("/lessons/{lesson_id}", response_model=LessonOut)
def get_lesson(lesson_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lesson, unit, course = _load(user, lesson_id, db)
    order = [l.id for u in course.units for l in u.lessons]  # the order a student reads them
    at = order.index(lesson.id)
    return LessonOut(
        id=lesson.id,
        unit_id=unit.id,
        unit_title=unit.title,
        course_id=course.id,
        course_title=course.title,
        title=lesson.title,
        content_md=lesson.content_md,
        video_url=lesson.video_url,
        position=lesson.position,
        completed=lesson.id in completed_ids(db, user),
        can_edit=can_edit_course(user, course),
        prev_lesson_id=order[at - 1] if at > 0 else None,
        next_lesson_id=order[at + 1] if at + 1 < len(order) else None,
    )


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
def update_lesson(lesson_id: int, data: LessonPatch, user: User = Depends(authors), db: Session = Depends(get_db)):
    lesson, _, course = _load(user, lesson_id, db)
    if not can_edit_course(user, course):
        raise HTTPException(status_code=403, detail="You cannot change this course.")
    changes = data.model_dump(exclude_unset=True)  # so "video_url": null can remove the video
    if "title" in changes and changes["title"] is not None:
        lesson.title = changes["title"].strip()
    if "content_md" in changes and changes["content_md"] is not None:
        lesson.content_md = changes["content_md"]
    if "video_url" in changes:
        lesson.video_url = changes["video_url"]
    db.commit()
    return get_lesson(lesson_id, user, db)


@router.delete("/lessons/{lesson_id}", response_model=CourseOut)
def delete_lesson(lesson_id: int, user: User = Depends(authors), db: Session = Depends(get_db)):
    lesson, unit, course = _load(user, lesson_id, db)
    if not can_edit_course(user, course):
        raise HTTPException(status_code=403, detail="You cannot change this course.")
    unit.lessons.remove(lesson)
    db.flush()
    renumber(list(unit.lessons))
    db.commit()
    db.refresh(course)
    return present(course, user, db)


@router.post("/lessons/{lesson_id}/complete", status_code=204)
def mark_complete(lesson_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Safe to call twice: a lesson is either done or not."""
    _load(user, lesson_id, db)
    exists = db.scalar(
        select(LessonProgress.id).where(LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id)
    )
    if exists is None:
        db.add(LessonProgress(user_id=user.id, lesson_id=lesson_id, completed_at=datetime.now(timezone.utc)))
        db.commit()


@router.delete("/lessons/{lesson_id}/complete", status_code=204)
def mark_not_complete(lesson_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _load(user, lesson_id, db)
    row = db.scalar(
        select(LessonProgress).where(LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id)
    )
    if row is not None:
        db.delete(row)
        db.commit()
