from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .auth import router as auth_router
from .listings import router as listings_router
from .profile import router as profile_router
from .chat import router as chat_router
from .market import router as market_router
from .system import router as system_router
from .notifications import router as notifications_router
from .orders import router as orders_router
from .websockets import router as websocket_router

app = FastAPI(
    title="Manticore Trading API",
    description="API for the Manticore Trading platform",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add routes
app.include_router(auth_router)
app.include_router(listings_router)
app.include_router(profile_router)
app.include_router(chat_router)
app.include_router(market_router)
app.include_router(system_router)
app.include_router(notifications_router)
app.include_router(orders_router)
app.include_router(websocket_router)

@app.get("/")
async def root():
    return {
        "name": "Manticore Trading API",
        "version": "1.0.0",
        "status": "running"
    } 