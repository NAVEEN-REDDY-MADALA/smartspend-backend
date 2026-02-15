from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import List

from app import models, schemas
from app.database import get_db
from app.auth import get_current_user
router = APIRouter(prefix="/reminders", tags=["reminders"])

# router = APIRouter(prefix="/reminders", tags=["reminders"])
# @router.get("/")
# def get_reminders():
#     return []


def calculate_next_payment_date(day_of_month: int, frequency: str = "monthly") -> datetime:
    """Calculate the next payment date based on day of month"""
    today = datetime.now()
    
    if frequency == "monthly":
        # Try current month first
        try:
            next_date = datetime(today.year, today.month, day_of_month)
            if next_date <= today:
                # Move to next month
                next_date = next_date + relativedelta(months=1)
        except ValueError:
            # Invalid day for this month (e.g., 31st in February)
            next_date = datetime(today.year, today.month, 1) + relativedelta(months=1)
            next_date = datetime(next_date.year, next_date.month, min(day_of_month, 28))
        
        return next_date
    
    # Add yearly support if needed
    return today + timedelta(days=30)


# Get all reminders
# Get all reminders
@router.get("/", response_model=List[schemas.RecurringReminderOut])
def get_reminders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    print("="*50)
    print("📋 GET REMINDERS REQUEST")
    print(f"User ID: {current_user.id}")
    
    reminders = (
        db.query(models.RecurringReminder)
        .filter(models.RecurringReminder.user_id == current_user.id)
        .filter(models.RecurringReminder.is_active == True)
        .order_by(models.RecurringReminder.day_of_month)
        .all()
    )
    
    print(f"Found {len(reminders)} reminders")
    for r in reminders:
        print(f"  - ID: {r.id}, Name: {r.name}, Amount: {r.amount}, Day: {r.day_of_month}")
    print("="*50)
    
    return reminders

# Get single reminder
@router.get("/{reminder_id}", response_model=schemas.RecurringReminderOut)
def get_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    reminder = db.query(models.RecurringReminder).filter(
        models.RecurringReminder.id == reminder_id,
        models.RecurringReminder.user_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    return reminder


# Create reminder
@router.post("/", response_model=schemas.RecurringReminderOut)
def create_reminder(
    reminder: schemas.RecurringReminderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Validate day of month
    if reminder.day_of_month < 1 or reminder.day_of_month > 31:
        raise HTTPException(status_code=400, detail="Day must be between 1 and 31")
    
    # Calculate next payment date
    next_payment = calculate_next_payment_date(reminder.day_of_month, reminder.frequency)
    
    new_reminder = models.RecurringReminder(
        user_id=current_user.id,
        name=reminder.name,
        amount=reminder.amount,
        category=reminder.category,
        day_of_month=reminder.day_of_month,
        frequency=reminder.frequency,
        notify_7_days=reminder.notify_7_days,
        notify_3_days=reminder.notify_3_days,
        notify_1_day=reminder.notify_1_day,
        notify_same_day=reminder.notify_same_day,
        auto_pay=reminder.auto_pay,
        next_payment_date=next_payment
    )
    
    db.add(new_reminder)
    db.commit()
    db.refresh(new_reminder)
    
    return new_reminder


# Update reminder
@router.put("/{reminder_id}", response_model=schemas.RecurringReminderOut)
def update_reminder(
    reminder_id: int,
    reminder_update: schemas.RecurringReminderUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    reminder = db.query(models.RecurringReminder).filter(
        models.RecurringReminder.id == reminder_id,
        models.RecurringReminder.user_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    # Update fields
    update_data = reminder_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(reminder, field, value)
    
    # Recalculate next payment if day changed
    if reminder_update.day_of_month:
        reminder.next_payment_date = calculate_next_payment_date(
            reminder.day_of_month, 
            reminder.frequency
        )
    
    db.commit()
    db.refresh(reminder)
    
    return reminder


# Delete (deactivate) reminder
@router.delete("/{reminder_id}")
def delete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    reminder = db.query(models.RecurringReminder).filter(
        models.RecurringReminder.id == reminder_id,
        models.RecurringReminder.user_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    # Soft delete
    reminder.is_active = False
    db.commit()
    
    return {"message": "Reminder deleted successfully"}


# Get upcoming reminders (next 30 days)
@router.get("/upcoming/list", response_model=List[schemas.RecurringReminderOut])
def get_upcoming_reminders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    today = datetime.now()
    next_month = today + timedelta(days=30)
    
    reminders = (
        db.query(models.RecurringReminder)
        .filter(models.RecurringReminder.user_id == current_user.id)
        .filter(models.RecurringReminder.is_active == True)
        .filter(models.RecurringReminder.next_payment_date <= next_month)
        .order_by(models.RecurringReminder.next_payment_date)
        .all()
    )
    
    return reminders


# Mark reminder as paid (creates expense and updates next date)
@router.post("/{reminder_id}/mark-paid")
def mark_reminder_paid(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    reminder = db.query(models.RecurringReminder).filter(
        models.RecurringReminder.id == reminder_id,
        models.RecurringReminder.user_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    # Create expense
    new_expense = models.Expense(
        user_id=current_user.id,
        amount=reminder.amount,
        category=reminder.category,
        date=datetime.now(),
        is_auto=False  # Manual confirmation
    )
    
    db.add(new_expense)
    
    # Update next payment date
    if reminder.frequency == "monthly":
        reminder.next_payment_date = reminder.next_payment_date + relativedelta(months=1)
    
    db.commit()
    
    return {
        "message": "Reminder marked as paid",
        "expense_id": new_expense.id,
        "next_payment_date": reminder.next_payment_date
    }