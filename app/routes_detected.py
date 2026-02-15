from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.auth import get_current_user
from app import models
from pydantic import BaseModel

router = APIRouter(prefix="/api/detected", tags=["detected"])
logger = logging.getLogger(__name__)


# =====================================================
# SCHEMA
# =====================================================
class DetectedTransactionCreate(BaseModel):
    amount: int
    merchant: str
    category_guess: str
    transaction_date: int  # milliseconds
    sms_hash: str


# =====================================================
# CREATE DETECTED TRANSACTION (ANDROID ONLY)
# =====================================================
@router.post("/create")
def create_detected_transaction(
    data: DetectedTransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    logger.info("📥 CREATE DETECTED TRANSACTION")

    existing = (
        db.query(models.DetectedTransaction)
        .filter(
            models.DetectedTransaction.user_id == current_user.id,
            models.DetectedTransaction.sms_hash == data.sms_hash,
        )
        .first()
    )

    if existing:
        logger.info("⚠️ Duplicate detected, skipping")
        return {"duplicate": True}

    txn_date = datetime.fromtimestamp(data.transaction_date / 1000)

    detected = models.DetectedTransaction(
        user_id=current_user.id,
        amount=data.amount,
        transaction_type="debit",
        merchant=data.merchant,
        category_guess=data.category_guess,
        category=data.category_guess,
        transaction_date=txn_date,
        status="pending",
        source="sms",
        sms_hash=data.sms_hash,
    )

    db.add(detected)
    db.commit()

    logger.info("✅ Detected transaction saved")

    return {"message": "Detected transaction created"}


# =====================================================
# GET PENDING TRANSACTIONS (FRONTEND)
# =====================================================
@router.get("/pending")
def get_pending_transactions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    pending = (
        db.query(models.DetectedTransaction)
        .filter(
            models.DetectedTransaction.user_id == current_user.id,
            models.DetectedTransaction.status == "pending",
        )
        .order_by(models.DetectedTransaction.transaction_date.desc())
        .all()
    )

    return [
        {
            "id": t.id,
            "amount": t.amount,
            "merchant": t.merchant,
            "category_guess": t.category_guess,
            "transaction_date": t.transaction_date.isoformat(),
            "sms_hash": t.sms_hash,
            "status": t.status,
        }
        for t in pending
    ]


# =====================================================
# PENDING COUNT (BADGE)
# =====================================================
@router.get("/count")
def get_pending_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    count = (
        db.query(models.DetectedTransaction)
        .filter(
            models.DetectedTransaction.user_id == current_user.id,
            models.DetectedTransaction.status == "pending",
        )
        .count()
    )
    return {"count": count}


# =====================================================
# ACCEPT TRANSACTION (ANDROID + WEB)
# THIS IS THE ONLY PLACE THAT CREATES EXPENSE
# =====================================================
@router.post("/accept/{sms_hash}")
def accept_transaction(
    sms_hash: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    detected = (
        db.query(models.DetectedTransaction)
        .filter(
            models.DetectedTransaction.user_id == current_user.id,
            models.DetectedTransaction.sms_hash == sms_hash,
        )
        .first()
    )

    if not detected:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if detected.status != "pending":
        return {"message": "Already processed"}

    # ✅ Create expense
    expense = models.Expense(
        user_id=current_user.id,
        amount=detected.amount,
        category=detected.category or detected.category_guess,
        date=detected.transaction_date,
        is_auto=True,
    )

    detected.status = "accepted"

    db.add(expense)
    db.commit()

    logger.info("✅ Transaction accepted & expense created")

    return {"message": "Transaction accepted"}


# =====================================================
# IGNORE TRANSACTION
# =====================================================
@router.post("/ignore/{sms_hash}")
def ignore_transaction(
    sms_hash: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    detected = (
        db.query(models.DetectedTransaction)
        .filter(
            models.DetectedTransaction.user_id == current_user.id,
            models.DetectedTransaction.sms_hash == sms_hash,
        )
        .first()
    )

    if not detected:
        raise HTTPException(status_code=404, detail="Transaction not found")

    detected.status = "ignored"
    db.commit()

    logger.info("❌ Transaction ignored")

    return {"message": "Transaction ignored"}


# =====================================================
# MARK OLD PENDING AS MISSED
# =====================================================
@router.post("/mark-missed")
def mark_old_as_missed(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    cutoff = datetime.utcnow() - timedelta(minutes=10)

    old = (
        db.query(models.DetectedTransaction)
        .filter(
            models.DetectedTransaction.user_id == current_user.id,
            models.DetectedTransaction.status == "pending",
            models.DetectedTransaction.transaction_date < cutoff,
        )
        .all()
    )

    for t in old:
        t.status = "missed"

    db.commit()

    return {"marked": len(old)}
