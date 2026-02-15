"""
Phase 3: AI Insights API Endpoints
Real ML-based financial intelligence endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app import models
from app.services.ml_service import MLService

router = APIRouter()


@router.get("/predict")
def predict_next_month(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Legacy endpoint - kept for backward compatibility
    Use /forecast for enhanced predictions
    """
    ml_service = MLService(db, current_user.id)
    forecast = ml_service.forecast_next_month()
    return {"prediction": forecast.get("predicted_amount", 0)}


@router.get("/forecast")
def forecast_next_month(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Predict next month's total spending using ML models
    
    Returns:
    {
        "predicted_amount": number,
        "confidence": float (0-1),
        "trend": "UP | DOWN | STABLE"
    }
    """
    ml_service = MLService(db, current_user.id)
    return ml_service.forecast_next_month()


@router.get("/risk")
def detect_budget_risks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Compare ML predictions vs budgets to detect risks
    
    Returns:
    [
        {
            "category": "Food",
            "risk_level": "HIGH | MEDIUM | LOW",
            "probability": float (0-1),
            "expected_spend": number,
            "budget_limit": number
        }
    ]
    """
    ml_service = MLService(db, current_user.id)
    risks = ml_service.detect_budget_risks()
    return risks


@router.get("/insights")
def detect_overspending_patterns(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Detect anomalies: spikes, rapid growth, category explosions
    
    Returns:
    [
        {
            "type": "SPIKE | RAPID_GROWTH",
            "category": string,
            "message": string,
            "severity": "HIGH | MEDIUM | LOW"
        }
    ]
    """
    ml_service = MLService(db, current_user.id)
    insights = ml_service.detect_overspending_patterns()
    return insights


@router.get("/recommendations")
def get_smart_recommendations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Generate actionable recommendations based on ML insights
    
    Returns:
    [
        {
            "suggestion": string,
            "priority": "HIGH | MEDIUM | LOW"
        }
    ]
    """
    ml_service = MLService(db, current_user.id)
    recommendations = ml_service.generate_recommendations()
    return recommendations


@router.get("/explain")
def explain_predictions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Provide explainable AI - WHY predictions were made
    
    Returns:
    {
        "reasons": [
            "Reason 1",
            "Reason 2",
            ...
        ]
    }
    """
    ml_service = MLService(db, current_user.id)
    explanation = ml_service.explain_predictions()
    return explanation


@router.get("/alerts")
def generate_alerts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Generate automated alerts based on ML predictions
    
    Returns:
    [
        {
            "alert_type": "BUDGET_RISK | FORECAST_EXCEED | ABNORMAL_SPENDING",
            "severity": "HIGH | MEDIUM | LOW",
            "message": string,
            "category": string
        }
    ]
    """
    ml_service = MLService(db, current_user.id)
    alerts = ml_service.generate_alerts()
    return alerts
