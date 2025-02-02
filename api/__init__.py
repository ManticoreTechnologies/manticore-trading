"""REST API module for the marketplace.

This module provides HTTP endpoints for:
- Creating and managing listings
- Placing and managing orders
- Checking balances and status
"""

import logging
from decimal import Decimal, DecimalException
from typing import List, Optional
from uuid import UUID
import json
import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, Query, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
    await init_db()
    
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
    await db_close()

# Create FastAPI app
app = FastAPI(
    title="Manticore Trading API",
    description="REST API for the Manticore Trading platform",
    version="1.0.0",
    lifespan=lifespan
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """Handle validation errors and return detailed error messages."""
    # Log the raw request body
    body = None
    if hasattr(request, 'body'):
        try:
            raw_body = await request.body()
            body = raw_body.decode()
            logger.error(f"Validation failed for request body: {body}")
        except Exception as e:
            logger.error(f"Could not decode request body: {e}")
    
    errors = []
    for error in exc.errors():
        error_msg = {
            "field": " -> ".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        }
        logger.error(f"Validation error: {error_msg}")
        errors.append(error_msg)
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": errors
        }
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
    ipfs_hash: Optional[str] = Field(None, description="Optional IPFS hash for price-specific content")
    
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

    @validator('amount')
    def validate_amount(cls, v):
        """Convert string amounts to Decimal and validate."""
        if isinstance(v, str):
            try:
                v = Decimal(v)
            except (TypeError, ValueError, DecimalException):
                raise ValueError("Invalid amount format")
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

class CreateOrder(BaseModel):
    """Request model for creating a new order"""
    buyer_address: str = Field(..., description="Buyer's EVR address")
    items: List[OrderItem] = Field(..., description="List of items to order")

class UpdateListing(BaseModel):
    """Request model for updating a listing"""
    name: Optional[str] = Field(None, description="New name for the listing")
    description: Optional[str] = Field(None, description="New description for the listing")
    image_ipfs_hash: Optional[str] = Field(None, description="New IPFS hash for the listing image")
    prices: Optional[dict] = Field(None, description="New prices for the listing")

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
    logger.info(f"Received create listing request with data: {listing.dict()}")
    try:
        return await manager.create_listing(
            seller_address=listing.seller_address,
            name=listing.name,
            description=listing.description,
            image_ipfs_hash=listing.image_ipfs_hash,
            prices=[price.dict() for price in listing.prices]
        )
    except ListingError as e:
        logger.error(f"ListingError: {str(e)}")
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
    logger.info(
        "Searching listings with params: search=%r, seller=%r, asset=%r, price_range=%r-%r, status=%r, limit=%d, offset=%d",
        search_term, seller_address, asset_name, min_price_evr, max_price_evr, status, limit, offset
    )
    try:
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

@app.patch("/listings/{listing_id}", tags=["listings"])
async def update_listing(
    listing_id: UUID,
    updates: UpdateListing,
    manager: ListingManager = Depends(get_listing_manager)
) -> dict:
    """Update a listing's mutable fields and prices."""
    logger.info(f"Updating listing {listing_id} with data: {updates}")
    try:
        # Convert Pydantic model to dict and remove None values
        update_data = {k: v for k, v in updates.dict().items() if v is not None}
        
        # Handle prices separately from listing fields
        prices = update_data.pop('prices', None)
        
        # Update the listing fields first (if any)
        result = None
        if update_data:
            result = await manager.update_listing(listing_id, update_data)
            
        # Handle price updates if provided
        if prices is not None:
            # If prices was provided as a list (old format), convert to new format
            if isinstance(prices, list):
                prices = {'add_or_update': prices, 'remove': []}
            
            result = await manager.update_listing_prices(
                listing_id=listing_id,
                add_or_update_prices=prices.get('add_or_update', []),
                remove_asset_names=prices.get('remove', [])
            )
        elif result is None:
            # If no updates were made, just return current listing
            result = await manager.get_listing(listing_id)
            
        return result
    except ListingNotFoundError:
        raise HTTPException(status_code=404, detail="Listing not found")
    except ListingError as e:
        logger.error(f"ListingError: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating listing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/listings/{listing_id}", tags=["listings"])
