from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models import College, Role
from app.schemas import CollegeCreate, CollegeOut

router = APIRouter(prefix="/colleges", tags=["colleges"])
super_only = require_roles(Role.super_admin)


@router.post("", response_model=CollegeOut, status_code=201)
def create_college(data: CollegeCreate, _=Depends(super_only), db: Session = Depends(get_db)):
    if db.scalar(select(College).where(College.code == data.code)):
        raise HTTPException(status_code=409, detail="A college with this code already exists.")
    college = College(**data.model_dump())
    db.add(college)
    db.commit()
    db.refresh(college)
    return college


@router.get("", response_model=list[CollegeOut])
def list_colleges(_=Depends(super_only), db: Session = Depends(get_db)):
    return db.scalars(select(College).order_by(College.name)).all()
