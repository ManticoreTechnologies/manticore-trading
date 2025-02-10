"""Listings API endpoints."""

from fastapi import APIRouter, HTTPException, Query, status, Security, Depends
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, timedelta
import asyncio

from listings import (
    ListingManager, ListingError, ListingNotFoundError, InvalidPriceError,
    get_listings, get_listing, get_listing_by_deposit_address,
    get_listings_by_seller_address, get_listings_by_asset_name,
    get_listings_by_tag, get_address_transactions,
    get_listing_transactions, get_seller_transactions,
    withdraw
)
from auth import get_current_user, auth_scheme
from database import get_pool

# Create router without global security
router = APIRouter(
    prefix="/listings",
    tags=["Listings"]
)

# Import management endpoints
from .management import router as management_router

# Include management router (protected endpoints)
router.include_router(management_router)

# Model definitions
class PriceSpecification(BaseModel):
    """Model for price specification."""
    asset_name: str
    price_evr: Optional[Decimal] = None
    price_asset_name: Optional[str] = None
    price_asset_amount: Optional[Decimal] = None
    ipfs_hash: Optional[str] = None
    units: Optional[int] = 8  # Optional with default value of 8

class CreateListingRequest(BaseModel):
    """Request model for creating a listing."""
    seller_address: str
    name: str
    description: Optional[str] = None
    image_ipfs_hash: Optional[str] = None
    prices: List[PriceSpecification]
    tags: Optional[List[str]] = None

class UpdateListingRequest(BaseModel):
    """Request model for updating a listing."""
    name: Optional[str] = None
    description: Optional[str] = None
    image_ipfs_hash: Optional[str] = None
    tags: Optional[List[str]] = None
    payout_address: Optional[str] = None
    prices: Optional[List[PriceSpecification]] = None

class WithdrawRequest(BaseModel):
    """Request model for withdrawing from a listing."""
    asset_name: str
    amount: Decimal

