"""Get transaction history for a specific address."""

from typing import Optional, Dict, List
from decimal import Decimal
from database import get_pool

async def get_address_transactions(
    address: str,
    asset_name: Optional[str] = None,
    entry_type: Optional[str] = None,
    min_confirmations: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict:
    """Get transaction history for a specific address with optional filters.
    
    Args:
        address: The address to get transactions for
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
        # Build base query
        query = """
            SELECT 
                tx_hash,
                entry_type,
                asset_name,
                amount,
                fee,
                confirmations,
                time,
                asset_type,
                asset_message,
                vout,
                trusted,
                bip125_replaceable,
                abandoned,
                created_at,
                updated_at
            FROM transaction_entries
            WHERE address = $1
        """
        count_query = """
            SELECT COUNT(*) 
            FROM transaction_entries 
            WHERE address = $1
        """
        
        # Build query params
        params = [address]
        param_num = 2
        
        # Add optional filters
        if asset_name:
            query += f" AND asset_name = ${param_num}"
            count_query += f" AND asset_name = ${param_num}"
            params.append(asset_name)
            param_num += 1
            
        if entry_type:
            query += f" AND entry_type = ${param_num}"
            count_query += f" AND entry_type = ${param_num}"
            params.append(entry_type)
            param_num += 1
            
        if min_confirmations is not None:
            query += f" AND confirmations >= ${param_num}"
            count_query += f" AND confirmations >= ${param_num}"
            params.append(min_confirmations)
            param_num += 1
        
        # Add ordering and pagination
        query += " ORDER BY time DESC, tx_hash NULLS LAST"
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