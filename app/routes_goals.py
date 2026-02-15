from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app import schemas, models
from app.database import get_db
from app.auth import get_current_user

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("/")
def create_goal(
    goal: schemas.GoalCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    new_goal = models.Goal(
        user_id=current_user.id,
        title=goal.title,
        description=goal.description,
        target_amount=goal.target_amount,
        target_date=goal.target_date
    )
    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)
    return new_goal


@router.get("/")
def get_goals(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.Goal)
        .filter(models.Goal.user_id == current_user.id)
        .order_by(models.Goal.created_at.desc())
        .all()
    )


@router.get("/{goal_id}")
def get_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    return goal


@router.put("/{goal_id}")
def update_goal(
    goal_id: int,
    updated: schemas.GoalUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    if updated.title is not None:
        goal.title = updated.title
    if updated.description is not None:
        goal.description = updated.description
    if updated.target_amount is not None:
        goal.target_amount = updated.target_amount
    if updated.current_amount is not None:
        goal.current_amount = updated.current_amount
    if updated.target_date is not None:
        goal.target_date = updated.target_date
    if updated.status is not None:
        goal.status = updated.status
    
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}")
def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    db.delete(goal)
    db.commit()
    return {"message": "Goal deleted successfully"}


@router.post("/{goal_id}/add-amount")
def add_amount_to_goal(
    goal_id: int,
    amount: float,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Add amount to goal. This creates an expense entry to deduct from savings.
    """
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Check available savings
    from sqlalchemy import func
    total_income = (
        db.query(func.sum(models.Income.amount))
        .filter(models.Income.user_id == current_user.id)
        .scalar() or 0.0
    )
    total_expenses = (
        db.query(func.sum(models.Expense.amount))
        .filter(models.Expense.user_id == current_user.id)
        .scalar() or 0.0
    )
    available_savings = total_income - total_expenses
    
    if amount > available_savings:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient savings. Available: ₹{available_savings:.2f}, Requested: ₹{amount:.2f}"
        )
    
    # Create expense entry for goal allocation (this deducts from savings)
    goal_expense = models.Expense(
        user_id=current_user.id,
        amount=amount,
        category=f"Goal: {goal.title}",
        date=datetime.utcnow()
    )
    db.add(goal_expense)
    
    # Update goal progress
    goal.current_amount += amount
    
    # Auto-complete if target reached
    if goal.current_amount >= goal.target_amount:
        goal.status = "completed"
        goal.current_amount = goal.target_amount
    
    db.commit()
    db.refresh(goal)
    return goal

