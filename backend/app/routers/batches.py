from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.access import get_batch_or_404, not_found
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models import Batch, BatchMember, Role, User
from app.schemas import BatchCreate, BatchOut, MembersAdd, UserOut

router = APIRouter(prefix="/batches", tags=["batches"])

teaching_staff = require_roles(Role.admin, Role.teacher)


@router.post("", response_model=BatchOut, status_code=201)
def create_batch(data: BatchCreate, actor: User = Depends(teaching_staff), db: Session = Depends(get_db)):
    batch = Batch(college_id=actor.college_id, created_by=actor.id, **data.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("", response_model=list[BatchOut])
def list_batches(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Admin: all batches of the college. Teacher: own batches. Student: batches they are in."""
    query = select(Batch).order_by(Batch.year.desc(), Batch.name)
    if actor.role == Role.super_admin.value:
        pass
    elif actor.role == Role.admin.value:
        query = query.where(Batch.college_id == actor.college_id)
    elif actor.role == Role.teacher.value:
        query = query.where(Batch.college_id == actor.college_id, Batch.created_by == actor.id)
    else:
        query = (
            query.join(BatchMember, BatchMember.batch_id == Batch.id)
            .where(BatchMember.user_id == actor.id)
        )
    return db.scalars(query).all()


@router.get("/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_batch_or_404(actor, batch_id, db)


@router.get("/{batch_id}/members", response_model=list[UserOut])
def list_members(batch_id: int, actor: User = Depends(teaching_staff), db: Session = Depends(get_db)):
    batch = get_batch_or_404(actor, batch_id, db)
    query = (
        select(User)
        .join(BatchMember, BatchMember.user_id == User.id)
        .where(BatchMember.batch_id == batch.id)
        .order_by(func.lower(User.name), User.id)
    )
    return db.scalars(query).unique().all()


@router.post("/{batch_id}/members", response_model=list[UserOut], status_code=201)
def add_members(
    batch_id: int, data: MembersAdd, actor: User = Depends(teaching_staff), db: Session = Depends(get_db)
):
    batch = get_batch_or_404(actor, batch_id, db)
    existing = set(db.scalars(select(BatchMember.user_id).where(BatchMember.batch_id == batch.id)))
    added: list[User] = []
    for user_id in dict.fromkeys(data.user_ids):  # remove repeats, keep order
        student = db.get(User, user_id)
        # Only students from the same college can be added. Anything else looks "not found".
        if student is None or student.role != Role.student.value or student.college_id != batch.college_id:
            raise not_found(f"Student {user_id} not found.")
        if user_id in existing:
            continue
        db.add(BatchMember(batch_id=batch.id, user_id=user_id))
        added.append(student)
    db.commit()
    return added


@router.delete("/{batch_id}/members/{user_id}", status_code=204)
def remove_member(
    batch_id: int, user_id: int, actor: User = Depends(teaching_staff), db: Session = Depends(get_db)
):
    batch = get_batch_or_404(actor, batch_id, db)
    member = db.scalar(
        select(BatchMember).where(BatchMember.batch_id == batch.id, BatchMember.user_id == user_id)
    )
    if member is None:
        raise HTTPException(status_code=404, detail="This student is not in the batch.")
    db.delete(member)
    db.commit()
