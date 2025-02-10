"""Featured listings payment endpoints."""

from fastapi import APIRouter, HTTPException, Security, status
from typing import Optional, Dict, Any
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import UUID

from auth import get_current_user
from database import get_pool
from rpc import client as rpc_client

router = APIRouter(
    prefix="/featured",
    tags=["Featured Listings"]
)

# Constants for featured listing pricing
FEATURED_LISTING_PRICES = {
    "basic": {
        "amount_evr": Decimal("100"),
        "duration_days": 7,
        "priority_level": 0
    },
    "premium": {
        "amount_evr": Decimal("250"),
        "duration_days": 14,
        "priority_level": 1
    },
    "platinum": {
        "amount_evr": Decimal("500"),
        "duration_days": 30,
        "priority_level": 2
    }
}

class FeaturedListingPlan(BaseModel):
    """Model for featured listing plan details."""
    name: str
    amount_evr: Decimal
    duration_days: int
    priority_level: int

class CreateFeaturedPaymentRequest(BaseModel):
    """Request model for creating a featured listing payment."""
    listing_id: UUID
    plan_name: str

class FeaturedPaymentResponse(BaseModel):
    """Response model for featured listing payment."""
    id: UUID
    listing_id: UUID
    payment_address: str
    amount_evr: Decimal
    duration_days: int
    priority_level: int
    status: str
    created_at: datetime
    expires_at: Optional[datetime]

@router.get("/plans")
async def get_featured_plans():
    """Get available featured listing plans."""
    return {
        name: FeaturedListingPlan(
            name=name,
            amount_evr=plan["amount_evr"],
            duration_days=plan["duration_days"],
            priority_level=plan["priority_level"]
        ) for name, plan in FEATURED_LISTING_PRICES.items()
    }

@router.post("/payments", response_model=FeaturedPaymentResponse)
async def create_featured_payment(
    request: CreateFeaturedPaymentRequest,
    current_user: str = Security(get_current_user)
):
    """Create a new featured listing payment."""
    try:
        # Get plan details
        plan = FEATURED_LISTING_PRICES.get(request.plan_name)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan name: {request.plan_name}"
            )
            
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify listing exists and user owns it
            listing = await conn.fetchrow(
                '''
                SELECT seller_address
                FROM listings
                WHERE id = $1
                ''',
                request.listing_id
            )
            
            if not listing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Listing {request.listing_id} not found"
                )
                
            if listing['seller_address'].lower() != current_user.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only feature your own listings"
                )
            
            # Check if listing already has a pending payment
            pending = await conn.fetchval(
                '''
                SELECT EXISTS(
                    SELECT 1
                    FROM featured_listing_payments
                    WHERE listing_id = $1
                    AND status = 'pending'
                )
                ''',
                request.listing_id
            )
            
            if pending:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Listing already has a pending featured payment"
                )
            
            # Generate payment address
            payment_address = rpc_client.getnewaddress()
            
            # Create payment record
            payment = await conn.fetchrow(
                '''
                INSERT INTO featured_listing_payments (
                    listing_id,
                    payment_address,
                    amount_evr,
                    duration_days,
                    priority_level,
                    status
                ) VALUES ($1, $2, $3, $4, $5, 'pending')
                RETURNING *
                ''',
                request.listing_id,
                payment_address,
                plan["amount_evr"],
                plan["duration_days"],
                plan["priority_level"]
            )
            
            return {
                "id": payment["id"],
                "listing_id": payment["listing_id"],
                "payment_address": payment["payment_address"],
                "amount_evr": payment["amount_evr"],
                "duration_days": payment["duration_days"],
                "priority_level": payment["priority_level"],
                "status": payment["status"],
                "created_at": payment["created_at"],
                "expires_at": None
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/payments/{payment_id}", response_model=FeaturedPaymentResponse)
async def get_featured_payment(
    payment_id: UUID,
    current_user: str = Security(get_current_user)
):
    """Get featured listing payment details."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Get payment with listing owner
            payment = await conn.fetchrow(
                '''
                SELECT p.*, l.seller_address
                FROM featured_listing_payments p
                JOIN listings l ON l.id = p.listing_id
                WHERE p.id = $1
                ''',
                payment_id
            )
            
            if not payment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Payment {payment_id} not found"
                )
                
            # Verify ownership
            if payment['seller_address'].lower() != current_user.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this payment"
                )
            
            # Get expiry if payment is completed
            expires_at = None
            if payment['paid_at']:
                expires_at = payment['paid_at'] + timedelta(days=payment['duration_days'])
            
            return {
                "id": payment["id"],
                "listing_id": payment["listing_id"],
                "payment_address": payment["payment_address"],
                "amount_evr": payment["amount_evr"],
                "duration_days": payment["duration_days"],
                "priority_level": payment["priority_level"],
                "status": payment["status"],
                "created_at": payment["created_at"],
                "expires_at": expires_at
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/payments", response_model=list[FeaturedPaymentResponse])
async def list_featured_payments(
    listing_id: Optional[UUID] = None,
    current_user: str = Security(get_current_user)
):
    """List featured listing payments for the authenticated user."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Build query
            query = '''
                SELECT p.*, l.seller_address
                FROM featured_listing_payments p
                JOIN listings l ON l.id = p.listing_id
                WHERE l.seller_address = $1
            '''
            params = [current_user]
            
            if listing_id:
                query += " AND p.listing_id = $2"
                params.append(listing_id)
                
            query += " ORDER BY p.created_at DESC"
            
            # Get payments
            payments = await conn.fetch(query, *params)
            
            return [
                {
                    "id": p["id"],
                    "listing_id": p["listing_id"],
                    "payment_address": p["payment_address"],
                    "amount_evr": p["amount_evr"],
                    "duration_days": p["duration_days"],
                    "priority_level": p["priority_level"],
                    "status": p["status"],
                    "created_at": p["created_at"],
                    "expires_at": p["paid_at"] + timedelta(days=p["duration_days"]) if p["paid_at"] else None
                }
                for p in payments
            ]
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Export router
__all__ = ['router'] 