"""Seller management endpoints for listing control and analytics."""

from fastapi import APIRouter, HTTPException, status, Depends, Security
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from decimal import Decimal
from database import get_pool
from listings import ListingManager, ListingError
from auth import get_current_user, AuthError, auth_scheme

# Create router without prefix since it will be included in the main listings router
router = APIRouter()

class Price(BaseModel):
    """Model for listing price in a specific asset."""
    asset_name: str = Field(..., description="The asset name/symbol (e.g. BTC)")
    price_evr: Decimal = Field(..., description="The price in EVR")
    units: Optional[int] = Field(default=8, description="Decimal places for the price (default: 8)")

class CreateListingRequest(BaseModel):
    """Model for creating a new listing."""
    seller_address: str = Field(..., description="The seller's address")
    name: str = Field(..., description="Name of the listing")
    description: str = Field(..., description="Description of the listing")
    image_ipfs_hash: Optional[str] = Field(None, description="Optional IPFS hash of the listing image")
    prices: List[Price] = Field(..., description="List of prices in different assets")
    tags: List[str] = Field(default=[], description="List of tags for the listing")
    payout_address: Optional[str] = Field(None, description="Optional payout address, defaults to seller_address if not provided")

@router.post("/")
async def create_listing(
    listing: CreateListingRequest,
    authenticated_address: str = Security(get_current_user)
):
    """Create a new listing.
    
    Args:
        listing: The listing details
        authenticated_address: The authenticated address from the JWT token
        
    Returns:
        Dict containing the created listing details
        
    Raises:
        HTTPException: If authentication fails or seller address doesn't match authenticated address
    """
    try:
        # Verify seller address matches authenticated address
        if listing.seller_address.lower() != authenticated_address.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seller address must match authenticated address"
            )
            
        manager = ListingManager()
        result = await manager.create_listing(
            seller_address=listing.seller_address,
            name=listing.name,
            description=listing.description,
            image_ipfs_hash=listing.image_ipfs_hash,
            prices=[price.dict() for price in listing.prices],
            tags=listing.tags,
            payout_address=listing.payout_address
        )
        return result
    except ListingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create listing: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

class ListingAnalytics(BaseModel):
    """Model for listing analytics data."""
    views: int
    unique_views: int
    sales_count: int
    total_revenue: Decimal
    conversion_rate: float
    avg_time_to_sale: Optional[float] = None
    popular_payment_methods: Dict[str, int]
    sales_by_day: Dict[str, int]

