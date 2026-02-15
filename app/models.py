from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

from sqlalchemy.sql import func



class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

    incomes = relationship("Income", back_populates="user")
    expenses = relationship("Expense", back_populates="user")
    goals = relationship("Goal", back_populates="user")
    detected_transactions = relationship("DetectedTransaction")
    

class Income(Base):
    __tablename__ = "income"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    source = Column(String, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="incomes")
class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)

    is_auto = Column(Boolean, default=False, nullable=False)  # ✅ ADD THIS

    user = relationship("User", back_populates="expenses")
class ExpensePattern(Base):
    __tablename__ = "expense_patterns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    category = Column(String, index=True)

    avg_amount = Column(Float)
    min_amount = Column(Float)
    max_amount = Column(Float)

    preferred_hour_start = Column(Integer)  # 0–23
    preferred_hour_end = Column(Integer)    # 0–23

    frequency = Column(String, default="daily")  # daily / weekly
    confidence = Column(Float, default=0.0)      # 0 → 1

    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
class ExpenseSuggestion(Base):
    __tablename__ = "expense_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    category = Column(String)
    suggested_amount = Column(Float)
    suggested_date = Column(DateTime)

    status = Column(String, default="pending")  
    # pending / confirmed / rejected

    source = Column(String, default="pattern")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(String)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    target_date = Column(DateTime)
    
    status = Column(String, default="active")  # active / completed / paused

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="goals")


class DetectedTransaction(Base):
    __tablename__ = "detected_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    amount = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)  # debit / credit
    merchant = Column(String)  # Zomato, PhonePe, Bank name, etc.
    category_guess = Column(String)  # Auto-detected category
    category = Column(String)  # User-selected or confirmed category
    
    transaction_date = Column(DateTime, nullable=False)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    status = Column(String, default="pending")  # pending / confirmed / ignored
    source = Column(String, default="sms")  # sms / manual
    
    # For duplicate detection
    sms_hash = Column(String, index=True)  # Hash of amount+merchant+date to prevent duplicates
    
    # Additional metadata
    account_number = Column(String)  # Last 4 digits if available
    reference_number = Column(String)  # Transaction reference if available

    user = relationship("User")

class RecurringReminder(Base):
    __tablename__ = "recurring_reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Reminder details
    name = Column(String, nullable=False)  # Netflix, Credit Card EMI, etc.
    amount = Column(Float, nullable=False)
    category = Column(String, default="Bills")
    
    # Recurrence
    day_of_month = Column(Integer, nullable=False)  # 1-31
    frequency = Column(String, default="monthly")  # monthly, yearly
    
    # Notification settings
    notify_7_days = Column(Boolean, default=True)
    notify_3_days = Column(Boolean, default=False)
    notify_1_day = Column(Boolean, default=True)
    notify_same_day = Column(Boolean, default=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    auto_pay = Column(Boolean, default=False)  # If auto-debit is enabled
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_notified = Column(DateTime(timezone=True))
    next_payment_date = Column(DateTime)
    
    user = relationship("User")


class ReminderNotification(Base):
    __tablename__ = "reminder_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    reminder_id = Column(Integer, ForeignKey("recurring_reminders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    scheduled_for = Column(DateTime, nullable=False)
    sent_at = Column(DateTime(timezone=True))
    status = Column(String, default="pending")  # pending, sent, dismissed
    
    reminder = relationship("RecurringReminder")
    user = relationship("User")