from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app import models, schemas
from app.database import get_db
from app.auth import get_current_user

router = APIRouter(prefix="/expenses", tags=["expenses"])


# -------------------------
# MANUAL EXPENSE ONLY
# -------------------------
@router.post("/", response_model=schemas.ExpenseOut)
def add_expense(
    expense: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    new_expense = models.Expense(
        user_id=current_user.id,
        amount=expense.amount,
        category=expense.category,
        date=expense.date or datetime.utcnow(),
        is_auto=False
    )

    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)

    return new_expense


# -------------------------
# GET ALL EXPENSES
# -------------------------
@router.get("/", response_model=list[schemas.ExpenseOut])
def get_expenses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.Expense)
        .filter(models.Expense.user_id == current_user.id)
        .order_by(models.Expense.date.desc())
        .all()
    )


# -------------------------
# DELETE EXPENSE
# -------------------------
@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    expense = db.query(models.Expense).filter(
        models.Expense.id == expense_id,
        models.Expense.user_id == current_user.id
    ).first()

    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    db.delete(expense)
    db.commit()

    return {"message": "Expense deleted"}
