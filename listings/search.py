""" Search listings in the database """
from typing import Optional, List, Dict, Any
from decimal import Decimal
from fastapi import Query, HTTPException, Depends
from listings import ListingManager
from database import get_pool
import logging

logger = logging.getLogger(__name__)

async def search(
        search_term: Optional[str] = None,
        seller_address: Optional[str] = None,
        asset_name: Optional[str] = None,
        min_price_evr: Optional[Decimal] = None,
        max_price_evr: Optional[Decimal] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
        pool = None
    ) -> Dict[str, Any]:
        """Search listings with various filters.
        
        Args:
            search_term: Optional text to search in name and description
            seller_address: Optional seller address to filter by
            asset_name: Optional asset name to filter by
            min_price_evr: Optional minimum EVR price
            max_price_evr: Optional maximum EVR price
            status: Optional listing status to filter by
            tags: Optional list of tags to filter by (matches any)
            limit: Maximum number of results to return (default: 50)
            offset: Number of results to skip (default: 0)
            
        Returns:
            Dict containing:
                - listings: List of matching listings with their details
                - total_count: Total number of listings matching the filters
                - total_pages: Total number of pages
                - current_page: Current page number
        """
        if pool is None:
            pool = await get_pool()
        
        try:
            # Build the base query for counting total results
            count_query = """
                SELECT COUNT(DISTINCT l.id)
                FROM listings l
                LEFT JOIN listing_prices lp ON l.id = lp.listing_id
                WHERE 1=1
            """
            
            # Build the base query for fetching listings
            query = """
                SELECT DISTINCT l.*
                FROM listings l
                LEFT JOIN listing_prices lp ON l.id = lp.listing_id
                WHERE 1=1
            """
            params = []
            param_idx = 1
            
            # Add search conditions to both queries
            if search_term:
                search_condition = f" AND (l.name ILIKE ${param_idx} OR l.description ILIKE ${param_idx})"
                query += search_condition
                count_query += search_condition
                params.append(f"%{search_term}%")
                param_idx += 1
                
            if seller_address:
                seller_condition = f" AND l.seller_address = ${param_idx}"
                query += seller_condition
                count_query += seller_condition
                params.append(seller_address)
                param_idx += 1
                
            if asset_name:
                asset_condition = f" AND EXISTS (SELECT 1 FROM listing_prices WHERE listing_id = l.id AND asset_name = ${param_idx})"
                query += asset_condition
                count_query += asset_condition
                params.append(asset_name)
                param_idx += 1

            if tags:
                # Convert tags to array and use ANY to match any of the provided tags
                tags_condition = f" AND l.tags && ${param_idx}::text[]"
                query += tags_condition
                count_query += tags_condition
                params.append(tags)
                param_idx += 1
                
            if min_price_evr is not None:
                min_price_condition = f" AND EXISTS (SELECT 1 FROM listing_prices WHERE listing_id = l.id AND price_evr >= ${param_idx})"
                query += min_price_condition
                count_query += min_price_condition
                params.append(min_price_evr)
                param_idx += 1
                
            if max_price_evr is not None:
                max_price_condition = f" AND EXISTS (SELECT 1 FROM listing_prices WHERE listing_id = l.id AND price_evr <= ${param_idx})"
                query += max_price_condition
                count_query += max_price_condition
                params.append(max_price_evr)
                param_idx += 1
                
            if status:
                status_condition = f" AND l.status = ${param_idx}"
                query += status_condition
                count_query += status_condition
                params.append(status)
                param_idx += 1
                
            # Add ordering and pagination only to the main query
            query += " ORDER BY l.created_at DESC LIMIT $" + str(param_idx) + " OFFSET $" + str(param_idx + 1)
            pagination_params = [limit, offset]
            
            logger.debug("Executing search query: %s with params: %r", query, params + pagination_params)
            
            async with pool.acquire() as conn:
                try:
                    # Get total count first
                    total_count = await conn.fetchval(count_query, *params)
                    
                    # Calculate pagination metadata
                    total_pages = (total_count + limit - 1) // limit
                    current_page = (offset // limit) + 1
                    
                    # Execute search query
                    rows = await conn.fetch(query, *(params + pagination_params))
                    logger.debug("Search query returned %d base results", len(rows))
                    
                    # Get full listing details for each result
                    listings = []
                    for row in rows:
                        try:
                            # Convert row to dict and serialize UUID and datetime fields
                            listing = {
                                'id': str(row['id']),  # Convert UUID to string
                                'seller_address': row['seller_address'],
                                'listing_address': row['listing_address'],
                                'deposit_address': row['deposit_address'],
                                'name': row['name'],
                                'description': row['description'],
                                'image_ipfs_hash': row['image_ipfs_hash'],
                                'status': row['status'],
                                'tags': row['tags'].split(',') if row['tags'] else [],  # Convert comma-separated string to list
                                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                                'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                            }
                            
                            # Get prices
                            prices = await conn.fetch(
                                'SELECT * FROM listing_prices WHERE listing_id = $1',
                                row['id']
                            )
                            listing['prices'] = [{
                                'asset_name': p['asset_name'],
                                'price_evr': str(p['price_evr']) if p['price_evr'] is not None else None,
                                'price_asset_name': p['price_asset_name'],
                                'price_asset_amount': str(p['price_asset_amount']) if p['price_asset_amount'] is not None else None,
                                'ipfs_hash': p['ipfs_hash'],
                                'units': p.get('units', 8),  # Default to 8 if units not specified
                                'created_at': p['created_at'].isoformat() if p['created_at'] else None,
                                'updated_at': p['updated_at'].isoformat() if p['updated_at'] else None
                            } for p in prices]
                            
                            # Get balances
                            balances = await conn.fetch(
                                'SELECT * FROM listing_balances WHERE listing_id = $1',
                                row['id']
                            )
                            listing['balances'] = [{
                                'asset_name': b['asset_name'],
                                'confirmed_balance': str(b['confirmed_balance']) if b['confirmed_balance'] is not None else '0',
                                'pending_balance': str(b['pending_balance']) if b['pending_balance'] is not None else '0',
                                'units': b.get('units', 8),  # Default to 8 if units not specified
                                'last_confirmed_tx_hash': b['last_confirmed_tx_hash'],
                                'last_confirmed_tx_time': b['last_confirmed_tx_time'].isoformat() if b['last_confirmed_tx_time'] else None,
                                'created_at': b['created_at'].isoformat() if b['created_at'] else None,
                                'updated_at': b['updated_at'].isoformat() if b['updated_at'] else None
                            } for b in balances]
                            
                            listings.append(listing)
                        except Exception as e:
                            logger.error("Error getting details for listing %s: %s", row.get('id'), str(e))
                            continue
                    
                    logger.debug("Returning %d listings with full details", len(listings))
                    return {
                        'listings': listings,
                        'total_count': total_count,
                        'total_pages': total_pages,
                        'current_page': current_page,
                        'limit': limit
                    }
                    
                except Exception as e:
                    logger.exception("Database error executing search query: %s", str(e))
                    raise LookupError(f"Database error: {str(e)}")
                    
        except Exception as e:
            logger.exception("Error in search_listings: %s", str(e))
            raise

