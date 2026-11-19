from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access import (
    CREATABLE_ROLES,
    can_manage,
    get_batch_or_404,
    not_found,
    resolve_college_id,
)
from app.core.database import get_db
from app.core.deps import require_roles
from app.core.security import generate_temp_password, hash_password
from app.models import BatchMember, College, Role, User
from app.schemas import (
    BulkStudentResult,
    BulkStudentsCreate,
    PasswordResetOut,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])

staff = require_roles(Role.super_admin, Role.admin, Role.teacher)
admins = require_roles(Role.super_admin, Role.admin)


def _check_college_exists(db: Session, college_id: int) -> None:
    if db.get(College, college_id) is None:
        raise HTTPException(status_code=404, detail="College not found.")


def _add_to_batch(db: Session, actor: User, batch_id: int, college_id: int, user: User) -> None:
    batch = get_batch_or_404(actor, batch_id, db)
    if batch.college_id != college_id:
        raise not_found("Batch not found.")
    db.add(BatchMember(batch_id=batch.id, user_id=user.id))


@router.post("", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, actor: User = Depends(staff), db: Session = Depends(get_db)):
    if data.role.value not in CREATABLE_ROLES[actor.role]:
        raise HTTPException(status_code=403, detail=f"You cannot create a {data.role.value}.")
    college_id = resolve_college_id(actor, data.college_id)
    _check_college_exists(db, college_id)
    if data.batch_id is not None and data.role != Role.student:
        raise HTTPException(status_code=422, detail="Only students can be added to a batch.")
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(status_code=409, detail="This email is already registered.")

    user = User(
        college_id=college_id,
        name=data.name.strip(),
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role.value,
    )
    db.add(user)
    try:
        db.flush()
        if data.batch_id is not None:
            _add_to_batch(db, actor, data.batch_id, college_id, user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This email is already registered.")
    except HTTPException:
        db.rollback()
        raise
    db.refresh(user)
    return user


@router.post("/bulk", response_model=list[BulkStudentResult], status_code=201)
def create_students_bulk(
    data: BulkStudentsCreate, actor: User = Depends(staff), db: Session = Depends(get_db)
):
    """Add many students at once. Each student gets a random temporary password."""
    college_id = resolve_college_id(actor, data.college_id)
    _check_college_exists(db, college_id)
    batch = None
    if data.batch_id is not None:
        batch = get_batch_or_404(actor, data.batch_id, db)
        if batch.college_id != college_id:
            raise not_found("Batch not found.")

    results: list[BulkStudentResult] = []
    seen: set[str] = set()
    for row in data.students:
        if row.email in seen:
            results.append(BulkStudentResult(name=row.name, email=row.email, error="Repeated in this list."))
            continue
        seen.add(row.email)
        if db.scalar(select(User.id).where(User.email == row.email)):
            results.append(BulkStudentResult(name=row.name, email=row.email, error="Email already registered."))
            continue
        temp = generate_temp_password()
        user = User(
            college_id=college_id,
            name=row.name.strip(),
            email=row.email,
            password_hash=hash_password(temp),
            role=Role.student.value,
        )
        db.add(user)
        db.flush()
        if batch is not None:
            db.add(BatchMember(batch_id=batch.id, user_id=user.id))
        results.append(BulkStudentResult(name=row.name, email=row.email, temp_password=temp))
    db.commit()
    return results


@router.get("", response_model=list[UserOut])
def list_users(
    role: Role | None = None,
    college_id: int | None = None,
    batch_id: int | None = None,
    actor: User = Depends(staff),
    db: Session = Depends(get_db),
):
    query = select(User).order_by(User.name)
    if actor.role == Role.super_admin.value:
        if college_id is not None:
            query = query.where(User.college_id == college_id)
    else:
        query = query.where(User.college_id == actor.college_id)
    if actor.role == Role.teacher.value:
        query = query.where(User.role == Role.student.value)  # teachers only see students
    elif role is not None:
        query = query.where(User.role == role.value)
    if batch_id is not None:
        batch = get_batch_or_404(actor, batch_id, db)
        query = query.join(BatchMember, BatchMember.user_id == User.id).where(BatchMember.batch_id == batch.id)
    return db.scalars(query).unique().all()


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, actor: User = Depends(admins), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None or not can_manage(actor, target):
        raise not_found("User not found.")
    if data.name is not None:
        target.name = data.name.strip()
    if data.is_active is not None:
        target.is_active = data.is_active
    db.commit()
    db.refresh(target)
    return target


@router.post("/{user_id}/reset-password", response_model=PasswordResetOut)
def reset_password(user_id: int, actor: User = Depends(staff), db: Session = Depends(get_db)):
    """Give a student or teacher a new temporary password (no email service needed)."""
    target = db.get(User, user_id)
    if target is None or not can_manage(actor, target):
        raise not_found("User not found.")
    temp = generate_temp_password()
    target.password_hash = hash_password(temp)
    db.commit()
    return PasswordResetOut(temp_password=temp)
