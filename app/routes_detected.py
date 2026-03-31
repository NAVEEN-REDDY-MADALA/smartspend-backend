from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import logging

from app.database import get_db
from app.auth import get_current_user
from app import models
from pydantic import BaseModel

router = APIRouter(prefix="/api/detected", tags=["Detected"])
logger = logging.getLogger(__name__)


# =====================================================
# SCHEMAS
# =====================================================
class DetectedTransactionCreate(BaseModel):
    amount: int
    merchant: str
    category_guess: str
    transaction_date: int           # milliseconds timestamp
    sms_hash: str
    transaction_type: str = "debit" # ← NEW: "debit" or "credit"
    credit_source: str    = ""      # ← NEW: "Salary", "Refund", "Cashback", "UPI Received", "Other"


# =====================================================
# CREATE DETECTED TRANSACTION  (called by Android)
# =====================================================
from sqlalchemy.exc import IntegrityError

@router.post("/create")
def create_detected_transaction(
    data: DetectedTransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Check existing first
    existing = (
        db.query(models.DetectedTransaction)
        .filter(
            models.DetectedTransaction.user_id == current_user.id,
            models.DetectedTransaction.sms_hash == data.sms_hash,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Duplicate transaction")

    txn_date = datetime.fromtimestamp(data.transaction_date / 1000)

    detected = models.DetectedTransaction(
        user_id          = current_user.id,
        amount           = data.amount,
        transaction_type = data.transaction_type,
        merchant         = data.merchant,
        category_guess   = data.category_guess,
        category         = data.category_guess,
        transaction_date = txn_date,
        status           = "pending",
        source           = "sms",
        sms_hash         = data.sms_hash,
        credit_source    = data.credit_source,
    )

    try:
        db.add(detected)
        db.commit()
        return {"message": "Detected transaction created"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate transaction")
# =====================================================
# SYNC DETECTED TRANSACTION  (called by Worker)
# =====================================================
@router.post("/sync")
def sync_detected_transaction(
    data: DetectedTransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    existing = (
        db.query(models.DetectedTransaction)
        .filter(
            models.DetectedTransaction.user_id == current_user.id,
            models.DetectedTransaction.sms_hash == data.sms_hash,
        )
        .first()
    )
    if existing:
        return {"synced": True}

    txn_date = datetime.fromtimestamp(data.transaction_date / 1000)

    detected = models.DetectedTransaction(
        user_id          = current_user.id,
        amount           = data.amount,
        transaction_type = data.transaction_type,
        merchant         = data.merchant,
        category_guess   = data.category_guess,
        category         = data.category_guess,
        transaction_date = txn_date,
        status           = "pending",
        source           = "sms",
        sms_hash         = data.sms_hash,
        credit_source    = data.credit_source,
    )

    db.add(detected)
    db.commit()
    return {"synced": True}


# =====================================================
# GET PENDING TRANSACTIONS  (called by frontend)
# Now returns transaction_type + credit_source
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
            "id":               t.id,
            "amount":           t.amount,
            "merchant":         t.merchant,
            "category_guess":   t.category_guess,
            "transaction_date": t.transaction_date.isoformat(),
            "sms_hash":         t.sms_hash,
            "status":           t.status,
            "transaction_type": t.transaction_type,             # ← NEW
            "credit_source":    getattr(t, "credit_source", ""), # ← NEW
        }
        for t in pending
    ]
# 

# =====================================================
# PENDING COUNT  (for badge)
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
# ACCEPT TRANSACTION  (Android + Web)
# ─ debit  → creates Expense (existing behaviour)
# ─ credit → creates Income  (NEW behaviour)
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

    txn_type = getattr(detected, "transaction_type", "debit")

    if txn_type == "credit":
        # ── Credit → save as Income ───────────────────────────────────────────
        credit_source = getattr(detected, "credit_source", "Other") or "Other"
        income = models.Income(
    user_id = current_user.id,
    amount  = detected.amount,
    source  = detected.merchant if detected.merchant and detected.merchant != "UNKNOWN"
              else (credit_source or "SMS Income"),
    date    = detected.transaction_date,
    is_auto = True,
)
        
        db.add(income)
        detected.status = "accepted"
        db.commit()

        logger.info(f"✅ Credit accepted → Income created (₹{detected.amount})")
        return {
            "message":          "Credit accepted and added to income",
            "amount":           detected.amount,
            "merchant":         detected.merchant,
            "category":         "Income",
            "transaction_type": "credit",
        }

    else:
        # ── Debit → save as Expense (existing behaviour) ──────────────────────
        expense = models.Expense(
            user_id  = current_user.id,
            amount   = detected.amount,
            category = detected.category or detected.category_guess,
            merchant = detected.merchant,
            date     = detected.transaction_date,
            is_auto  = True,
        )
        db.add(expense)
        detected.status = "accepted"
        db.commit()

        logger.info(f"✅ Debit accepted → Expense created (₹{detected.amount})")
        return {
            "message":          "Transaction accepted",
            "amount":           detected.amount,
            "merchant":         detected.merchant,
            "category":         detected.category or detected.category_guess,
            "transaction_type": "debit",
        }


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


# =====================================================
# PENDING COUNT BY TYPE  (optional — for split badges)
# =====================================================
@router.get("/count/split")
def get_pending_count_split(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    debit_count = (
        db.query(models.DetectedTransaction)
        .filter(
            models.DetectedTransaction.user_id == current_user.id,
            models.DetectedTransaction.status == "pending",
            models.DetectedTransaction.transaction_type == "debit",
        )
        .count()
    )
    credit_count = (
        db.query(models.DetectedTransaction)
        .filter(
            models.DetectedTransaction.user_id == current_user.id,
            models.DetectedTransaction.status == "pending",
            models.DetectedTransaction.transaction_type == "credit",
        )
        .count()
    )
    return {"debit": debit_count, "credit": credit_count, "total": debit_count + credit_count}