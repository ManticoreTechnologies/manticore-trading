"""Orders API endpoints"""

from api import app
import orders
from fastapi import HTTPException, Query, status
from pydantic import BaseModel
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

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

@app.post("/listings/{listing_id}/orders")
async def create_order(listing_id: str, order_request: CreateOrderRequest):
    """Create a new order for a listing."""
    try:
        return await orders.OrderManager().create_order(
            listing_id=listing_id,
            buyer_address=order_request.buyer_address,
            items=[{"asset_name": item.asset_name, "amount": item.amount} for item in order_request.items]
        )
    except orders.ListingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found"
        )
    except orders.InsufficientBalanceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except orders.OrderError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get order details by ID."""
    try:
        order = await orders.OrderManager().get_order(order_id)
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

@app.get("/orders/{order_id}/balances")
async def get_order_balances(order_id: str):
    """Get order payment balances."""
    try:
        return await orders.OrderManager().get_order_balances(order_id)
    except orders.OrderError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/orders")
async def search_orders(
    buyer_address: Optional[str] = Query(None),
    listing_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    per_page: int = Query(50),
    page: int = Query(1)
):
    """Search orders with various filters."""
    try:
        return await orders.OrderManager().search_orders(
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

@app.post("/cart/orders")
async def create_cart_order(cart_request: CartOrderRequest):
    """Create a new cart order for multiple listings."""
    try:
        return await orders.OrderManager().create_cart_order(
            buyer_address=cart_request.buyer_address,
            items=cart_request.items
        )
    except orders.ListingNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except orders.InsufficientBalanceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except orders.OrderError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/cart/orders/{cart_order_id}")
async def get_cart_order(cart_order_id: str):
    """Get cart order details by ID."""
    try:
        order = await orders.OrderManager().get_cart_order(cart_order_id)
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

@app.get("/cart/orders/{cart_order_id}/balances")
async def get_cart_order_balances(cart_order_id: str):
    """Get cart order payment balances."""
    try:
        return await orders.OrderManager().get_cart_order_balances(cart_order_id)
    except orders.OrderError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart order {cart_order_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 