async def delete_listing(
    listing_id: UUID,
    manager: ListingManager = Depends(get_listing_manager)
) -> dict:
    """Delete a listing."""
    logger.info(f"Deleting listing {listing_id}")
    try:
        await manager.delete_listing(listing_id)
        return {"status": "success", "message": f"Listing {listing_id} deleted"}
    except ListingNotFoundError:
        raise HTTPException(status_code=404, detail="Listing not found")
    except Exception as e:
        logger.error(f"Error deleting listing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/listings/{listing_id}/deposit-address", tags=["listings"])
async def get_listing_deposit_address(
    listing_id: UUID,
    manager: ListingManager = Depends(get_listing_manager)
) -> dict:
    """Get the deposit address for a listing."""
    logger.info(f"Getting deposit address for listing {listing_id}")
    try:
        address = await manager.get_deposit_address(listing_id)
        return {"listing_id": listing_id, "deposit_address": address}
    except ListingNotFoundError:
        raise HTTPException(status_code=404, detail="Listing not found")
    except Exception as e:
        logger.error(f"Error getting deposit address: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/listings/by-deposit/{deposit_address}", tags=["listings"])
async def get_listing_by_deposit(
    deposit_address: str,
    manager: ListingManager = Depends(get_listing_manager)
) -> dict:
    """Get a listing by its deposit address."""
    logger.info(f"Looking up listing by deposit address {deposit_address}")
    try:
        return await manager.get_listing_by_deposit_address(deposit_address)
    except ListingNotFoundError:
        raise HTTPException(status_code=404, detail="No listing found for this deposit address")
    except Exception as e:
        logger.error(f"Error looking up listing by deposit: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/listings/{listing_id}/prices", tags=["listings"])
async def get_price_history(
    listing_id: UUID,
    asset: Optional[str] = Query(None, description="Filter by specific asset name"),
    range: str = Query('1M', description="Time range (1D, 1W, 1M, 3M, 1Y, ALL)"),
    manager: ListingManager = Depends(get_listing_manager)
) -> List[dict]:
    """Get price history for a listing or specific asset."""
    try:
        # Convert time range to interval
        interval = {
            '1D': 'interval \'1 day\'',
            '1W': 'interval \'7 days\'',
            '1M': 'interval \'30 days\'',
            '3M': 'interval \'90 days\'',
            '1Y': 'interval \'365 days\'',
            'ALL': None
        }.get(range.upper())

        async with manager.pool.acquire() as conn:
            # Build time range condition
            time_condition = ''
            if interval:
                time_condition = f'AND sale_time > (now() - {interval})'

            # Build asset condition
            asset_condition = ''
            if asset:
                asset_condition = 'AND asset_name = $2'

            # Get price history with hourly aggregation for recent data,
            # daily for older data to optimize performance
            query = f'''
                WITH time_buckets AS (
                    SELECT
                        CASE
                            WHEN now() - sale_time < interval '7 days' THEN 
                                date_trunc('hour', sale_time)
                            ELSE 
                                date_trunc('day', sale_time)
                        END as bucket_time,
                        asset_name,
                        listing_id,
                        price_evr,
                        amount
                    FROM sale_history
                    WHERE listing_id = $1
                    {asset_condition}
                    {time_condition}
                )
                SELECT
                    bucket_time as time,
                    asset_name,
                    COUNT(*) as num_sales,
                    MIN(price_evr) as min_price,
                    MAX(price_evr) as max_price,
                    AVG(price_evr) as avg_price,
                    SUM(amount) as volume
                FROM time_buckets
                GROUP BY bucket_time, asset_name
                ORDER BY bucket_time ASC
            '''

            params = [listing_id]
            if asset:
                params.append(asset)

            rows = await conn.fetch(query, *params)

            # Format response
            return [{
                'time': row['time'].isoformat(),
                'asset_name': row['asset_name'],
                'num_sales': row['num_sales'],
                'min_price': str(row['min_price']),
                'max_price': str(row['max_price']),
                'avg_price': str(row['avg_price']),
                'volume': str(row['volume'])
            } for row in rows]

    except Exception as e:
        logger.error(f"Error getting price history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get price history")

