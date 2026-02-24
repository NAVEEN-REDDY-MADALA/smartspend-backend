from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.utils import hash_password
from app.auth import SECRET_KEY, ALGORITHM
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError
import random
import string

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ────────────────────────────────────────────────────────────────────
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str


# ── Helper ─────────────────────────────────────────────────────────────────────
def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def create_reset_token(email: str) -> str:
    """Create a short-lived reset token (5 min) — bypasses create_access_token type restriction."""
    expire = datetime.utcnow() + timedelta(minutes=5)
    data = {
        "user_email": email,
        "purpose":    "password_reset",
        "exp":        expire,
        "type":       "password_reset"
    }
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — POST /api/auth/forgot-password
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email")

    # Invalidate any old unused OTPs for this email
    db.query(models.PasswordResetOTP).filter(
        models.PasswordResetOTP.email == payload.email,
        models.PasswordResetOTP.used  == False
    ).delete()
    db.commit()

    otp        = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    db.add(models.PasswordResetOTP(
        email      = payload.email,
        otp        = otp,
        expires_at = expires_at,
        used       = False
    ))
    db.commit()

    return {
        "message":            "OTP generated successfully",
        "otp":                otp,
        "expires_in_minutes": 10,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — POST /api/auth/verify-otp
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/verify-otp")
def verify_otp(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    record = db.query(models.PasswordResetOTP).filter(
        models.PasswordResetOTP.email == payload.email,
        models.PasswordResetOTP.otp   == payload.otp,
        models.PasswordResetOTP.used  == False
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if datetime.utcnow() > record.expires_at:
        raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")

    record.used = True
    db.commit()

    reset_token = create_reset_token(payload.email)

    return {
        "message":     "OTP verified successfully",
        "reset_token": reset_token
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — POST /api/auth/reset-password
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        data = jwt.decode(payload.reset_token, SECRET_KEY, algorithms=[ALGORITHM])
        if data.get("purpose") != "password_reset":
            raise HTTPException(status_code=400, detail="Invalid reset token")
        email = data.get("user_email")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid reset token")
    except JWTError:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user.password = hash_password(payload.new_password)
    db.commit()

    return {"message": "Password reset successfully. You can now log in."}