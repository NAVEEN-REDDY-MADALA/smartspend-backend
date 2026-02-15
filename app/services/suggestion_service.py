from sqlalchemy.orm import Session
from datetime import datetime
from app import models


def generate_expense_suggestions(db: Session, user_id: int):
    """
    Generate expense suggestions from learned patterns
    """

    patterns = db.query(models.ExpensePattern)\
        .filter(models.ExpensePattern.user_id == user_id)\
        .filter(models.ExpensePattern.confidence >= 0.6)\
        .all()

    for pattern in patterns:
        # Avoid duplicate pending suggestions
        existing = db.query(models.ExpenseSuggestion).filter(
            models.ExpenseSuggestion.user_id == user_id,
            models.ExpenseSuggestion.category == pattern.category,
            models.ExpenseSuggestion.status == "pending"
        ).first()

        if existing:
            continue

        suggestion = models.ExpenseSuggestion(
            user_id=user_id,
            category=pattern.category,
            suggested_amount=round(pattern.avg_amount),
            suggested_date=datetime.utcnow(),
            source="pattern"
        )

        db.add(suggestion)

    db.commit()
