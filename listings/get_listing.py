from typing import Dict, Any, Union
from database import get_pool
import uuid

async def get_listing(listing_id: Union[str, uuid.UUID], pool=None) -> Dict[str, Any]:
    """Get a listing by ID with all related data.
    
    Args:
        listing_id: The listing UUID
        
    Returns:
        Dict containing listing details including prices and balances
        
    Raises:
        LookupError: If listing doesn't exist
    """
    if pool is None:
        pool = await get_pool()
    
    async with pool.acquire() as conn:
        
        # Get base listing
        listing = await conn.fetchrow(
            'SELECT * FROM listings WHERE id = $1',
            listing_id
        )
        
        if not listing:
            raise LookupError(f"Listing {listing_id} not found")
        
        # Convert to dict and ensure proper JSON serialization
        result = {
            'id': str(listing['id']),  # Convert UUID to string
            'seller_address': listing['seller_address'],
            'listing_address': listing['listing_address'],
            'deposit_address': listing['deposit_address'],
            'name': listing['name'],
            'description': listing['description'],
            'image_ipfs_hash': listing['image_ipfs_hash'],
            'status': listing['status'],
            'created_at': listing['created_at'].isoformat() if listing['created_at'] else None,
            'updated_at': listing['updated_at'].isoformat() if listing['updated_at'] else None
        }
        
        # Get prices with units
        prices = await conn.fetch(
            'SELECT * FROM listing_prices WHERE listing_id = $1',
            listing_id
        )
        result['prices'] = [{
            'asset_name': p['asset_name'],
            'price_evr': str(p['price_evr']) if p['price_evr'] is not None else None,
            'price_asset_name': p['price_asset_name'],
            'price_asset_amount': str(p['price_asset_amount']) if p['price_asset_amount'] is not None else None,
            'ipfs_hash': p['ipfs_hash'],
            'units': p.get('units', 8),  # Default to 8 if units not specified
            'created_at': p['created_at'].isoformat() if p['created_at'] else None,
            'updated_at': p['updated_at'].isoformat() if p['updated_at'] else None
        } for p in prices]
        
        # Get balances with units
        balances = await conn.fetch(
            'SELECT * FROM listing_balances WHERE listing_id = $1',
            listing_id
        )
        result['balances'] = [{
            'asset_name': b['asset_name'],
            'confirmed_balance': str(b['confirmed_balance']) if b['confirmed_balance'] is not None else '0',
            'pending_balance': str(b['pending_balance']) if b['pending_balance'] is not None else '0',
            'units': b.get('units', 8),  # Default to 8 if units not specified
            'last_confirmed_tx_hash': b['last_confirmed_tx_hash'],
            'last_confirmed_tx_time': b['last_confirmed_tx_time'].isoformat() if b['last_confirmed_tx_time'] else None,
            'created_at': b['created_at'].isoformat() if b['created_at'] else None,
            'updated_at': b['updated_at'].isoformat() if b['updated_at'] else None
        } for b in balances]
        
        return result
        