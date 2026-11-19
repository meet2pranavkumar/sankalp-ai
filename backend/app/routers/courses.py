from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.course_access import can_edit_course, can_view_course, get_course_or_404, get_editable_course
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models import Course, Lesson, LessonProgress, Role, Unit, User
from app.schemas import (
    CourseIn, CourseOut, CoursePatch, CourseSummary, LessonBrief, LessonIn, LessonOut, LessonPatch,
    OrderIn, UnitIn, UnitOut,
)

router = APIRouter(tags=["courses"])
authors = require_roles(Role.super_admin, Role.admin, Role.teacher)


# ---------- helpers ----------
def completed_ids(db: Session, user: User) -> set[int]:
    return set(db.scalars(select(LessonProgress.lesson_id).where(LessonProgress.user_id == user.id)))


def summarize(course: Course, user: User, done: set[int]) -> CourseSummary:
    lesson_ids = [lesson.id for unit in course.units for lesson in unit.lessons]
    return CourseSummary(
        id=course.id,
        title=course.title,
        description=course.description,
        language=course.language,
        is_published=course.is_published,
        is_shared=course.college_id is None,
        can_edit=can_edit_course(user, course),
        total_lessons=len(lesson_ids),
        completed_lessons=sum(1 for i in lesson_ids if i in done),
    )


def present(course: Course, user: User, db: Session) -> CourseOut:
    done = completed_ids(db, user)
    base = summarize(course, user, done)
    units = [
        UnitOut(
            id=unit.id,
            title=unit.title,
            position=unit.position,
            lessons=[
                LessonBrief(id=l.id, title=l.title, position=l.position, completed=l.id in done)
                for l in unit.lessons
            ],
        )
        for unit in course.units
    ]
    return CourseOut(**base.model_dump(), units=units)


def apply_order(items: list, ids: list[int]) -> None:
    """Give the items new positions 1..n in the order of ids. ids must be exactly the same items."""
    if len(set(ids)) != len(ids) or set(ids) != {item.id for item in items}:
        raise HTTPException(status_code=422, detail="The list must contain every item exactly once.")
    by_id = {item.id: item for item in items}
    for position, item_id in enumerate(ids, start=1):
        by_id[item_id].position = position


def renumber(items: list) -> None:
    for position, item in enumerate(sorted(items, key=lambda i: i.position), start=1):
        item.position = position


def get_editable_unit(user: User, unit_id: int, db: Session) -> Unit:
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not found.")
    course = db.get(Course, unit.course_id)
    if not can_view_course(user, course):
        raise HTTPException(status_code=404, detail="Unit not found.")
    if not can_edit_course(user, course):
        raise HTTPException(status_code=403, detail="You cannot change this course.")
    return unit


# ---------- courses ----------
@router.get("/courses", response_model=list[CourseSummary])
def list_courses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Course).order_by(Course.title)
    if user.role != Role.super_admin.value:
        query = query.where(or_(Course.college_id.is_(None), Course.college_id == user.college_id))
    done = completed_ids(db, user)
    return [summarize(c, user, done) for c in db.scalars(query).unique() if can_view_course(user, c)]


