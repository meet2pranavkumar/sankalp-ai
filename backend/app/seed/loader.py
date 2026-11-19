"""Puts the starter course and its practice problems into the database."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Lesson, Problem, TestCase, Unit, User
from app.seed.starter_c_course import COURSE
from app.seed.starter_c_problems import PROBLEMS


@dataclass
class SeedReport:
    problems_created: int = 0
    problems_existing: int = 0
    course_created: bool = False
    course_id: int | None = None


def seed_starter_content(db: Session, owner: User, publish: bool = True) -> SeedReport:
    """Safe to run many times: anything that already exists is left alone."""
    report = SeedReport()

    for item in PROBLEMS:
        exists = db.scalar(
            select(Problem.id).where(Problem.college_id.is_(None), Problem.title == item["title"])
        )
        if exists:
            report.problems_existing += 1
            continue
        problem = Problem(
            college_id=None,
            created_by=owner.id,
            title=item["title"],
            statement_md=item["statement_md"],
            difficulty=item["difficulty"],
            tags=item["tags"],
            time_limit_ms=item.get("time_limit_ms", 1000),
            memory_limit_mb=item.get("memory_limit_mb", 256),
            is_public=True,
        )
        problem.test_cases = [
            TestCase(position=i, input=inp, expected_output=out, is_hidden=hidden, weight=1)
            for i, (inp, out, hidden) in enumerate(item["tests"], start=1)
        ]
        db.add(problem)
        report.problems_created += 1

    existing_course = db.scalar(
        select(Course).where(Course.college_id.is_(None), Course.title == COURSE["title"])
    )
    if existing_course:
        report.course_id = existing_course.id
    else:
        course = Course(
            college_id=None,
            created_by=owner.id,
            title=COURSE["title"],
            description=COURSE["description"],
            language=COURSE["language"],
            is_published=publish,
        )
        for u_pos, unit_data in enumerate(COURSE["units"], start=1):
            unit = Unit(title=unit_data["title"], position=u_pos)
            for l_pos, lesson_data in enumerate(unit_data["lessons"], start=1):
                unit.lessons.append(
                    Lesson(title=lesson_data["title"], content_md=lesson_data["content_md"].strip() + "\n", position=l_pos)
                )
            course.units.append(unit)
        db.add(course)
        db.flush()
        report.course_created = True
        report.course_id = course.id

    db.commit()
    return report
