from fastapi import APIRouter
from app.api.v1.endpoints import transactions, analytics, subscriptions, accounts, goals, paycheck, auth, onboarding, bot_webhook, categories, jago_pockets
from app.api.v1.endpoints import backup, search

api_router = APIRouter()
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(backup.router, prefix="/backup", tags=["backup"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
api_router.include_router(paycheck.router, prefix="/paycheck", tags=["paycheck"])
api_router.include_router(bot_webhook.router, prefix="/bot", tags=["bot"])
api_router.include_router(jago_pockets.router, prefix="/jago-pockets", tags=["jago-pockets"])
api_router.include_router(jago_pockets.router, prefix="/pockets", tags=["pockets"])