@router.post("/courses", response_model=CourseOut, status_code=201)
def create_course(data: CourseIn, user: User = Depends(authors), db: Session = Depends(get_db)):
    course = Course(
        college_id=None if user.role == Role.super_admin.value else user.college_id,
        created_by=user.id,
        title=data.title.strip(),
        description=data.description,
        language=data.language,
        is_published=False,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return present(course, user, db)


@router.get("/courses/{course_id}", response_model=CourseOut)
def get_course(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return present(get_course_or_404(user, course_id, db), user, db)


@router.patch("/courses/{course_id}", response_model=CourseOut)
def update_course(course_id: int, data: CoursePatch, user: User = Depends(authors), db: Session = Depends(get_db)):
    course = get_editable_course(user, course_id, db)
    for field in ("title", "description", "language", "is_published"):
        value = getattr(data, field)
        if value is not None:
            setattr(course, field, value.strip() if field == "title" else value)
    db.commit()
    db.refresh(course)
    return present(course, user, db)


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: int, user: User = Depends(authors), db: Session = Depends(get_db)):
    course = get_editable_course(user, course_id, db)
    db.delete(course)  # units, lessons and everyone's progress in them go too
    db.commit()


@router.post("/courses/{course_id}/duplicate", response_model=CourseOut, status_code=201)
def duplicate_course(course_id: int, user: User = Depends(authors), db: Session = Depends(get_db)):
    """Copy a course (for example the shared starter course) so your college can change it."""
    source = get_course_or_404(user, course_id, db)
    copy = Course(
        college_id=None if user.role == Role.super_admin.value else user.college_id,
        created_by=user.id,
        title=f"{source.title} (copy)"[:200],
        description=source.description,
        language=source.language,
        is_published=False,
    )
    for unit in source.units:
        new_unit = Unit(title=unit.title, position=unit.position)
        for lesson in unit.lessons:
            new_unit.lessons.append(
                Lesson(title=lesson.title, content_md=lesson.content_md, video_url=lesson.video_url, position=lesson.position)
            )
        copy.units.append(new_unit)
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return present(copy, user, db)


# ---------- units ----------
@router.post("/courses/{course_id}/units", response_model=CourseOut, status_code=201)
def add_unit(course_id: int, data: UnitIn, user: User = Depends(authors), db: Session = Depends(get_db)):
    course = get_editable_course(user, course_id, db)
    position = max((u.position for u in course.units), default=0) + 1
    course.units.append(Unit(title=data.title.strip(), position=position))
    db.commit()
    db.refresh(course)
    return present(course, user, db)


@router.put("/courses/{course_id}/units/order", response_model=CourseOut)
def reorder_units(course_id: int, data: OrderIn, user: User = Depends(authors), db: Session = Depends(get_db)):
    course = get_editable_course(user, course_id, db)
    apply_order(list(course.units), data.ids)
    db.commit()
    db.refresh(course)
    return present(course, user, db)


@router.patch("/units/{unit_id}", response_model=CourseOut)
def rename_unit(unit_id: int, data: UnitIn, user: User = Depends(authors), db: Session = Depends(get_db)):
    unit = get_editable_unit(user, unit_id, db)
    unit.title = data.title.strip()
    db.commit()
    course = db.get(Course, unit.course_id)
    db.refresh(course)
    return present(course, user, db)


@router.delete("/units/{unit_id}", response_model=CourseOut)
def delete_unit(unit_id: int, user: User = Depends(authors), db: Session = Depends(get_db)):
    unit = get_editable_unit(user, unit_id, db)
    course = db.get(Course, unit.course_id)
    course.units.remove(unit)
    db.flush()
    renumber(list(course.units))
    db.commit()
    db.refresh(course)
    return present(course, user, db)


# ---------- lessons (create and reorder live here, because they belong to a unit) ----------
@router.post("/units/{unit_id}/lessons", response_model=CourseOut, status_code=201)
def add_lesson(unit_id: int, data: LessonIn, user: User = Depends(authors), db: Session = Depends(get_db)):
    unit = get_editable_unit(user, unit_id, db)
    position = max((l.position for l in unit.lessons), default=0) + 1
    unit.lessons.append(
        Lesson(title=data.title.strip(), content_md=data.content_md, video_url=data.video_url, position=position)
    )
    db.commit()
    course = db.get(Course, unit.course_id)
    db.refresh(course)
    return present(course, user, db)


@router.put("/units/{unit_id}/lessons/order", response_model=CourseOut)
def reorder_lessons(unit_id: int, data: OrderIn, user: User = Depends(authors), db: Session = Depends(get_db)):
    unit = get_editable_unit(user, unit_id, db)
    apply_order(list(unit.lessons), data.ids)
    db.commit()
    course = db.get(Course, unit.course_id)
    db.refresh(course)
    return present(course, user, db)
