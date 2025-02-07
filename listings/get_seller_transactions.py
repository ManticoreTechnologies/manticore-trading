"""Get transaction history for all listings owned by a seller."""

from typing import Optional, Dict
from decimal import Decimal
from database import get_pool

async def get_seller_transactions(
    seller_address: str,
    asset_name: Optional[str] = None,
    entry_type: Optional[str] = None,
    min_confirmations: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict:
    """Get transaction history for all listings owned by a seller.
    
    Args:
        seller_address: The seller's address
        asset_name: Optional filter by asset name
        entry_type: Optional filter by entry type ('send' or 'receive')
        min_confirmations: Optional minimum confirmations filter
        limit: Number of results per page
        offset: Offset for pagination
        
    Returns:
        Dict containing:
        - transactions: List of transaction entries
        - total_count: Total number of transactions matching filters
        - metadata: Pagination metadata
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Build base query to get transactions for all listings owned by the seller
        query = """
            SELECT 
                te.tx_hash,
                te.address,
                te.entry_type,
                te.asset_name,
                te.amount,
                te.fee,
                te.confirmations,
                te.time,
                te.asset_type,
                te.asset_message,
                te.vout,
                te.trusted,
                te.bip125_replaceable,
                te.abandoned,
                te.created_at,
                te.updated_at,
                l.id as listing_id,
                l.name as listing_name
            FROM transaction_entries te
            JOIN listings l ON te.address IN (l.listing_address, l.deposit_address)
            WHERE l.seller_address = $1
        """
        count_query = """
            SELECT COUNT(*) 
            FROM transaction_entries te
            JOIN listings l ON te.address IN (l.listing_address, l.deposit_address)
            WHERE l.seller_address = $1
        """
        
        # Build query params
        params = [seller_address]
        param_num = 2
        
        # Add optional filters
        if asset_name:
            query += f" AND te.asset_name = ${param_num}"
            count_query += f" AND te.asset_name = ${param_num}"
            params.append(asset_name)
            param_num += 1
            
        if entry_type:
            query += f" AND te.entry_type = ${param_num}"
            count_query += f" AND te.entry_type = ${param_num}"
            params.append(entry_type)
            param_num += 1
            
        if min_confirmations is not None:
            query += f" AND te.confirmations >= ${param_num}"
            count_query += f" AND te.confirmations >= ${param_num}"
            params.append(min_confirmations)
            param_num += 1
        
        # Add ordering and pagination
        query += " ORDER BY te.time DESC, te.tx_hash NULLS LAST"
        query += f" LIMIT ${param_num} OFFSET ${param_num + 1}"
        params.extend([limit, offset])
        
        # Execute queries
        transactions = await conn.fetch(query, *params)
        total_count = await conn.fetchval(count_query, *params[:-2])  # Exclude limit/offset
        
        # Format results
        results = []
        for tx in transactions:
            tx_dict = dict(tx)
            # Convert Decimal objects to strings for JSON serialization
            for key in ['amount', 'fee']:
                if isinstance(tx_dict[key], Decimal):
                    tx_dict[key] = str(tx_dict[key])
            # Convert UUID to string
            tx_dict['listing_id'] = str(tx_dict['listing_id'])
            results.append(tx_dict)
        
        return {
            'transactions': results,
            'total_count': total_count,
            'metadata': {
                'limit': limit,
                'offset': offset,
                'page': (offset // limit) + 1,
                'total_pages': (total_count + limit - 1) // limit
            }
        } 