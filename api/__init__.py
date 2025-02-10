"""REST API module for the marketplace.

This module provides HTTP endpoints for:
- Creating and managing listings
- Placing and managing orders
- Checking balances and status
- Real-time updates via WebSocket
- Market analytics and trends
- System health monitoring
- Notifications and alerts
- Authentication and session management
"""

import logging
from decimal import Decimal, DecimalException
from typing import List, Optional, Dict, Any
from uuid import UUID
import json
import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, Query, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field, validator
from contextlib import asynccontextmanager

from database import get_pool, init_db, close as db_close
from listings import ListingManager, ListingError, ListingNotFoundError
from orders import OrderManager, OrderError, InsufficientBalanceError, ORDER_EXPIRATION_MINUTES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Background task for order expiration
async def expire_orders_task():
    """Background task to expire pending orders."""
    manager = OrderManager()
    while True:
        try:
            # Run expiration check every minute
            await asyncio.sleep(60)
            expired_count = await manager.expire_pending_orders()
            if expired_count > 0:
                logger.info(f"Expired {expired_count} pending orders")
        except Exception as e:
            logger.error(f"Error in order expiration task: {e}")
            # Don't let the task die, wait and retry
            await asyncio.sleep(60)

# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    logger.info("Initializing API...")
    # Don't initialize DB here since it's handled in __main__.py
    
    # Start order expiration task
    expiration_task = asyncio.create_task(expire_orders_task())
    logger.info(f"Started order expiration task (expires after {ORDER_EXPIRATION_MINUTES} minutes)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down API...")
    expiration_task.cancel()
    try:
        await expiration_task
    except asyncio.CancelledError:
        pass
    # Don't close DB here since it's handled in __main__.py

# Create FastAPI app
app = FastAPI(
    title="Manticore Trading API",
    description="REST API for the Manticore Trading platform",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint - register this BEFORE other routers
@app.get("/")
async def root():
    """Root endpoint returning API documentation."""
    try:
        with open("api/index.html", "r") as f:
            content = f.read()
        return HTMLResponse(
            content=content,
            status_code=200,
            media_type="text/html"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Documentation not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading documentation: {str(e)}"
        )

# Import and include all routers
from .listings import router as listings_router
from .orders import router as orders_router
from .websockets import router as websocket_router
from .market import router as market_router
from .system import router as system_router
from .notifications import router as notifications_router
from .auth import router as auth_router
from .profile import router as profile_router
from .chat import router as chat_router
from .listings.featured import router as featured_router

# Include all routers
app.include_router(listings_router)
app.include_router(orders_router)
app.include_router(websocket_router)
app.include_router(market_router)
app.include_router(system_router)
app.include_router(notifications_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(chat_router)
app.include_router(featured_router)