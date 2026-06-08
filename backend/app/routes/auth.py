from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password, is_legacy_hash, verify_password
from app.database import get_db
from app.dependencies.auth import create_access_token, get_current_user
from app.models.db_models import User
from app.models.schemas import LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if is_legacy_hash(user.password_hash):
        user.password_hash = hash_password(body.password)
        db.commit()

    token = create_access_token(user)
    return LoginResponse(
        access_token=token,
        role=user.role,
        username=user.username,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
