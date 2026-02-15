from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app import models
router = APIRouter(
    prefix="/suggestions",
    tags=["suggestions"]
)


@router.get("/")
def get_suggestions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.ExpenseSuggestion)
        .filter(
            models.ExpenseSuggestion.user_id == current_user.id,
            models.ExpenseSuggestion.status == "pending"
        )
        .all()
    )


@router.post("/{suggestion_id}/confirm")
def confirm_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    s = db.query(models.ExpenseSuggestion).filter(
        models.ExpenseSuggestion.id == suggestion_id,
        models.ExpenseSuggestion.user_id == current_user.id
    ).first()

    if not s:
        return {"message": "Suggestion not found"}

    # Add expense
    expense = models.Expense(
        user_id=current_user.id,
        amount=s.suggested_amount,
        category=s.category
    )

    s.status = "confirmed"

    db.add(expense)
    db.commit()

    return {"message": "Suggestion confirmed"}


@router.post("/{suggestion_id}/reject")
def reject_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    s = db.query(models.ExpenseSuggestion).filter(
        models.ExpenseSuggestion.id == suggestion_id,
        models.ExpenseSuggestion.user_id == current_user.id
    ).first()

    if not s:
        return {"message": "Suggestion not found"}

    s.status = "rejected"
    db.commit()

    return {"message": "Suggestion rejected"}
