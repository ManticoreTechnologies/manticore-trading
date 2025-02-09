"""Orders API endpoints."""

from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional, Dict, Any
from decimal import Decimal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from database import get_pool
from orders import OrderManager, OrderError

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

# Import management endpoints
from .management import *

# Export the router
__all__ = ['router'] 