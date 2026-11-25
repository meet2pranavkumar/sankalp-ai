from datetime import datetime, timedelta, timezone

from app.models import AIRequest, LessonProgress, Submission

UTC = timezone.utc
NOON = datetime(2026, 12, 10, 12, 0, tzinfo=UTC)  # "now" in the report tests: 10 December 2026, 12:00 UTC
API = "/api/v1"


def at(days_ago=0, hour=10):
    """A moment on a day counted back from the fixed 'today'."""
    return NOON.replace(hour=hour) - timedelta(days=days_ago)


def add_sub(db, user, problem_id, verdict="accepted", kind="submit", when=None, assessment_id=None, passed=None, total=2,
            status="done", language="python"):
    if passed is None:
        passed = total if verdict == "accepted" else 1
    row = Submission(
        user_id=user.id, problem_id=problem_id, kind=kind, language=language, source_code="x", status=status,
        verdict=verdict if status == "done" else None, passed_count=passed if status == "done" else None,
        total_count=total if status == "done" else None, assessment_id=assessment_id, created_at=when or at(),
    )
    db.add(row)
    db.commit()
    return row


def lesson_done(db, user, lesson_id, when=None):
    db.add(LessonProgress(user_id=user.id, lesson_id=lesson_id, completed_at=when or at()))
    db.commit()


def ai_request(db, user, problem_id, kind="hint", status="ok", when=None, level=1):
    db.add(AIRequest(user_id=user.id, problem_id=problem_id, kind=kind, level=level if kind == "hint" else None, language="python",
                     status=status, response_text="x", created_at=when or at()))
    db.commit()


def course_with_lessons(client, headers, count=4, title="C Basics", publish=True):
    """A course with one unit and `count` lessons. Returns (course, [lesson ids])."""
    course = client.post(f"{API}/courses", headers=headers, json={"title": title}).json()
    unit = client.post(f"{API}/courses/{course['id']}/units", headers=headers, json={"title": "Unit"}).json()["units"][0]
    for i in range(count):
        client.post(f"{API}/units/{unit['id']}/lessons", headers=headers, json={"title": f"Lesson {i + 1}"})
    if publish:
        client.patch(f"{API}/courses/{course['id']}", headers=headers, json={"is_published": True})
    full = client.get(f"{API}/courses/{course['id']}", headers=headers).json()
    return full, [lesson["id"] for u in full["units"] for lesson in u["lessons"]]
