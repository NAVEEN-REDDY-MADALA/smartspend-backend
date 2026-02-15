from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import schemas, models
from app.database import get_db
from app.utils import hash_password, verify_password
from app.auth import create_access_token, create_refresh_token, verify_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()

    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(
        name=user.name,
        email=user.email,
        password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()

    return {"message": "User created successfully"}


@router.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()

    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token = create_access_token({"user_id": db_user.id})
    refresh_token = create_refresh_token({"user_id": db_user.id})  # ✅ Create refresh token
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,  # ✅ Return both tokens
        "token_type": "bearer"
    }


@router.post("/refresh")
def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    """Get new access token using refresh token"""
    user_id = verify_refresh_token(refresh_token)
    
    # Verify user still exists
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Create new access token
    new_access_token = create_access_token({"user_id": user_id})
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }