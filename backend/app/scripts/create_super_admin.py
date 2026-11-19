"""Create the first platform owner account.

Run from the backend folder:
    python -m app.scripts.create_super_admin --name "Your Name" --email you@example.com
It asks for the password so it never appears in your shell history.
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Role, User


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a super admin user")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", help="If left out, you will be asked for it.")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password (min 8 characters): ")
    if len(password) < 8:
        print("Password must have at least 8 characters.")
        return 1

    email = args.email.strip().lower()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print("A user with this email already exists.")
            return 1
        db.add(
            User(
                name=args.name.strip(),
                email=email,
                password_hash=hash_password(password),
                role=Role.super_admin.value,
                college_id=None,
            )
        )
        db.commit()
    print(f"Super admin created: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
