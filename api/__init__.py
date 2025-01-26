"""REST API module for the marketplace.

This module provides HTTP endpoints for:
- Creating and managing listings
- Placing and managing orders
- Checking balances and status
"""

import logging
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

from database import get_pool, init_db, close as db_close
from listings import ListingManager, ListingError, ListingNotFoundError
from orders import OrderManager, OrderError, InsufficientBalanceError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    logger.info("Initializing API...")
    await init_db()
    
    yield
    
    # Shutdown
    logger.info("Shutting down API...")
    await db_close()

# Create FastAPI app
app = FastAPI(
    title="Manticore Trading API",
    description="REST API for the Manticore Trading platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers
    max_age=86400,  # Cache preflight requests for 24 hours
)

# Pydantic models for request/response validation
class PriceSpec(BaseModel):
    """Price specification for a listing asset"""
    asset_name: str = Field(..., description="Name of the asset being sold")
    price_evr: Optional[Decimal] = Field(None, description="Price in EVR")
    price_asset_name: Optional[str] = Field(None, description="Asset name for pricing")
    price_asset_amount: Optional[Decimal] = Field(None, description="Asset amount for pricing")

class CreateListing(BaseModel):
    """Request model for creating a new listing"""
    seller_address: str = Field(..., description="Seller's EVR address")
    name: str = Field(..., description="Name of the listing")
    description: Optional[str] = Field(None, description="Optional listing description")
    image_ipfs_hash: Optional[str] = Field(None, description="Optional IPFS hash for listing image")
    prices: List[PriceSpec] = Field(..., description="List of price specifications")

class OrderItem(BaseModel):
    """Item in an order"""
    asset_name: str = Field(..., description="Name of the asset to order")
    amount: Decimal = Field(..., description="Amount of the asset to order")

class CreateOrder(BaseModel):
    """Request model for creating a new order"""
    buyer_address: str = Field(..., description="Buyer's EVR address")
    items: List[OrderItem] = Field(..., description="List of items to order")

# Dependency for getting managers
async def get_listing_manager():
    """Get a listing manager instance."""
    pool = await get_pool()
    try:
        manager = ListingManager(pool)
        yield manager
    finally:
        # Pool will be cleaned up by lifespan handler
        pass

async def get_order_manager():
    """Get an order manager instance."""
    pool = await get_pool()
    try:
        manager = OrderManager(pool)
        yield manager
    finally:
        # Pool will be cleaned up by lifespan handler
        pass

# Listing endpoints
@app.post("/listings/", tags=["listings"])
async def create_listing(
    listing: CreateListing,
    manager: ListingManager = Depends(get_listing_manager)
) -> dict:
    """Create a new listing."""
    try:
        return await manager.create_listing(
            seller_address=listing.seller_address,
            name=listing.name,
            description=listing.description,
            image_ipfs_hash=listing.image_ipfs_hash,
            prices=[price.dict() for price in listing.prices]
        )
    except ListingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating listing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/listings/{listing_id}", tags=["listings"])
async def get_listing(
    listing_id: UUID,
    manager: ListingManager = Depends(get_listing_manager)
) -> dict:
    """Get a listing by ID."""
    try:
        return await manager.get_listing(listing_id)
    except ListingNotFoundError:
        raise HTTPException(status_code=404, detail="Listing not found")
    except Exception as e:
        logger.error(f"Error getting listing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/listings/{listing_id}/balances", tags=["listings"])
async def get_listing_balances(
    listing_id: UUID,
    manager: ListingManager = Depends(get_listing_manager)
) -> dict:
    """Get balances for a listing."""
    try:
        return await manager.get_balances(listing_id)
    except ListingNotFoundError:
        raise HTTPException(status_code=404, detail="Listing not found")
    except Exception as e:
        logger.error(f"Error getting listing balances: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/listings/", tags=["listings"])
async def search_listings(
    search_term: Optional[str] = Query(None, description="Text to search in name and description"),
    seller_address: Optional[str] = Query(None, description="Filter by seller address"),
    asset_name: Optional[str] = Query(None, description="Filter by asset name"),
    min_price_evr: Optional[Decimal] = Query(None, description="Minimum EVR price"),
    max_price_evr: Optional[Decimal] = Query(None, description="Maximum EVR price"),
    status: Optional[str] = Query(None, description="Filter by listing status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    manager: ListingManager = Depends(get_listing_manager)
) -> List[dict]:
    """Search listings with various filters."""
    try:
        logger.info(
            "Searching listings with params: search=%r, seller=%r, asset=%r, price_range=%r-%r, status=%r, limit=%d, offset=%d",
            search_term, seller_address, asset_name, min_price_evr, max_price_evr, status, limit, offset
        )
        results = await manager.search_listings(
            search_term=search_term,
            seller_address=seller_address,
            asset_name=asset_name,
            min_price_evr=min_price_evr,
            max_price_evr=max_price_evr,
            status=status,
            limit=limit,
            offset=offset
        )
        logger.info("Search returned %d results", len(results))
        return results
    except Exception as e:
        logger.exception("Error searching listings: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Order endpoints
@app.post("/listings/{listing_id}/orders/", tags=["orders"])
async def create_order(
    listing_id: UUID,
    order: CreateOrder,
    manager: OrderManager = Depends(get_order_manager)
) -> dict:
    """Create a new order for a listing."""
    try:
        return await manager.create_order(
            listing_id=listing_id,
            buyer_address=order.buyer_address,
            items=[item.dict() for item in order.items]
        )
    except ListingNotFoundError:
        raise HTTPException(status_code=404, detail="Listing not found")
    except InsufficientBalanceError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance for {e.asset_name}: have {e.available}, need {e.requested}"
        )
    except OrderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/orders/{order_id}", tags=["orders"])
async def get_order(
    order_id: UUID,
    manager: OrderManager = Depends(get_order_manager)
) -> dict:
    """Get an order by ID."""
    try:
        order = await manager.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order
    except Exception as e:
        logger.error(f"Error getting order: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/orders/{order_id}/balances", tags=["orders"])
async def get_order_balances(
    order_id: UUID,
    manager: OrderManager = Depends(get_order_manager)
) -> dict:
    """Get balances for an order."""
    try:
        return await manager.get_order_balances(order_id)
    except OrderError:
        raise HTTPException(status_code=404, detail="Order not found")
    except Exception as e:
        logger.error(f"Error getting order balances: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 