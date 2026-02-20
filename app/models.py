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
    merchant = Column(String, nullable=True)   # ← NEW: merchant/shop name
    date = Column(DateTime, default=datetime.utcnow)
    is_auto = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="expenses")


class ExpensePattern(Base):
    __tablename__ = "expense_patterns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    category = Column(String, index=True)

    avg_amount = Column(Float)
    min_amount = Column(Float)
    max_amount = Column(Float)

    preferred_hour_start = Column(Integer)
    preferred_hour_end = Column(Integer)

    frequency = Column(String, default="daily")
    confidence = Column(Float, default=0.0)

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
    
    status = Column(String, default="active")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="goals")


class DetectedTransaction(Base):
    __tablename__ = "detected_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    amount = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)
    merchant = Column(String)
    category_guess = Column(String)
    category = Column(String)
    
    transaction_date = Column(DateTime, nullable=False)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    status = Column(String, default="pending")
    source = Column(String, default="sms")
    
    sms_hash = Column(String, index=True)
    account_number = Column(String)
    reference_number = Column(String)

    user = relationship("User")


class RecurringReminder(Base):
    __tablename__ = "recurring_reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, default="Bills")
    
    day_of_month = Column(Integer, nullable=False)
    frequency = Column(String, default="monthly")
    
    notify_7_days = Column(Boolean, default=True)
    notify_3_days = Column(Boolean, default=False)
    notify_1_day = Column(Boolean, default=True)
    notify_same_day = Column(Boolean, default=True)
    
    is_active = Column(Boolean, default=True)
    auto_pay = Column(Boolean, default=False)
    
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
    status = Column(String, default="pending")
    
    reminder = relationship("RecurringReminder")
    user = relationship("User")