# Order endpoints
@app.post("/listings/{listing_id}/orders/", tags=["orders"])
async def create_order(
    listing_id: UUID,
    order: CreateOrder,
    response: Response,
    manager: OrderManager = Depends(get_order_manager)
) -> dict:
    """Create a new order for a listing."""
    try:
        # Create the order
        result = await manager.create_order(
            listing_id=listing_id,
            buyer_address=order.buyer_address,
            items=[item.dict() for item in order.items]
        )
        
        # Format the response for frontend tracking
        order_data = {
            "id": str(result["id"]),
            "listing_id": str(result["listing_id"]),
            "buyer_address": result["buyer_address"],
            "payment_address": result["payment_address"],
            "status": result["status"],
            "total_price_evr": str(result["total_price_evr"]),
            "total_fee_evr": str(result["total_fee_evr"]),
            "total_payment_evr": str(result["total_payment_evr"]),
            "items": [{
                "asset_name": item["asset_name"],
                "amount": str(item["amount"]),
                "price_evr": str(item["price_evr"]),
                "fee_evr": str(item["fee_evr"])
            } for item in result["items"]],
            "created_at": result["created_at"].isoformat() if result["created_at"] else None,
            "updated_at": result["updated_at"].isoformat() if result["updated_at"] else None
        }
        
        # Set cookie with order tracking info
        response.set_cookie(
            key=f"order_{order_data['id']}", 
            value=json.dumps(order_data),
            max_age=60*60*24*30,  # 30 days
            httponly=False,  # Allow JavaScript access
            samesite="strict",
            secure=True
        )
        
        return order_data
        
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

@app.get("/orders/", tags=["orders"])
async def search_orders(
    buyer_address: Optional[str] = Query(None, description="Filter by buyer address"),
    listing_id: Optional[UUID] = Query(None, description="Filter by listing ID"),
    status: Optional[str] = Query(None, description="Filter by order status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    manager: OrderManager = Depends(get_order_manager)
) -> List[dict]:
    """Search orders with various filters."""
    logger.info(
        "Searching orders with params: buyer=%r, listing=%r, status=%r, limit=%d, offset=%d",
        buyer_address, listing_id, status, limit, offset
    )
    try:
        return await manager.search_orders(
            buyer_address=buyer_address,
            listing_id=listing_id,
            status=status,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Error searching orders: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/orders/{order_id}/status", tags=["orders"])
async def get_order_status(
    order_id: UUID,
    manager: OrderManager = Depends(get_order_manager)
) -> dict:
    """Get detailed status information for an order."""
    logger.info(f"Getting status for order {order_id}")
    try:
        order = await manager.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
            
        balances = await manager.get_order_balances(order_id)
        
        # Calculate payment progress
        total_required = order['total_payment_evr']
        total_paid = sum(
            balance['confirmed_balance'] 
            for balance in balances.values()
        )
        
        # Get payout information
        async with manager.pool.acquire() as conn:
            payout = await conn.fetchrow(
                '''
                SELECT 
                    success,
                    failure_count,
                    last_attempt_time,
                    completed_at,
                    total_fees_paid
                FROM order_payouts
                WHERE order_id = $1
                ''',
                order_id
            )
            
            # Get fulfillment info for items
            items = await conn.fetch(
                '''
                SELECT 
                    asset_name,
                    amount,
                    fulfillment_time,
                    fulfillment_tx_hash
                FROM order_items
                WHERE order_id = $1
                ''',
                order_id
            )
            
            fulfillment_info = {
                item['asset_name']: {
                    'amount': str(item['amount']),
                    'fulfilled_at': item['fulfillment_time'].isoformat() if item['fulfillment_time'] else None,
                    'tx_hash': item['fulfillment_tx_hash']
                }
                for item in items
            }
        
        return {
            "order_id": order_id,
            "status": order['status'],
            "total_required": total_required,
            "total_paid": total_paid,
            "is_paid": total_paid >= total_required,
            "balances": balances,
            "payout_info": {
                "is_completed": payout['success'] if payout else False,
                "failure_count": payout['failure_count'] if payout else 0,
                "last_attempt": payout['last_attempt_time'].isoformat() if payout and payout['last_attempt_time'] else None,
                "completed_at": payout['completed_at'].isoformat() if payout and payout['completed_at'] else None,
                "total_fees_paid": str(payout['total_fees_paid']) if payout and payout['total_fees_paid'] else "0",
            },
            "fulfillment": fulfillment_info
        }
    except Exception as e:
        logger.error(f"Error getting order status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 