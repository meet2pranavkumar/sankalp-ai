from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas import LoginIn, PasswordChange, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Same message for "no such email" and "wrong password", so nobody can
# use the login page to find out which emails exist.
BAD_LOGIN = HTTPException(status_code=401, detail="Wrong email or password.")


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if user is None or not verify_password(data.password, user.password_hash):
        raise BAD_LOGIN
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled. Contact your college admin.")
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", status_code=204)
def change_password(
    data: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is wrong.")
    user.password_hash = hash_password(data.new_password)
    db.commit()
