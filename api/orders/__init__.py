"""Orders API endpoints."""

from fastapi import APIRouter, HTTPException, Query, status, Security
from typing import List, Optional, Dict, Any
from decimal import Decimal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from database import get_pool
from orders import OrderManager, OrderError
from auth import get_current_user

# Create router
router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)

class OrderItem(BaseModel):
    """Request model for order items."""
    asset_name: str
    amount: Decimal

class CreateOrderRequest(BaseModel):
    """Request model for creating an order."""
    buyer_address: str
    items: List[OrderItem]

class CartOrderRequest(BaseModel):
    """Request model for creating a cart order."""
    buyer_address: str
    items: List[dict]  # List of {listing_id, asset_name, amount}

class DisputeRequest(BaseModel):
    """Request model for creating a dispute."""
    reason: str
    description: str
    evidence: Optional[Dict[str, Any]] = None

@router.post("/create/{listing_id}")
async def create_order(listing_id: str, order_request: CreateOrderRequest):
    """Create a new order for a listing."""
    try:
        return await OrderManager().create_order(
            listing_id=listing_id,
            buyer_address=order_request.buyer_address,
            items=[{"asset_name": item.asset_name, "amount": item.amount} for item in order_request.items]
        )
    except OrderError.ListingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found"
        )
    except OrderError.InsufficientBalanceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except OrderError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{order_id}")
async def get_order(order_id: str):
    """Get order details by ID."""
    try:
        order = await OrderManager().get_order(order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found"
            )
        return order
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{order_id}/balances")
async def get_order_balances(order_id: str):
    """Get order payment balances."""
    try:
        return await OrderManager().get_order_balances(order_id)
    except OrderError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/")
async def search_orders(
    buyer_address: Optional[str] = Query(None),
    listing_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    per_page: int = Query(50),
    page: int = Query(1)
):
    """Search orders with various filters."""
    try:
        return await OrderManager().search_orders(
            buyer_address=buyer_address,
            listing_id=listing_id,
            status=status,
            limit=per_page,
            offset=(page - 1) * per_page
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/cart")
async def create_cart_order(cart_request: CartOrderRequest):
    """Create a new cart order for multiple listings."""
    try:
        return await OrderManager().create_cart_order(
            buyer_address=cart_request.buyer_address,
            items=cart_request.items
        )
    except OrderError.ListingNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except OrderError.InsufficientBalanceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except OrderError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/cart/{cart_order_id}")
async def get_cart_order(cart_order_id: str):
    """Get cart order details by ID."""
    try:
        order = await OrderManager().get_cart_order(cart_order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cart order {cart_order_id} not found"
            )
        return order
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/cart/{cart_order_id}/balances")
async def get_cart_order_balances(cart_order_id: str):
    """Get cart order payment balances."""
    try:
        return await OrderManager().get_cart_order_balances(cart_order_id)
    except OrderError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart order {cart_order_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    current_user: str = Security(get_current_user)
):
    """Cancel an order if it's still pending."""
    try:
        manager = OrderManager()
        order = await manager.get_order(order_id)
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found"
            )
            
        # Verify ownership
        if order['buyer_address'].lower() != current_user.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to cancel this order"
            )
            
        # Cancel the order
        await manager.cancel_order(order_id)
        return {"status": "cancelled"}
        
    except OrderError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{order_id}/dispute")
async def create_dispute(
    order_id: str,
    dispute: DisputeRequest,
    current_user: str = Security(get_current_user)
):
    """Create a dispute for an order."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify order exists and user is buyer
            order = await conn.fetchrow(
                '''
                SELECT buyer_address, status
                FROM orders
                WHERE id = $1
                ''',
                order_id
            )
            
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found"
                )
                
            if order['buyer_address'].lower() != current_user.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to dispute this order"
                )
                
            if order['status'] not in ('paid', 'completed'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot dispute order in status: {order['status']}"
                )
                
            # Create dispute
            dispute_id = await conn.fetchval(
                '''
                INSERT INTO order_disputes (
                    order_id,
                    reason,
                    description,
                    evidence,
                    status
                ) VALUES ($1, $2, $3, $4, 'opened')
                RETURNING id
                ''',
                order_id,
                dispute.reason,
                dispute.description,
                dispute.evidence
            )
            
            return {
                "dispute_id": dispute_id,
                "status": "opened"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{order_id}/history")
async def get_order_history(
    order_id: str,
    current_user: str = Security(get_current_user)
):
    """Get the history of status changes and events for an order."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify order exists and user is buyer
            order = await conn.fetchrow(
                '''
                SELECT buyer_address
                FROM orders
                WHERE id = $1
                ''',
                order_id
            )
            
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found"
                )
                
            if order['buyer_address'].lower() != current_user.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this order's history"
                )
                
            # Get history entries
            history = await conn.fetch(
                '''
                SELECT 
                    id,
                    status,
                    description,
                    details,
                    created_at
                FROM order_history
                WHERE order_id = $1
                ORDER BY created_at DESC
                ''',
                order_id
            )
            
            return {
                "order_id": order_id,
                "history": [dict(entry) for entry in history]
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/disputes")
async def list_disputes(
    order_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: str = Security(get_current_user)
):
    """List disputes for orders."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Build query conditions
            conditions = ["o.buyer_address = $1"]
            params = [current_user]
            param_idx = 2
            
            if order_id:
                conditions.append(f"d.order_id = ${param_idx}")
                params.append(order_id)
                param_idx += 1
                
            if status:
                conditions.append(f"d.status = ${param_idx}")
                params.append(status)
                param_idx += 1
                
            # Get disputes
            disputes = await conn.fetch(
                f'''
                SELECT 
                    d.id,
                    d.order_id,
                    d.reason,
                    d.description,
                    d.status,
                    d.created_at,
                    d.resolved_at,
                    d.resolution
                FROM order_disputes d
                JOIN orders o ON o.id = d.order_id
                WHERE {" AND ".join(conditions)}
                ORDER BY d.created_at DESC
                ''',
                *params
            )
            
            return {
                "disputes": [dict(d) for d in disputes]
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Import management endpoints
from .management import *

# Export the router
__all__ = ['router'] 