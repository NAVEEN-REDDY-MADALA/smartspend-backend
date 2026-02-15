from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.database import get_db
from app.auth import get_current_user
from app import models

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/")
def get_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get financial summary: total income, total expenses, and savings
    """
    # Calculate total income
    total_income = (
        db.query(func.sum(models.Income.amount))
        .filter(models.Income.user_id == current_user.id)
        .scalar() or 0.0
    )
    
    # Calculate total expenses
    total_expenses = (
        db.query(func.sum(models.Expense.amount))
        .filter(models.Expense.user_id == current_user.id)
        .scalar() or 0.0
    )
    
    # Calculate savings (income - expenses)
    savings = total_income - total_expenses
    
    return {
        "total_income": round(float(total_income), 2),
        "total_expenses": round(float(total_expenses), 2),
        "savings": round(float(savings), 2)
    }

