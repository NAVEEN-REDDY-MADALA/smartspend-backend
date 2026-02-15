"""
ML Service for SmartSpend AI Insights
Implements real machine learning models for financial predictions
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from statistics import mean, stdev
from collections import defaultdict

from app import models


class MLService:
    """Core ML service for expense forecasting and insights"""
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.expenses = self._load_expenses()
        self.budgets = self._load_budgets()
    
    def _load_expenses(self) -> List[models.Expense]:
        """Load all expenses for the user"""
        return (
            self.db.query(models.Expense)
            .filter(models.Expense.user_id == self.user_id)
            .order_by(models.Expense.date.asc())
            .all()
        )
    
    def _load_budgets(self) -> Dict[str, float]:
        """Load budgets from database (or return empty dict if not implemented)"""
        # For now, return empty dict - budgets are in localStorage
        # TODO: Implement Budget model when migrating to database
        return {}
    
    def _engineer_features(self) -> pd.DataFrame:
        """Engineer features from expense data"""
        if len(self.expenses) < 3:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            "date": e.date,
            "amount": e.amount,
            "category": e.category
        } for e in self.expenses])
        
        df["date"] = pd.to_datetime(df["date"])
        
        # Monthly aggregation
        df["year_month"] = df["date"].dt.to_period("M")
        monthly = df.groupby("year_month").agg({
            "amount": "sum",
            "category": lambda x: x.nunique(),  # unique categories
        }).reset_index()
        monthly.columns = ["month", "total_spend", "category_count"]
        
        # Time features
        monthly["month_index"] = np.arange(len(monthly))
        
        # Trend features
        if len(monthly) > 1:
            monthly["spend_change"] = monthly["total_spend"].diff()
            monthly["spend_pct_change"] = monthly["total_spend"].pct_change() * 100
        else:
            monthly["spend_change"] = 0
            monthly["spend_pct_change"] = 0
        
        # Volatility (rolling std)
        if len(monthly) >= 3:
            monthly["volatility"] = monthly["total_spend"].rolling(window=3, min_periods=1).std()
        else:
            monthly["volatility"] = monthly["total_spend"].std() if len(monthly) > 1 else 0
        
        # Category-wise features
        category_monthly = df.groupby(["year_month", "category"])["amount"].sum().reset_index()
        category_monthly.columns = ["month", "category", "category_spend"]
        
        # Day-of-week patterns
        df["day_of_week"] = df["date"].dt.dayofweek
        weekday_spend = df.groupby("day_of_week")["amount"].mean()
        monthly["avg_weekday_spend"] = weekday_spend.mean() if len(weekday_spend) > 0 else 0
        
        # Frequency (transactions per month)
        monthly["transaction_count"] = df.groupby("year_month").size().values
        
        return monthly
    
    def forecast_next_month(self) -> Dict:
        """
        Predict next month's total spending using ML models
        Returns: {predicted_amount, confidence, trend}
        """
        monthly = self._engineer_features()
        
        if len(monthly) < 3:
            return {
                "predicted_amount": 0,
                "confidence": 0.0,
                "trend": "STABLE",
                "message": "Insufficient data (need at least 3 months)"
            }
        
        # Prepare features
        X = monthly[["month_index", "total_spend", "spend_change", "volatility", "transaction_count"]].fillna(0)
        y = monthly["total_spend"].values
        
        # Train multiple models and ensemble
        models_list = []
        predictions = []
        
        # Linear Regression
        lr = LinearRegression()
        lr.fit(X[:-1], y[:-1])  # Leave last month for validation
        lr_pred = lr.predict(X.iloc[[-1]].values)[0]
        models_list.append(("LinearRegression", lr, lr_pred))
        predictions.append(lr_pred)
        
        # Random Forest (if enough data)
        if len(monthly) >= 5:
            rf = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=3)
            rf.fit(X[:-1], y[:-1])
            rf_pred = rf.predict(X.iloc[[-1]].values)[0]
            models_list.append(("RandomForest", rf, rf_pred))
            predictions.append(rf_pred)
        
        # Weighted ensemble (more weight to RF if available)
        if len(predictions) == 2:
            predicted_amount = 0.4 * predictions[0] + 0.6 * predictions[1]
        else:
            predicted_amount = predictions[0]
        
        # Calculate confidence based on data quality and model agreement
        if len(predictions) == 2:
            agreement = 1 - abs(predictions[0] - predictions[1]) / (max(predictions) + 1)
            confidence = min(0.95, max(0.3, agreement * (len(monthly) / 12)))
        else:
            confidence = min(0.85, max(0.3, len(monthly) / 12))
        
        # Determine trend
        if len(monthly) >= 2:
            recent_trend = monthly["spend_change"].iloc[-1]
            if recent_trend > monthly["total_spend"].iloc[-2] * 0.05:  # >5% increase
                trend = "UP"
            elif recent_trend < -monthly["total_spend"].iloc[-2] * 0.05:  # >5% decrease
                trend = "DOWN"
            else:
                trend = "STABLE"
        else:
            trend = "STABLE"
        
        return {
            "predicted_amount": round(float(max(0, predicted_amount)), 2),
            "confidence": round(float(confidence), 2),
            "trend": trend
        }
    
    def detect_budget_risks(self) -> List[Dict]:
        """
        Compare ML predictions vs budgets to detect risks
        Returns: List of risk assessments per category
        """
        if len(self.expenses) < 3:
            return []
        
        # Get category-wise predictions
        df = pd.DataFrame([{
            "date": e.date,
            "amount": e.amount,
            "category": e.category
        } for e in self.expenses])
        
        df["date"] = pd.to_datetime(df["date"])
        df["year_month"] = df["date"].dt.to_period("M")
        
        # Monthly category spending
        category_monthly = df.groupby(["year_month", "category"])["amount"].sum().reset_index()
        category_monthly.columns = ["month", "category", "spend"]
        
        risks = []
        
        # For each category with budget, predict next month
        categories = category_monthly["category"].unique()
        
        for category in categories:
            cat_data = category_monthly[category_monthly["category"] == category]
            
            if len(cat_data) < 2:
                continue
            
            # Simple trend-based prediction for category
            recent_avg = cat_data["spend"].tail(3).mean()
            trend = cat_data["spend"].tail(2).diff().iloc[-1] if len(cat_data) >= 2 else 0
            predicted = max(0, recent_avg + (trend * 0.5))
            
            # Get budget limit (from localStorage for now - would be from DB)
            # For demo, we'll use a default or calculate from recent spending
            budget_limit = recent_avg * 1.2  # Default 20% buffer
            
            # Calculate risk
            if budget_limit > 0:
                probability = min(1.0, predicted / budget_limit)
                
                if probability >= 0.9:
                    risk_level = "HIGH"
                elif probability >= 0.7:
                    risk_level = "MEDIUM"
                else:
                    risk_level = "LOW"
                
                risks.append({
                    "category": category,
                    "risk_level": risk_level,
                    "probability": round(float(probability), 2),
                    "expected_spend": round(float(predicted), 2),
                    "budget_limit": round(float(budget_limit), 2)
                })
        
        return sorted(risks, key=lambda x: x["probability"], reverse=True)
    
    def detect_overspending_patterns(self) -> List[Dict]:
        """
        Detect anomalies: spikes, rapid growth, category explosions
        Returns: List of detected patterns
        """
        if len(self.expenses) < 4:
            return []
        
        df = pd.DataFrame([{
            "date": e.date,
            "amount": e.amount,
            "category": e.category
        } for e in self.expenses])
        
        df["date"] = pd.to_datetime(df["date"])
        df["year_month"] = df["date"].dt.to_period("M")
        
        insights = []
        
        # Monthly totals
        monthly = df.groupby("year_month")["amount"].sum().reset_index()
        monthly.columns = ["month", "total"]
        
        if len(monthly) >= 2:
            # Detect spikes
            recent = monthly["total"].iloc[-1]
            previous = monthly["total"].iloc[-2]
            
            if recent > previous * 1.4:  # 40% increase
                pct_increase = ((recent - previous) / previous) * 100
                insights.append({
                    "type": "SPIKE",
                    "category": "Overall",
                    "message": f"Overall spending increased by {pct_increase:.0f}% compared to last month.",
                    "severity": "HIGH" if pct_increase > 50 else "MEDIUM"
                })
            
            # Category-wise spikes
            category_monthly = df.groupby(["year_month", "category"])["amount"].sum().reset_index()
            category_monthly.columns = ["month", "category", "spend"]
            
            for category in category_monthly["category"].unique():
                cat_data = category_monthly[category_monthly["category"] == category]
                if len(cat_data) >= 2:
                    recent_cat = cat_data["spend"].iloc[-1]
                    prev_cat = cat_data["spend"].iloc[-2]
                    
                    if prev_cat > 0 and recent_cat > prev_cat * 1.3:  # 30% increase
                        pct = ((recent_cat - prev_cat) / prev_cat) * 100
                        insights.append({
                            "type": "SPIKE",
                            "category": category,
                            "message": f"{category} spending increased by {pct:.0f}% compared to last month.",
                            "severity": "HIGH" if pct > 50 else "MEDIUM"
                        })
        
        # Rapid growth detection (3+ months)
        if len(monthly) >= 3:
            growth_rate = (monthly["total"].iloc[-1] / monthly["total"].iloc[-3]) - 1
            if growth_rate > 0.3:  # 30% growth over 3 months
                insights.append({
                    "type": "RAPID_GROWTH",
                    "category": "Overall",
                    "message": f"Spending has grown by {growth_rate*100:.0f}% over the last 3 months.",
                    "severity": "HIGH"
                })
        
        return insights
    
    def generate_recommendations(self) -> List[Dict]:
        """
        Generate actionable recommendations based on ML insights
        """
        recommendations = []
        
        # Get forecast
        forecast = self.forecast_next_month()
        
        # Get risks
        risks = self.detect_budget_risks()
        
        # Get patterns
        patterns = self.detect_overspending_patterns()
        
        # Recommendation 1: Based on forecast vs current
        if forecast["predicted_amount"] > 0 and len(self.expenses) > 0:
            recent_expenses = [e.amount for e in self.expenses[-30:]]
            current_avg = mean(recent_expenses) if recent_expenses else 0
            if current_avg > 0 and forecast["predicted_amount"] > current_avg * 1.2:
                diff = forecast["predicted_amount"] - current_avg
                recommendations.append({
                    "suggestion": f"Expected spending increase of ₹{diff:.0f} next month. Consider reviewing discretionary expenses.",
                    "priority": "HIGH"
                })
        
        # Recommendation 2: Based on high-risk categories
        high_risk = [r for r in risks if r["risk_level"] == "HIGH"]
        for risk in high_risk[:2]:  # Top 2
            reduction = risk["expected_spend"] - risk["budget_limit"]
            if reduction > 0:
                recommendations.append({
                    "suggestion": f"Reduce {risk['category']} expenses by ₹{reduction:.0f} to stay within your monthly budget.",
                    "priority": "HIGH"
                })
        
        # Recommendation 3: Based on patterns
        for pattern in patterns[:2]:  # Top 2 patterns
            if pattern["type"] == "SPIKE":
                recommendations.append({
                    "suggestion": f"Monitor {pattern['category']} spending - significant increase detected.",
                    "priority": pattern["severity"]
                })
        
        # Default recommendation if none
        if not recommendations:
            recommendations.append({
                "suggestion": "Your spending patterns look healthy. Keep tracking your expenses!",
                "priority": "LOW"
            })
        
        return recommendations
    
    def explain_predictions(self) -> Dict:
        """
        Provide explainable AI - WHY predictions were made
        """
        reasons = []
        
        monthly = self._engineer_features()
        
        if len(monthly) < 2:
            return {
                "reasons": ["Insufficient historical data for detailed analysis."]
            }
        
        # Reason 1: Trend analysis
        if len(monthly) >= 3:
            recent_trend = monthly["spend_change"].tail(3).mean()
            if recent_trend > 0:
                months_increasing = sum(monthly["spend_change"].tail(3) > 0)
                if months_increasing >= 2:
                    reasons.append(f"Spending has increased for {months_increasing} consecutive months")
            elif recent_trend < 0:
                reasons.append("Spending trend is decreasing")
            else:
                reasons.append("Spending trend is stable")
        
        # Reason 2: Weekend vs weekday
        df = pd.DataFrame([{
            "date": e.date,
            "amount": e.amount
        } for e in self.expenses])
        df["date"] = pd.to_datetime(df["date"])
        df["day_of_week"] = df["date"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"].isin([5, 6])
        
        weekend_avg = df[df["is_weekend"]]["amount"].mean() if len(df[df["is_weekend"]]) > 0 else 0
        weekday_avg = df[~df["is_weekend"]]["amount"].mean() if len(df[~df["is_weekend"]]) > 0 else 0
        
        if weekend_avg > 0 and weekday_avg > 0:
            pct_diff = ((weekend_avg - weekday_avg) / weekday_avg) * 100
            if abs(pct_diff) > 20:
                if pct_diff > 0:
                    reasons.append(f"Weekend expenses are {pct_diff:.0f}% higher than weekdays")
                else:
                    reasons.append(f"Weekday expenses are {abs(pct_diff):.0f}% higher than weekends")
        
        # Reason 3: Volatility
        if len(monthly) >= 3:
            volatility = monthly["volatility"].iloc[-1]
            avg_spend = monthly["total_spend"].mean()
            if volatility > avg_spend * 0.3:
                reasons.append("High spending volatility detected - expenses vary significantly month-to-month")
        
        # Reason 4: Category patterns
        category_totals = defaultdict(float)
        for e in self.expenses:
            category_totals[e.category] += e.amount
        
        if category_totals:
            top_category = max(category_totals.items(), key=lambda x: x[1])
            total = sum(category_totals.values())
            pct = (top_category[1] / total) * 100
            if pct > 40:
                reasons.append(f"{top_category[0]} accounts for {pct:.0f}% of total spending")
        
        if not reasons:
            reasons.append("Analysis based on historical spending patterns and trends")
        
        return {"reasons": reasons}
    
    def generate_alerts(self) -> List[Dict]:
        """
        Generate automated alerts based on ML predictions
        """
        alerts = []
        
        # Alert 1: Budget risks
        risks = self.detect_budget_risks()
        for risk in risks:
            if risk["risk_level"] == "HIGH":
                alerts.append({
                    "alert_type": "BUDGET_RISK",
                    "severity": "HIGH",
                    "message": f"{risk['category']} budget likely to exceed next month (expected: ₹{risk['expected_spend']:.0f})",
                    "category": risk["category"]
                })
        
        # Alert 2: Forecast exceeds current spending significantly
        forecast = self.forecast_next_month()
        if forecast["predicted_amount"] > 0 and len(self.expenses) > 0:
            recent_expenses = [e.amount for e in self.expenses[-30:]]
            recent_avg = mean(recent_expenses) if recent_expenses else 0
            if recent_avg > 0 and forecast["predicted_amount"] > recent_avg * 1.3:
                alerts.append({
                    "alert_type": "FORECAST_EXCEED",
                    "severity": "MEDIUM",
                    "message": f"Next month's predicted spending (₹{forecast['predicted_amount']:.0f}) is significantly higher than recent average",
                    "category": "Overall"
                })
        
        # Alert 3: Abnormal spending patterns
        patterns = self.detect_overspending_patterns()
        for pattern in patterns:
            if pattern["severity"] == "HIGH":
                alerts.append({
                    "alert_type": "ABNORMAL_SPENDING",
                    "severity": "HIGH",
                    "message": pattern["message"],
                    "category": pattern["category"]
                })
        
        return alerts

