from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import schemas, models
from app.database import get_db
from app.auth import get_current_user   


router = APIRouter(prefix="/income", tags=["income"])


@router.post("/")
def add_income(
    income: schemas.IncomeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    new_income = models.Income(
        user_id=current_user.id,
        amount=income.amount,
        source=income.source,
        date=income.date
    )
    db.add(new_income)
    db.commit()
    db.refresh(new_income)
    return new_income


@router.get("/")
def get_income(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Income).filter(
        models.Income.user_id == current_user.id
    ).all()
@router.delete("/{income_id}")
def delete_income(income_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    income = db.query(models.Income).filter(models.Income.id == income_id, models.Income.user_id == current_user.id).first()

    if not income:
        raise HTTPException(status_code=404, detail="Income not found")

    db.delete(income)
    db.commit()

    return {"message": "Income deleted"}
@router.put("/{income_id}")
def update_income(
    income_id: int,
    updated: schemas.IncomeUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    income = db.query(models.Income).filter(
        models.Income.id == income_id,
        models.Income.user_id == current_user.id
    ).first()

    if not income:
        raise HTTPException(status_code=404, detail="Income not found")

    if updated.amount is not None:
        income.amount = updated.amount
    if updated.source is not None:
        income.source = updated.source
    if updated.date is not None:
        income.date = updated.date

    db.commit()
    db.refresh(income)
    return income
