""" /api/listings """

from api import app
import listings
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from decimal import Decimal
from fastapi import Query, HTTPException, status, Body
from pydantic import BaseModel
from listings.withdraw import WithdrawError

""" Getters """
@app.get("/listings") # Get all listings with pagination metadata
async def get_listings(
    per_page: int = Query(50),
    page: int = Query(1)
):
    """ Get all listings with pagination metadata """
    try:
        offset = (page - 1) * per_page
        return await listings.get_listings(
            limit=per_page,
            offset=offset
        )
    except LookupError:
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

@app.get("/listings/search") # Search listings with various filters and pagination metadata
async def search_listings(
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
    """ Search listings with various filters """
    try:
        offset = (page - 1) * per_page
        return await listings.search(
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

@app.get("/listings/by-id/{listing_id}") # Get a listing by ID
async def get_listing(listing_id: str):
    try:
        return await listings.get_listing(listing_id)
    except listings.ListingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/listings/by-deposit-address/{deposit_address}") # Get a listing by deposit address
async def get_listing_by_deposit_address(deposit_address: str):
    try:
        return await listings.get_listing_by_deposit_address(deposit_address)
    except listings.ListingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No listing found for deposit address {deposit_address}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/listings/by-seller-address/{seller_address}") # Get listings by seller address
async def get_listings_by_seller_address(seller_address: str):
    try:
        return await listings.get_listings_by_seller_address(seller_address)
    except LookupError:
        # Return empty result for seller
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

@app.get("/listings/by-asset-name/{asset_name}") # Get listings by asset name
async def get_listings_by_asset_name(asset_name: str):
    try:
        return await listings.get_listings_by_asset_name(asset_name)
    except LookupError:
        # Return empty result for asset
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

@app.get("/listings/by-tag/{tag}") # Get listings by tag
async def get_listings_by_tag(
    tag: str,
    per_page: int = Query(50),
    page: int = Query(1)
):
    """ Get listings by tag with pagination """
    try:
        offset = (page - 1) * per_page
        return await listings.get_listings_by_tag(
            tag=tag,
            limit=per_page,
            offset=offset
        )
    except LookupError:
        # Return empty result for tag with pagination metadata
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

@app.get("/listings/transactions/{address}") # Get transaction history for an address
async def get_address_transactions(
    address: str,
    asset_name: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    min_confirmations: Optional[int] = Query(None),
    per_page: int = Query(50),
    page: int = Query(1)
):
    """ Get transaction history for a specific address with optional filters """
    try:
        offset = (page - 1) * per_page
        return await listings.get_address_transactions(
            address=address,
            asset_name=asset_name,
            entry_type=entry_type,
            min_confirmations=min_confirmations,
            limit=per_page,
            offset=offset
        )
    except LookupError:
        # Return empty transaction history with pagination metadata
        return {
            "transactions": [],
            "total_count": 0,
            "total_pages": 0,
            "current_page": page,
            "limit": per_page,
            "offset": offset,
            "address": address
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/listings/{listing_id}/transactions") # Get transactions for a specific listing
async def get_listing_transactions(
    listing_id: str,
    asset_name: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    min_confirmations: Optional[int] = Query(None),
    per_page: int = Query(50),
    page: int = Query(1)
):
    """ Get all transactions for a specific listing (both deposit and listing address) """
    try:
        offset = (page - 1) * per_page
        return await listings.get_listing_transactions(
            listing_id=listing_id,
            asset_name=asset_name,
            entry_type=entry_type,
            min_confirmations=min_confirmations,
            limit=per_page,
            offset=offset
        )
    except listings.ListingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found"
        )
    except LookupError:
        # Return empty transaction list with pagination metadata
        return {
            "transactions": [],
            "total_count": 0,
            "total_pages": 0,
            "current_page": page,
            "limit": per_page,
            "offset": offset,
            "listing_id": listing_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/listings/seller/{seller_address}/transactions") # Get all transactions for a seller's listings
async def get_seller_transactions(
    seller_address: str,
    asset_name: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    min_confirmations: Optional[int] = Query(None),
    per_page: int = Query(50),
    page: int = Query(1)
):
    """ Get all transactions for a seller's listings """
    try:
        offset = (page - 1) * per_page
        return await listings.get_seller_transactions(
            seller_address=seller_address,
            asset_name=asset_name,
            entry_type=entry_type,
            min_confirmations=min_confirmations,
            limit=per_page,
            offset=offset
        )
    except LookupError:
        # Return empty transaction list with pagination metadata
        return {
            "transactions": [],
            "total_count": 0,
            "total_pages": 0,
            "current_page": page,
            "limit": per_page,
            "offset": offset,
            "seller_address": seller_address
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

""" Setters """
@app.post("/listings/")
async def create_listing():
    try:
        return await listings.create_listing()
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

class UpdateListingRequest(BaseModel):
    """Request model for updating a listing."""
    name: Optional[str] = None
    description: Optional[str] = None
    image_ipfs_hash: Optional[str] = None
    tags: Optional[List[str]] = None
    prices: Optional[List[PriceSpecification]] = None

@app.post("/listings/by-id/{listing_id}")
async def update_listing(listing_id: str, update_request: UpdateListingRequest):
    """Update an existing listing.
    
    Args:
        listing_id: The listing's UUID
        update_request: The update details containing:
            - name (optional): New listing name
            - description (optional): New listing description
            - image_ipfs_hash (optional): New IPFS hash for listing image
            - tags (optional): New list of tags
            - prices (optional): New price specifications
    """
    try:
        manager = listings.ListingManager()
        
        # First verify the listing exists
        try:
            await manager.get_listing(listing_id)
        except listings.ListingNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Listing {listing_id} not found"
            )
        
        # Convert request model to dict, handling nested models
        updates = {}
        for field, value in update_request.dict(exclude_unset=True).items():
            if value is not None:
                if field == 'prices':
                    # Convert price specifications to dicts
                    updates[field] = [price.dict(exclude_unset=True) for price in update_request.prices]
                elif field == 'tags':
                    # Convert tags list to comma-separated string
                    updates[field] = ','.join(value)
                else:
                    updates[field] = value
        
        # Perform the update
        try:
            updated_listing = await manager.update_listing(listing_id, updates)
            return updated_listing
        except listings.InvalidPriceError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except listings.ListingError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update listing: {str(e)}"
        )

@app.delete("/listings/by-id/{listing_id}")
async def delete_listing(listing_id: str):
    try:
        return await listings.delete_listing(listing_id)
    except listings.ListingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

""" Test endpoints """
@app.get("/test/create-listing")
async def create_test_listing():
    try:
        return await listings.create_test_listing()
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

@app.post("/listings/{listing_id}/withdraw")
async def withdraw_from_listing(
    listing_id: str,
    withdraw_request: WithdrawRequest
):
    """Withdraw assets from a listing.
    
    Args:
        listing_id: The listing UUID
        withdraw_request: The withdrawal details containing:
            - asset_name: Name of asset to withdraw
            - amount: Amount to withdraw
            - to_address: Address to send assets to
    """
    try:
        result = await listings.withdraw(
            listing_id=listing_id,
            asset_name=withdraw_request.asset_name,
            amount=withdraw_request.amount,
            to_address=withdraw_request.to_address
        )
        return result
    except WithdrawError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        elif "insufficient balance" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