@router.post("/listings/{listing_id}/pause")
async def pause_listing(listing_id: str):
    """Temporarily pause a listing from accepting new orders.
    
    Args:
        listing_id: The listing's UUID
        
    Returns:
        Dict containing updated listing status
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify listing exists and is active
            listing = await conn.fetchrow(
                '''
                SELECT id, status
                FROM listings
                WHERE id = $1 AND status = 'active'
                ''',
                listing_id
            )
            
            if not listing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Listing {listing_id} not found or not active"
                )
            
            # Update listing status
            await conn.execute(
                '''
                UPDATE listings
                SET status = 'paused',
                    updated_at = now()
                WHERE id = $1
                ''',
                listing_id
            )
            
            return {
                "listing_id": listing_id,
                "status": "paused",
                "paused_at": datetime.utcnow().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/listings/{listing_id}/resume")
async def resume_listing(listing_id: str):
    """Resume a paused listing.
    
    Args:
        listing_id: The listing's UUID
        
    Returns:
        Dict containing updated listing status
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify listing exists and is paused
            listing = await conn.fetchrow(
                '''
                SELECT id, status
                FROM listings
                WHERE id = $1 AND status = 'paused'
                ''',
                listing_id
            )
            
            if not listing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Listing {listing_id} not found or not paused"
                )
            
            # Update listing status
            await conn.execute(
                '''
                UPDATE listings
                SET status = 'active',
                    updated_at = now()
                WHERE id = $1
                ''',
                listing_id
            )
            
            return {
                "listing_id": listing_id,
                "status": "active",
                "resumed_at": datetime.utcnow().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/listings/{listing_id}/analytics")
async def get_listing_analytics(
    listing_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> ListingAnalytics:
    """Get detailed analytics about listing performance.
    
    Args:
        listing_id: The listing's UUID
        start_date: Optional start date for analytics period
        end_date: Optional end date for analytics period
        
    Returns:
        ListingAnalytics object containing performance metrics
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify listing exists
            exists = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM listings WHERE id = $1)',
                listing_id
            )
            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Listing {listing_id} not found"
                )
            
            # Use default date range if not specified
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # Get view counts
            views = await conn.fetchrow(
                '''
                SELECT 
                    COUNT(*) as total_views,
                    COUNT(DISTINCT viewer_address) as unique_views
                FROM listing_views
                WHERE listing_id = $1
                AND view_time BETWEEN $2 AND $3
                ''',
                listing_id,
                start_date,
                end_date
            )
            
            # Get sales data
            sales = await conn.fetchrow(
                '''
                SELECT 
                    COUNT(*) as sales_count,
                    COALESCE(SUM(price_evr), 0) as total_revenue,
                    AVG(EXTRACT(EPOCH FROM (sale_time - created_at)) / 3600) as avg_time_to_sale
                FROM sale_history
                WHERE listing_id = $1
                AND sale_time BETWEEN $2 AND $3
                ''',
                listing_id,
                start_date,
                end_date
            )
            
            # Get payment method distribution
            payment_methods = await conn.fetch(
                '''
                SELECT asset_name, COUNT(*) as count
                FROM sale_history
                WHERE listing_id = $1
                AND sale_time BETWEEN $2 AND $3
                GROUP BY asset_name
                ORDER BY count DESC
                ''',
                listing_id,
                start_date,
                end_date
            )
            
            # Get daily sales
            daily_sales = await conn.fetch(
                '''
                SELECT 
                    DATE_TRUNC('day', sale_time) as sale_date,
                    COUNT(*) as count
                FROM sale_history
                WHERE listing_id = $1
                AND sale_time BETWEEN $2 AND $3
                GROUP BY DATE_TRUNC('day', sale_time)
                ORDER BY sale_date
                ''',
                listing_id,
                start_date,
                end_date
            )
            
            # Calculate conversion rate
            conversion_rate = (sales['sales_count'] / views['total_views']) if views['total_views'] > 0 else 0
            
            return ListingAnalytics(
                views=views['total_views'],
                unique_views=views['unique_views'],
                sales_count=sales['sales_count'],
                total_revenue=sales['total_revenue'],
                conversion_rate=conversion_rate,
                avg_time_to_sale=sales['avg_time_to_sale'],
                popular_payment_methods={
                    pm['asset_name']: pm['count']
                    for pm in payment_methods
                },
                sales_by_day={
                    ds['sale_date'].strftime("%Y-%m-%d"): ds['count']
                    for ds in daily_sales
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

class BatchUpdateRequest(BaseModel):
    """Model for batch update request."""
    listing_ids: List[str]
    updates: Dict[str, Any]

@router.post("/listings/batch-update")
async def batch_update_listings(update_request: BatchUpdateRequest):
    """Update multiple listings at once.
    
    Args:
        update_request: The batch update details
        
    Returns:
        Dict containing update results
    """
    try:
        pool = await get_pool()
        manager = ListingManager(pool)
        results = {}
        failed = 0
        
        for listing_id in update_request.listing_ids:
            try:
                # Update each listing
                await manager.update_listing(listing_id, update_request.updates)
                results[listing_id] = {
                    "success": True,
                    "updated_at": datetime.utcnow().isoformat()
                }
            except Exception as e:
                failed += 1
                results[listing_id] = {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "total": len(update_request.listing_ids),
            "successful": len(update_request.listing_ids) - failed,
            "failed": failed,
            "results": results
        }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Export the router
__all__ = ['router'] 