from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import traders, smart_universe, signals, risk, backtests, hyperliquid_sync

app = FastAPI()

origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Temporary debugging: print all routes on startup
@app.on_event("startup")
async def print_routes():
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info("--- Registered Routes ---")
    for route in app.router.routes:
        logger.info(f"PATH: {route.path} METHODS: {route.methods}")
    logger.info("-------------------------")

# Routers that don't have prefix defined in their files
app.include_router(traders.router, prefix="/traders", tags=["traders"])
app.include_router(risk.router, prefix="/risk", tags=["risk"])
app.include_router(backtests.router, prefix="/backtests", tags=["backtests"])

# Routers that DO have prefix defined in their files
app.include_router(smart_universe.router)
app.include_router(signals.router)
app.include_router(hyperliquid_sync.router)
