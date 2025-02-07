from typing import Dict, Any, Union
from database import get_pool
import uuid

async def get_listings_by_tag(tag: str, offset: int = 0, limit: int = 10, pool=None) -> Dict[str, Any]:
    """Get listings by tag with all related data and pagination metadata.
    
    Args:
        tag: The tag to filter listings
        pool: The database connection pool
        offset: The offset for pagination
        limit: The limit for pagination
        
    Returns:
        Dict containing listing details including prices and balances with pagination metadata
        
    Raises:
        LookupError: if no listings are found
    """
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        
        # Get base listing with pagination and filter by tag
        listings = await conn.fetch(
            'SELECT * FROM listings WHERE $1 = ANY(tags) OFFSET $2 LIMIT $3',
            tag, offset, limit
        )
        
        # Get total count of listings for the tag
        total_count = await conn.fetchval(
            'SELECT COUNT(*) FROM listings WHERE $1 = ANY(tags)',
            tag
        )
        
        if not listings:
            raise LookupError("No listings found for the given tag")
        
        # Calculate current page
        current_page = (offset // limit) + 1
        
        # Calculate next page and previous page
        next_page = current_page + 1 if offset + limit < total_count else None
        previous_page = current_page - 1 if offset > 0 else None
        
        # Convert to dict and ensure proper JSON serialization
        listings_dict = {
            str(listing['id']): {
                'id': str(listing['id']),  # Convert UUID to string
                'seller_address': listing['seller_address'],
                'listing_address': listing['listing_address'],
                'deposit_address': listing['deposit_address'],
                'name': listing['name'],
                'description': listing['description'],
                'image_ipfs_hash': listing['image_ipfs_hash'],
                'status': listing['status'],
                'created_at': listing['created_at'].isoformat() if listing['created_at'] else None,
                'updated_at': listing['updated_at'].isoformat() if listing['updated_at'] else None,
                'prices': [],
                'balances': []
            }
            for listing in listings
        }
        
        # Get prices with units
        prices = await conn.fetch(
            'SELECT * FROM listing_prices'
        )
        
        for p in prices:
            listing_id = str(p['listing_id'])
            if listing_id in listings_dict:
                listings_dict[listing_id]['prices'].append({
                    'asset_name': p['asset_name'],
                    'price_evr': str(p['price_evr']) if p['price_evr'] is not None else None,
                    'price_asset_name': p['price_asset_name'],
                    'price_asset_amount': str(p['price_asset_amount']) if p['price_asset_amount'] is not None else None,
                    'ipfs_hash': p['ipfs_hash'],
                    'units': p.get('units', 8),  # Default to 8 if units not specified
                    'created_at': p['created_at'].isoformat() if p['created_at'] else None,
                    'updated_at': p['updated_at'].isoformat() if p['updated_at'] else None
                })
        
        # Get balances with units
        balances = await conn.fetch(
            'SELECT * FROM listing_balances'
        )
        
        for b in balances:
            listing_id = str(b['listing_id'])
            if listing_id in listings_dict:
                listings_dict[listing_id]['balances'].append({
                    'asset_name': b['asset_name'],
                    'confirmed_balance': str(b['confirmed_balance']) if b['confirmed_balance'] is not None else '0',
                    'pending_balance': str(b['pending_balance']) if b['pending_balance'] is not None else '0',
                    'units': b.get('units', 8),  # Default to 8 if units not specified
                    'last_confirmed_tx_hash': b['last_confirmed_tx_hash'],
                    'last_confirmed_tx_time': b['last_confirmed_tx_time'].isoformat() if b['last_confirmed_tx_time'] else None,
                    'created_at': b['created_at'].isoformat() if b['created_at'] else None,
                    'updated_at': b['updated_at'].isoformat() if b['updated_at'] else None
                })
        
        result = {
            'listings': list(listings_dict.values()),
            'offset': offset,
            'limit': limit,
            'total': total_count,  # Total count of listings
            'current_page': current_page,  # Current page
            'current_page_total': len(listings),  # Total count of listings on current page
            'next_page': next_page,  # Next page
            'previous_page': previous_page  # Previous page
        }
        
        return result
    