""" Public Endpoints - No Authentication Required """
@router.get("/")
async def list_listings(
    per_page: int = Query(50),
    page: int = Query(1)
):
    """Get all listings with pagination metadata."""
    try:
        offset = (page - 1) * per_page
        return await get_listings(offset=offset, limit=per_page)
    except ListingNotFoundError:
        # Return empty result set with pagination metadata
        return {
            "listings": [],
            "total_count": 0,
            "total_pages": 0,
            "current_page": page,
            "limit": per_page,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/search")
async def search(
    search_term: Optional[str] = Query(None),
    seller_address: Optional[str] = Query(None),
    asset_name: Optional[str] = Query(None),
    min_price_evr: Optional[Decimal] = Query(None),
    max_price_evr: Optional[Decimal] = Query(None),
    status: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    per_page: int = Query(50),
    page: int = Query(1)
):
    """Search listings with various filters."""
    try:
        offset = (page - 1) * per_page
        manager = ListingManager()
        return await manager.search_listings(
            search_term=search_term,
            seller_address=seller_address,
            asset_name=asset_name,
            min_price_evr=min_price_evr,
            max_price_evr=max_price_evr,
            status=status,
            tags=tags,
            limit=per_page,
            offset=offset
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/by-id/{listing_id}")
async def get_listing_by_id(listing_id: str):
    """Get a listing by ID."""
    try:
        manager = ListingManager()
        listing = await manager.get_listing(listing_id)
        
        # Add tags if not present
        if 'tags' not in listing and hasattr(listing, 'tags'):
            listing['tags'] = listing.tags.split(',') if listing.tags else []
            
        # Add payout address if not present
        if 'payout_address' not in listing and hasattr(listing, 'payout_address'):
            listing['payout_address'] = listing.payout_address
            
        return listing
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/by-deposit-address/{deposit_address}")
async def get_listing_by_deposit(deposit_address: str):
    """Get a listing by deposit address."""
    try:
        return await get_listing_by_deposit_address(deposit_address)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing with deposit address {deposit_address} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/by-seller-address/{seller_address}")
async def get_seller_listings(seller_address: str):
    """Get listings by seller address."""
    try:
        return await get_listings_by_seller_address(seller_address)
    except LookupError:
        return {
            "listings": [],
            "total_count": 0,
            "seller_address": seller_address
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/by-asset-name/{asset_name}")
async def get_asset_listings(asset_name: str):
    """Get listings by asset name."""
    try:
        return await get_listings_by_asset_name(asset_name)
    except LookupError:
        return {
            "listings": [],
            "total_count": 0,
            "asset_name": asset_name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/by-tag/{tag}")
async def get_tag_listings(
    tag: str,
    per_page: int = Query(50),
    page: int = Query(1)
):
    """Get listings by tag."""
    try:
        return await ListingManager().search_listings(
            tags=[tag],
            limit=per_page,
            offset=(page - 1) * per_page
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/transactions/{address}")
async def get_address_txns(
    address: str,
    asset_name: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    min_confirmations: Optional[int] = Query(None),
    per_page: int = Query(50),
    page: int = Query(1)
):
    """Get transaction history for an address."""
    try:
        offset = (page - 1) * per_page
        return await get_address_transactions(
            address=address,
            asset_name=asset_name,
            entry_type=entry_type,
            min_confirmations=min_confirmations,
            limit=per_page,
            offset=offset
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{listing_id}/transactions")
async def get_listing_txns(
    listing_id: str,
    asset_name: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    min_confirmations: Optional[int] = Query(None),
    per_page: int = Query(50),
    page: int = Query(1)
):
    """Get transactions for a specific listing."""
    try:
        offset = (page - 1) * per_page
        return await get_listing_transactions(
            listing_id=listing_id,
            asset_name=asset_name,
            entry_type=entry_type,
            min_confirmations=min_confirmations,
            limit=per_page,
            offset=offset
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/seller/{seller_address}/transactions")
async def get_seller_txns(
    seller_address: str,
    asset_name: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    min_confirmations: Optional[int] = Query(None),
    per_page: int = Query(50),
    page: int = Query(1)
):
    """Get all transactions for a seller's listings."""
    try:
        offset = (page - 1) * per_page
        return await get_seller_transactions(
            seller_address=seller_address,
            asset_name=asset_name,
            entry_type=entry_type,
            min_confirmations=min_confirmations,
            limit=per_page,
            offset=offset
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/featured")
async def get_featured_listings(
    per_page: int = Query(10),
    page: int = Query(1)
):
    """Get featured listings with pagination.
    Featured listings are manually curated by admins."""
    try:
        pool = await get_pool()
        offset = (page - 1) * per_page
        
        async with pool.acquire() as conn:
            # Get featured listings
            listings = await conn.fetch(
                '''
                SELECT l.*
                FROM listings l
                JOIN featured_listings fl ON l.id = fl.listing_id
                WHERE l.status = 'active'
                ORDER BY fl.featured_at DESC
                LIMIT $1 OFFSET $2
                ''',
                per_page,
                offset
            )
            
            # Get total count
            total_count = await conn.fetchval(
                '''
                SELECT COUNT(*)
                FROM listings l
                JOIN featured_listings fl ON l.id = fl.listing_id
                WHERE l.status = 'active'
                '''
            )
            
            # Process listings
            manager = ListingManager(pool)
            processed_listings = []
            for listing in listings:
                try:
                    full_listing = await manager.get_listing(listing['id'])
                    processed_listings.append(full_listing)
                except Exception as e:
                    continue
            
            return {
                "listings": processed_listings,
                "total_count": total_count,
                "total_pages": (total_count + per_page - 1) // per_page,
                "current_page": page,
                "limit": per_page,
                "offset": offset
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/trending")
async def get_trending_listings(
    timeframe: str = Query("24h", regex="^(1h|24h|7d|30d)$"),
    per_page: int = Query(10),
    page: int = Query(1)
):
    """Get trending listings based on views, orders, and sales.
    Timeframe options: 1h, 24h, 7d, 30d"""
    try:
        pool = await get_pool()
        offset = (page - 1) * per_page
        
        # Calculate start time based on timeframe
        now = datetime.utcnow()
        timeframes = {
            "1h": now - timedelta(hours=1),
            "24h": now - timedelta(days=1),
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30)
        }
        start_time = timeframes[timeframe]
        
        async with pool.acquire() as conn:
            # Get trending listings based on a weighted score of views, orders, and sales
            listings = await conn.fetch(
                '''
                WITH metrics AS (
                    SELECT 
                        l.id,
                        COUNT(DISTINCT v.viewer_address) as unique_views,
                        COUNT(DISTINCT o.id) as order_count,
                        COUNT(DISTINCT s.id) as sale_count
                    FROM listings l
                    LEFT JOIN listing_views v ON l.id = v.listing_id 
                        AND v.view_time >= $1
                    LEFT JOIN orders o ON l.id = o.listing_id 
                        AND o.created_at >= $1
                    LEFT JOIN sale_history s ON l.id = s.listing_id 
                        AND s.sale_time >= $1
                    WHERE l.status = 'active'
                    GROUP BY l.id
                )
                SELECT 
                    l.*,
                    (m.unique_views * 1 + m.order_count * 10 + m.sale_count * 100) as score
                FROM listings l
                JOIN metrics m ON l.id = m.id
                WHERE l.status = 'active'
                ORDER BY score DESC
                LIMIT $2 OFFSET $3
                ''',
                start_time,
                per_page,
                offset
            )
            
            # Get total count
            total_count = await conn.fetchval(
                '''
                SELECT COUNT(DISTINCT l.id)
                FROM listings l
                JOIN metrics m ON l.id = m.id
                WHERE l.status = 'active'
                '''
            )
            
            # Process listings
            manager = ListingManager(pool)
            processed_listings = []
            for listing in listings:
                try:
                    full_listing = await manager.get_listing(listing['id'])
                    processed_listings.append(full_listing)
                except Exception as e:
                    continue
            
            return {
                "listings": processed_listings,
                "total_count": total_count,
                "total_pages": (total_count + per_page - 1) // per_page,
                "current_page": page,
                "limit": per_page,
                "offset": offset,
                "timeframe": timeframe
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/new")
async def get_new_listings(
    hours: int = Query(24, ge=1, le=168),  # Default 24 hours, max 7 days
    per_page: int = Query(10),
    page: int = Query(1)
):
    """Get newest listings within the specified time window."""
    try:
        pool = await get_pool()
        offset = (page - 1) * per_page
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        async with pool.acquire() as conn:
            # Get new listings
            listings = await conn.fetch(
                '''
                SELECT *
                FROM listings
                WHERE status = 'active'
                AND created_at >= $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                ''',
                start_time,
                per_page,
                offset
            )
            
            # Get total count
            total_count = await conn.fetchval(
                '''
                SELECT COUNT(*)
                FROM listings
                WHERE status = 'active'
                AND created_at >= $1
                ''',
                start_time
            )
            
            # Process listings
            manager = ListingManager(pool)
            processed_listings = []
            for listing in listings:
                try:
                    full_listing = await manager.get_listing(listing['id'])
                    processed_listings.append(full_listing)
                except Exception as e:
                    continue
            
            return {
                "listings": processed_listings,
                "total_count": total_count,
                "total_pages": (total_count + per_page - 1) // per_page,
                "current_page": page,
                "limit": per_page,
                "offset": offset,
                "time_window_hours": hours
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/home")
async def get_home_listings(
    featured_count: int = Query(5, ge=1, le=20),
    trending_count: int = Query(10, ge=1, le=50),
    new_count: int = Query(10, ge=1, le=50),
    trending_timeframe: str = Query("24h", regex="^(1h|24h|7d|30d)$"),
    new_hours: int = Query(24, ge=1, le=168)
):
    """Get featured, trending, and new listings for the home page."""
    try:
        pool = await get_pool()
        manager = ListingManager(pool)
        
        async with pool.acquire() as conn:
            # Get featured listings
            featured = await conn.fetch(
                '''
                SELECT l.*
                FROM listings l
                JOIN featured_listings fl ON l.id = fl.listing_id
                WHERE l.status = 'active'
                AND (fl.expires_at IS NULL OR fl.expires_at > now())
                ORDER BY fl.priority DESC, fl.featured_at DESC
                LIMIT $1
                ''',
                featured_count
            )
            
            # Calculate start time for trending
            now = datetime.utcnow()
            timeframes = {
                "1h": now - timedelta(hours=1),
                "24h": now - timedelta(days=1),
                "7d": now - timedelta(days=7),
                "30d": now - timedelta(days=30)
            }
            trending_start = timeframes[trending_timeframe]
            
            # Get trending listings
            trending = await conn.fetch(
                '''
                WITH metrics AS (
                    SELECT 
                        l.id,
                        COUNT(DISTINCT v.viewer_address) as unique_views,
                        COUNT(DISTINCT o.id) as order_count,
                        COUNT(DISTINCT s.id) as sale_count
                    FROM listings l
                    LEFT JOIN listing_views v ON l.id = v.listing_id 
                        AND v.view_time >= $1
                    LEFT JOIN orders o ON l.id = o.listing_id 
                        AND o.created_at >= $1
                    LEFT JOIN sale_history s ON l.id = s.listing_id 
                        AND s.sale_time >= $1
                    WHERE l.status = 'active'
                    GROUP BY l.id
                )
                SELECT 
                    l.*,
                    (m.unique_views * 1 + m.order_count * 10 + m.sale_count * 100) as score
                FROM listings l
                JOIN metrics m ON l.id = m.id
                WHERE l.status = 'active'
                ORDER BY score DESC
                LIMIT $2
                ''',
                trending_start,
                trending_count
            )
            
            # Get new listings
            new_start = now - timedelta(hours=new_hours)
            new = await conn.fetch(
                '''
                SELECT *
                FROM listings
                WHERE status = 'active'
                AND created_at >= $1
                ORDER BY created_at DESC
                LIMIT $2
                ''',
                new_start,
                new_count
            )
            
            # Process all listings to include full details
            async def process_listings(listings):
                result = []
                for listing in listings:
                    try:
                        full_listing = await manager.get_listing(listing['id'])
                        result.append(full_listing)
                    except Exception as e:
                        continue
                return result
            
            # Process all sections concurrently
            featured_listings, trending_listings, new_listings = await asyncio.gather(
                process_listings(featured),
                process_listings(trending),
                process_listings(new)
            )
            
            return {
                "featured": {
                    "listings": featured_listings,
                    "total": len(featured_listings)
                },
                "trending": {
                    "listings": trending_listings,
                    "total": len(trending_listings),
                    "timeframe": trending_timeframe
                },
                "new": {
                    "listings": new_listings,
                    "total": len(new_listings),
                    "time_window_hours": new_hours
                }
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

""" Protected Endpoints - Authentication Required """
@router.post("/")
async def create_listing(
    request: CreateListingRequest,
    current_user: str = Security(get_current_user)  # Add authentication
):
    """Create a new listing."""
    try:
        # Verify seller address matches authenticated user
        if request.seller_address.lower() != current_user.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seller address must match authenticated address"
            )
            
        manager = ListingManager()
        return await manager.create_listing(
            seller_address=request.seller_address,
            name=request.name,
            description=request.description,
            image_ipfs_hash=request.image_ipfs_hash,
            prices=[dict(price) for price in request.prices],
            tags=request.tags
        )
    except InvalidPriceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch("/{listing_id}")
async def update_listing(
    listing_id: str,
    update: UpdateListingRequest,
    current_user: str = Security(get_current_user)
):
    """Update a listing.
    
    Only the listing owner can update their listing.
    Cannot change: seller_address, listing_address, deposit_address, units
    """
    try:
        manager = ListingManager()
        
        # Get current listing to verify ownership
        listing = await manager.get_listing(listing_id)
        if not listing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Listing {listing_id} not found"
            )
            
        # Verify ownership
        if listing['seller_address'].lower() != current_user.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this listing"
            )
            
        # Build update dict with only provided fields
        updates = {}
        if update.name is not None:
            updates['name'] = update.name
        if update.description is not None:
            updates['description'] = update.description
        if update.image_ipfs_hash is not None:
            updates['image_ipfs_hash'] = update.image_ipfs_hash
        if update.tags is not None:
            updates['tags'] = ','.join(update.tags) if update.tags else None
        if update.payout_address is not None:
            updates['payout_address'] = update.payout_address
            
        # Update base listing info if any updates
        if updates:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    f'''
                    UPDATE listings
                    SET {', '.join(f"{k} = ${i+1}" for i, k in enumerate(updates.keys()))},
                        updated_at = now()
                    WHERE id = ${len(updates) + 1}
                    ''',
                    *updates.values(),
                    listing_id
                )
                
        # Update prices if provided
        if update.prices:
            await manager.update_listing_prices(
                listing_id,
                add_or_update_prices=[price.dict() for price in update.prices]
            )
            
        # Get updated listing
        updated = await manager.get_listing(listing_id)
        return updated
        
    except ListingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/by-id/{listing_id}")
async def delete_listing(
    listing_id: str,
    current_user: str = Security(get_current_user)  # Add authentication
):
    """Delete a listing."""
    try:
        manager = ListingManager()
        
        # Verify listing exists and user owns it
        listing = await manager.get_listing(listing_id)
        if not listing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Listing {listing_id} not found"
            )
            
        if listing['seller_address'].lower() != current_user.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this listing"
            )
            
        return await manager.delete_listing(listing_id)
    except ListingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{listing_id}/withdraw")
async def withdraw_from_listing(
    listing_id: str,
    withdraw_request: WithdrawRequest,
    current_user: str = Security(get_current_user)  # Add authentication
):
    """Withdraw assets from a listing to the seller's address."""
    try:
        # Verify listing exists and user owns it
        manager = ListingManager()
        listing = await manager.get_listing(listing_id)
        if not listing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Listing {listing_id} not found"
            )
            
        if listing['seller_address'].lower() != current_user.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to withdraw from this listing"
            )
            
        return await withdraw(
            listing_id=listing_id,
            asset_name=withdraw_request.asset_name,
            amount=withdraw_request.amount,
            to_address=listing['seller_address']  # Always withdraw to seller's address
        )
    except ListingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found"
        )
    except ListingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{listing_id}/rescan")
async def rescan_listing_balance(
    listing_id: str,
    current_user: str = Security(get_current_user)
):
    """Rescan and recalculate listing balances.
    
    This endpoint allows manual rescanning of a listing's balances by:
    1. Fetching all transactions for the listing's deposit address
    2. Recalculating confirmed and pending balances
    3. Creating balance entries for any new assets
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify listing exists and user owns it
            listing = await conn.fetchrow(
                '''
                SELECT seller_address, deposit_address
                FROM listings
                WHERE id = $1
                ''',
                listing_id
            )
            
            if not listing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Listing {listing_id} not found"
                )
                
            if listing['seller_address'].lower() != current_user.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to rescan this listing"
                )

            # Create balance entries for any new assets
            await conn.execute(
                '''
                INSERT INTO listing_balances (listing_id, asset_name, confirmed_balance, pending_balance)
                SELECT DISTINCT 
                    l.id,
                    te.asset_name,
                    0,
                    0
                FROM transaction_entries te
                JOIN listings l ON l.deposit_address = te.address
                WHERE l.id = $1
                AND te.entry_type = 'receive'
                AND NOT EXISTS (
                    SELECT 1 
                    FROM listing_balances lb 
                    WHERE lb.listing_id = l.id 
                    AND lb.asset_name = te.asset_name
                )
                ON CONFLICT (listing_id, asset_name) DO NOTHING
                ''',
                listing_id
            )

            # Recalculate confirmed balances
            await conn.execute(
                '''
                WITH confirmed_txs AS (
                    SELECT 
                        te.asset_name,
                        SUM(te.amount) as total_amount,
                        MAX(te.tx_hash) as last_tx_hash,
                        MAX(te.time) as last_tx_time
                    FROM transaction_entries te
                    WHERE te.address = $1
                    AND te.entry_type = 'receive'
                    AND te.abandoned = false
                    AND te.confirmations >= 6
                    GROUP BY te.asset_name
                )
                UPDATE listing_balances lb
                SET 
                    confirmed_balance = COALESCE(ct.total_amount, 0),
                    last_confirmed_tx_hash = ct.last_tx_hash,
                    last_confirmed_tx_time = ct.last_tx_time,
                    updated_at = now()
                FROM confirmed_txs ct
                WHERE lb.listing_id = $2
                AND lb.asset_name = ct.asset_name
                ''',
                listing['deposit_address'],
                listing_id
            )

            # Recalculate pending balances
            await conn.execute(
                '''
                WITH pending_txs AS (
                    SELECT 
                        te.asset_name,
                        SUM(te.amount) as total_amount
                    FROM transaction_entries te
                    WHERE te.address = $1
                    AND te.entry_type = 'receive'
                    AND te.abandoned = false
                    AND te.confirmations < 6
                    GROUP BY te.asset_name
                )
                UPDATE listing_balances lb
                SET 
                    pending_balance = COALESCE(pt.total_amount, 0),
                    updated_at = now()
                FROM pending_txs pt
                WHERE lb.listing_id = $2
                AND lb.asset_name = pt.asset_name
                ''',
                listing['deposit_address'],
                listing_id
            )

            # Get updated balances
            balances = await conn.fetch(
                '''
                SELECT 
                    asset_name,
                    confirmed_balance,
                    pending_balance,
                    last_confirmed_tx_hash,
                    last_confirmed_tx_time,
                    updated_at
                FROM listing_balances
                WHERE listing_id = $1
                ORDER BY asset_name
                ''',
                listing_id
            )

            return {
                "listing_id": listing_id,
                "balances": [{
                    "asset_name": b['asset_name'],
                    "confirmed_balance": str(b['confirmed_balance']),
                    "pending_balance": str(b['pending_balance']),
                    "last_confirmed_tx_hash": b['last_confirmed_tx_hash'],
                    "last_confirmed_tx_time": b['last_confirmed_tx_time'].isoformat() if b['last_confirmed_tx_time'] else None,
                    "updated_at": b['updated_at'].isoformat()
                } for b in balances],
                "scanned_at": datetime.utcnow().isoformat()
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Export the router
__all__ = ['router']
