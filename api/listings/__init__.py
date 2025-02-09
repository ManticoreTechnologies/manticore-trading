"""Listings API endpoints."""

from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel
from uuid import UUID

from listings import (
    ListingManager, ListingError, ListingNotFoundError, InvalidPriceError,
    get_listings, get_listing, get_listing_by_deposit_address,
    get_listings_by_seller_address, get_listings_by_asset_name,
    get_listings_by_tag, get_address_transactions,
    get_listing_transactions, get_seller_transactions,
    withdraw
)

# Create router
router = APIRouter(
    prefix="/listings",
    tags=["Listings"]
)

# Import management endpoints
from .management import router as management_router

# Include management router
router.include_router(management_router)

""" Getters """
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
    except LookupError:
        # Return empty search result with pagination metadata
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

@router.get("/by-id/{listing_id}")
async def get_listing_by_id(listing_id: str):
    """Get a listing by ID."""
    try:
        return await get_listing(listing_id)
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
    """Get listings by tag with pagination."""
    try:
        offset = (page - 1) * per_page
        return await get_listings_by_tag(
            tag=tag,
            limit=per_page,
            offset=offset
        )
    except LookupError:
        return {
            "listings": [],
            "total_count": 0,
            "total_pages": 0,
            "current_page": page,
            "limit": per_page,
            "offset": offset,
            "tag": tag
        }
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

class PriceSpecification(BaseModel):
    """Model for price specification."""
    asset_name: str
    price_evr: Optional[Decimal] = None
    price_asset_name: Optional[str] = None
    price_asset_amount: Optional[Decimal] = None
    ipfs_hash: Optional[str] = None
    units: Optional[int] = 8  # Default to 8 decimal places

class CreateListingRequest(BaseModel):
    """Request model for creating a listing."""
    seller_address: str
    name: str
    description: Optional[str] = None
    image_ipfs_hash: Optional[str] = None
    prices: List[PriceSpecification]
    tags: Optional[List[str]] = None

@router.post("/")
async def create_listing(request: CreateListingRequest):
    """Create a new listing."""
    try:
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

class UpdateListingRequest(BaseModel):
    """Request model for updating a listing."""
    name: Optional[str] = None
    description: Optional[str] = None
    image_ipfs_hash: Optional[str] = None
    tags: Optional[List[str]] = None
    prices: Optional[List[PriceSpecification]] = None

@router.post("/by-id/{listing_id}")
async def update_listing(listing_id: str, request: UpdateListingRequest):
    """Update a listing's details."""
    try:
        manager = ListingManager()
        
        # First verify the listing exists
        try:
            await manager.get_listing(listing_id)
        except ListingNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Listing {listing_id} not found"
            )
            
        # Build updates dict
        updates = {}
        if request.name is not None:
            updates['name'] = request.name
        if request.description is not None:
            updates['description'] = request.description
        if request.image_ipfs_hash is not None:
            updates['image_ipfs_hash'] = request.image_ipfs_hash
        if request.tags is not None:
            updates['tags'] = request.tags
        if request.prices is not None:
            updates['prices'] = [dict(price) for price in request.prices]
            
        # Update listing
        try:
            updated_listing = await manager.update_listing(listing_id, updates)
            return updated_listing
        except ListingError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/by-id/{listing_id}")
async def delete_listing(listing_id: str):
    """Delete a listing."""
    try:
        manager = ListingManager()
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

@router.get("/test/create-listing")
async def create_test_listing():
    """Create a test listing with sample data."""
    try:
        manager = ListingManager()
        return await manager.create_test_listing()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

class WithdrawRequest(BaseModel):
    """Request model for withdrawing from a listing."""
    asset_name: str
    amount: Decimal
    to_address: str

@router.post("/{listing_id}/withdraw")
async def withdraw_from_listing(
    listing_id: str,
    withdraw_request: WithdrawRequest
):
    """Withdraw assets from a listing."""
    try:
        return await withdraw(
            listing_id=listing_id,
            asset_name=withdraw_request.asset_name,
            amount=withdraw_request.amount,
            to_address=withdraw_request.to_address
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

# Export the router
__all__ = ['router']
