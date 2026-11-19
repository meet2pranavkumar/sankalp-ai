"""Rules about who is allowed to touch whose data. Kept in one place on purpose."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Batch, BatchMember, Role, User

# Which roles each role may create.
CREATABLE_ROLES: dict[str, set[str]] = {
    Role.super_admin.value: {Role.admin.value, Role.teacher.value, Role.student.value},
    Role.admin.value: {Role.teacher.value, Role.student.value},
    Role.teacher.value: {Role.student.value},
}

# Which roles each role may manage (reset password, etc.) inside a college.
MANAGEABLE_ROLES = CREATABLE_ROLES


def not_found(what: str = "Not found") -> HTTPException:
    # 404 instead of 403, so people cannot find out what exists in other colleges.
    return HTTPException(status_code=404, detail=what)


def resolve_college_id(actor: User, requested: int | None) -> int:
    """The college a new record belongs to."""
    if actor.role == Role.super_admin.value:
        if requested is None:
            raise HTTPException(status_code=422, detail="college_id is required.")
        return requested
    return actor.college_id


def can_manage(actor: User, target: User) -> bool:
    if actor.id == target.id:
        return False
    allowed = MANAGEABLE_ROLES.get(actor.role, set())
    if target.role not in allowed:
        return False
    if actor.role == Role.super_admin.value:
        return True
    return target.college_id == actor.college_id


def can_access_batch(actor: User, batch: Batch, db: Session) -> bool:
    if actor.role == Role.super_admin.value:
        return True
    if batch.college_id != actor.college_id:
        return False
    if actor.role == Role.admin.value:
        return True
    if actor.role == Role.teacher.value:
        return batch.created_by == actor.id
    if actor.role == Role.student.value:
        return (
            db.scalar(
                select(BatchMember.id).where(
                    BatchMember.batch_id == batch.id, BatchMember.user_id == actor.id
                )
            )
            is not None
        )
    return False


def get_batch_or_404(actor: User, batch_id: int, db: Session) -> Batch:
    batch = db.get(Batch, batch_id)
    if batch is None or not can_access_batch(actor, batch, db):
        raise not_found("Batch not found.")
    return batch
