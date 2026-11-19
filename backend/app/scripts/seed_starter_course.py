"""Adds the free starter course (C Programming Basics) and its practice problems.

Run from the backend folder, after creating your super admin:
    python -m app.scripts.seed_starter_course
    python -m app.scripts.seed_starter_course --email you@example.com
    python -m app.scripts.seed_starter_course --draft      (add it, but do not publish yet)

It is safe to run again: nothing is added twice.
Every college can read the course. Teachers can press "Make my own copy" to change it.
"""
import argparse
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Role, User
from app.seed.loader import seed_starter_content


def main() -> int:
    parser = argparse.ArgumentParser(description="Add the starter course and problems")
    parser.add_argument("--email", help="Super admin who will own the content (default: the first super admin)")
    parser.add_argument("--draft", action="store_true", help="Do not publish the course")
    args = parser.parse_args()

    with SessionLocal() as db:
        query = select(User).where(User.role == Role.super_admin.value).order_by(User.id)
        if args.email:
            query = query.where(User.email == args.email.strip().lower())
        owner = db.scalars(query).first()
        if owner is None:
            print("No super admin found. Create one first: python -m app.scripts.create_super_admin")
            return 1
        owner_email = owner.email  # read it now: the database session closes at the end of this block
        report = seed_starter_content(db, owner, publish=not args.draft)

    print(f"Owner: {owner_email}")
    print(f"Practice problems: {report.problems_created} added, {report.problems_existing} already there")
    if report.course_created:
        print(f"Course 'C Programming Basics' added (id {report.course_id}), {'draft' if args.draft else 'published'}.")
    else:
        print(f"Course already exists (id {report.course_id}). Left unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
