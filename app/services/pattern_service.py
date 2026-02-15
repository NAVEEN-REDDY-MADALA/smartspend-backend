from sqlalchemy.orm import Session
from collections import defaultdict
from statistics import mean
from datetime import datetime

from app import models
def learn_expense_patterns(db: Session, user_id: int):
    expenses = db.query(models.Expense)\
        .filter(models.Expense.user_id == user_id)\
        .all()

    if len(expenses) < 5:
        return

    grouped = defaultdict(list)

    for e in expenses:
        grouped[e.category].append(e)

    for category, items in grouped.items():
        if len(items) < 5:
            continue

        amounts = [e.amount for e in items]
        avg_amt = mean(amounts)

        if max(amounts) - min(amounts) > avg_amt * 0.6:
            continue  # too much variance

        hours = [e.date.hour if hasattr(e.date, "hour") else 12 for e in items]

        start_hour = max(min(hours) - 1, 0)
        end_hour = min(max(hours) + 1, 23)

        confidence = min(len(items) / 10, 1.0)

        existing = db.query(models.ExpensePattern).filter(
            models.ExpensePattern.user_id == user_id,
            models.ExpensePattern.category == category
        ).first()

        if existing:
            existing.avg_amount = avg_amt
            existing.min_amount = min(amounts)
            existing.max_amount = max(amounts)
            existing.preferred_hour_start = start_hour
            existing.preferred_hour_end = end_hour
            existing.confidence = confidence
        else:
            pattern = models.ExpensePattern(
                user_id=user_id,
                category=category,
                avg_amount=avg_amt,
                min_amount=min(amounts),
                max_amount=max(amounts),
                preferred_hour_start=start_hour,
                preferred_hour_end=end_hour,
                frequency="daily",
                confidence=confidence
            )
            db.add(pattern)

    db.commit()
