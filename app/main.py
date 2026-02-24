from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models
from app.database import engine
from app.routes_auth import router as auth_router
from app.routes_income import router as income_router
from app.routes_expense import router as expense_router
from app.routes_suggestions import router as suggestions_router
from app.routes_goals import router as goals_router
from app.routes_summary import router as summary_router
from app.routes_detected import router as detected_router
from app.predict import router as predict_router
from app.routes_reminders import router as reminders_router

# ✅ NEW: Import forgot password router
from app.routes_password import router as password_router  # ← ADD THIS


models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartSpend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ ALL ROUTES UNDER /api
app.include_router(auth_router,        prefix="/api")
app.include_router(income_router,      prefix="/api")
app.include_router(expense_router,     prefix="/api")
app.include_router(suggestions_router, prefix="/api")
app.include_router(goals_router,       prefix="/api")
app.include_router(summary_router,     prefix="/api")
app.include_router(detected_router)
app.include_router(predict_router,     prefix="/api/ai")
app.include_router(reminders_router,   prefix="/api")

# ✅ NEW: Forgot/Reset password routes
app.include_router(password_router, prefix="/api")  # ← ADD THIS


@app.get("/")
def root():
    return {"message": "SmartSpend API running 🚀"}