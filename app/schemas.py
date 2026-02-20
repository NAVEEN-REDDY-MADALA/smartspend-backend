from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ---------- USERS ----------
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ---------- INCOME ----------
class IncomeCreate(BaseModel):
    amount: float
    source: str
    date: datetime


class IncomeUpdate(BaseModel):
    amount: Optional[float] = None
    source: Optional[str] = None
    date: Optional[datetime] = None


# ---------- EXPENSE ----------
class ExpenseCreate(BaseModel):
    amount: float
    category: str
    merchant: Optional[str] = None   # ← NEW
    date: datetime


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = None
    category: Optional[str] = None
    merchant: Optional[str] = None   # ← NEW
    date: Optional[datetime] = None


class AutoExpenseCreate(BaseModel):
    amount: int
    category: Optional[str] = "Other"
    merchant: Optional[str] = None   # ← NEW
    date: Optional[datetime] = None


class ExpenseOut(BaseModel):
    id: int
    user_id: int
    amount: float
    category: str
    merchant: Optional[str] = None   # ← NEW
    date: datetime
    is_auto: bool

    class Config:
        from_attributes = True


# ---------- GOALS ----------
class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    target_amount: float
    target_date: Optional[datetime] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_amount: Optional[float] = None
    current_amount: Optional[float] = None
    target_date: Optional[datetime] = None
    status: Optional[str] = None


# ---------- DETECTED TRANSACTIONS ----------
class DetectedTransactionCreate(BaseModel):
    amount: float
    transaction_type: str
    merchant: Optional[str] = None
    category_guess: Optional[str] = None
    transaction_date: datetime
    sms_hash: Optional[str] = None
    account_number: Optional[str] = None
    reference_number: Optional[str] = None


class DetectedTransactionUpdate(BaseModel):
    category: Optional[str] = None
    amount: Optional[float] = None
    merchant: Optional[str] = None
    status: Optional[str] = None


# ---------- REMINDERS ----------
class RecurringReminderCreate(BaseModel):
    name: str
    amount: float
    category: Optional[str] = "Bills"
    day_of_month: int
    frequency: Optional[str] = "monthly"
    notify_7_days: Optional[bool] = True
    notify_3_days: Optional[bool] = False
    notify_1_day: Optional[bool] = True
    notify_same_day: Optional[bool] = True
    auto_pay: Optional[bool] = False


class RecurringReminderUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    day_of_month: Optional[int] = None
    notify_7_days: Optional[bool] = None
    notify_3_days: Optional[bool] = None
    notify_1_day: Optional[bool] = None
    notify_same_day: Optional[bool] = None
    is_active: Optional[bool] = None
    auto_pay: Optional[bool] = None


class RecurringReminderOut(BaseModel):
    id: int
    user_id: int
    name: str
    amount: float
    category: str
    day_of_month: int
    frequency: str
    notify_7_days: bool
    notify_3_days: bool
    notify_1_day: bool
    notify_same_day: bool
    is_active: bool
    auto_pay: bool
    next_payment_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True