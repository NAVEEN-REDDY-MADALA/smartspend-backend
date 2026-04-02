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
    transaction_type: str = "debit"
    credit_source: str    = ""


# =====================================================
# CREATE DETECTED TRANSACTION  (called by Android)
# ─ FIX: If already accepted/ignored/auto_confirmed → return 409
#   so Android knows NOT to re-show it as pending
# =====================================================
from sqlalchemy.exc import IntegrityError

@router.post("/create")
def create_detected_transaction(
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
        # ── FIX: Return the current status so Android can update local DB ──
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Duplicate transaction",
                "status": existing.status,   # "accepted", "ignored", "pending", etc.
                "sms_hash": existing.sms_hash,
            }
        )

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
        return {"message": "Detected transaction created", "status": "pending"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"error": "Duplicate transaction"})


# =====================================================
# SYNC DETECTED TRANSACTION  (called by Worker/Android background sync)
# ─ FIX: If already accepted/ignored → return existing status
#   so Android can update its local DB and stop re-syncing
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
        # ── FIX: Tell Android the real status so it can update local DB ────
        return {
            "synced":   True,
            "status":   existing.status,   # "accepted", "ignored", "pending"
            "sms_hash": existing.sms_hash,
        }

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
    return {"synced": True, "status": "pending"}


# =====================================================
# GET PENDING TRANSACTIONS  (called by frontend)
# ─ STRICTLY only status == "pending"
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
            models.DetectedTransaction.status == "pending",   # STRICTLY pending only
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
            "transaction_type": t.transaction_type,
            "credit_source":    getattr(t, "credit_source", "") or "",
        }
        for t in pending
    ]


# =====================================================
# PENDING COUNT  (for badge)
# ─ STRICTLY only status == "pending"
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
            models.DetectedTransaction.status == "pending",   # STRICTLY pending only
        )
        .count()
    )
    return {"count": count}


# =====================================================
# CHECK STATUS  (NEW — called by Android to check if web-accepted)
# Android calls this to sync local DB with backend status
# =====================================================
@router.get("/status/{sms_hash}")
def get_transaction_status(
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
        return {"status": "not_found", "sms_hash": sms_hash}
    return {"status": detected.status, "sms_hash": sms_hash}


# =====================================================
# ACCEPT TRANSACTION  (Android + Web)
# ─ debit  → creates Expense
# ─ credit → creates Income
# ─ FIX: If already accepted → return success (idempotent)
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

    # ── FIX: Idempotent — if already accepted, return success immediately ──
    if detected.status == "accepted":
        return {
            "message":          "Already accepted",
            "amount":           detected.amount,
            "merchant":         detected.merchant,
            "transaction_type": getattr(detected, "transaction_type", "debit"),
        }

    if detected.status == "ignored":
        return {"message": "Already ignored"}

    txn_type = getattr(detected, "transaction_type", "debit")

    if txn_type == "credit":
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
# ─ FIX: Idempotent — if already ignored → return success
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

    if detected.status in ("ignored", "accepted"):
        return {"message": f"Already {detected.status}"}

    detected.status = "ignored"
    db.commit()
    return {"message": "Transaction ignored"}


# =====================================================
# AUTO-ACCEPT  (called by Android in auto mode)
# ─ Creates expense/income AND marks as auto_confirmed
# =====================================================
@router.post("/auto-accept/{sms_hash}")
def auto_accept_transaction(
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

    if detected.status in ("accepted", "auto_confirmed"):
        return {"message": "Already processed", "status": detected.status}

    txn_type = getattr(detected, "transaction_type", "debit")

    if txn_type == "credit":
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
        detected.status = "auto_confirmed"
        db.commit()
        return {"message": "Auto-confirmed as income", "amount": detected.amount, "transaction_type": "credit"}
    else:
        expense = models.Expense(
            user_id  = current_user.id,
            amount   = detected.amount,
            category = detected.category or detected.category_guess,
            merchant = detected.merchant,
            date     = detected.transaction_date,
            is_auto  = True,
        )
        db.add(expense)
        detected.status = "auto_confirmed"
        db.commit()
        return {"message": "Auto-confirmed as expense", "amount": detected.amount, "transaction_type": "debit"}
# 

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
# PENDING COUNT BY TYPE
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