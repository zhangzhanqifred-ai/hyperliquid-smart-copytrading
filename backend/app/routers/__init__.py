from fastapi import APIRouter

from .health import router as health_router
from .traders import router as traders_router
from .smart_universe import router as smart_universe_router
from .signals import router as signals_router
from .risk import router as risk_router
from .backtests import router as backtests_router

api_router = APIRouter()

# Mount all sub-routers here. This keeps main.py clean.
api_router.include_router(health_router)
api_router.include_router(traders_router, prefix="/traders", tags=["traders"])
api_router.include_router(smart_universe_router)
api_router.include_router(signals_router, prefix="/signals", tags=["signals"])
api_router.include_router(risk_router, prefix="/risk", tags=["risk"])
api_router.include_router(backtests_router, prefix="/backtests", tags=["backtests"])


