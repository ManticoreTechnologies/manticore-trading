"""Listings module for managing marketplace listings.

This module provides functionality for:
- Creating and managing listings
- Tracking listing balances
- Managing deposit addresses
- Price management
"""

import logging
import uuid
from typing import Dict, List, Optional, Union, Any
from decimal import Decimal

from database import get_pool
from rpc import getnewaddress, getassetdata, RPCError

logger = logging.getLogger(__name__)

# User-mutable fields for listings
MUTABLE_FIELDS = {
    'name',
    'description',
    'image_ipfs_hash',
    'tags'
}

# System-managed fields (not directly mutable by users)
SYSTEM_FIELDS = {
    'id',
    'seller_address',
    'listing_address',
    'deposit_address',
    'created_at',
    'updated_at'
}

# Balance fields (managed by monitor)
BALANCE_FIELDS = {
    'confirmed_balance',
    'pending_balance',
    'last_confirmed_tx_hash',
    'last_confirmed_tx_time'
}

class ListingError(Exception):
    """Base exception for listing operations."""
    pass

class ListingNotFoundError(ListingError):
    """Raised when a listing is not found."""
    pass

class InvalidPriceError(ListingError):
    """Raised when price specification is invalid."""
    pass

class ListingManager:
    """Manager class for handling listing operations."""
    
    def __init__(self, pool=None):
        """Initialize the listing manager.
        
        Args:
            pool: Optional database pool. If not provided, will get from database module.
        """
        self.pool = pool
    
    async def ensure_pool(self):
        """Ensure we have a database pool."""
        if not self.pool:
            self.pool = await get_pool()
            
    async def create_listing(
        self,
        seller_address: str,
        name: str,
        description: Optional[str] = None,
        image_ipfs_hash: Optional[str] = None,
        prices: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Create a new listing.
        
        Args:
            seller_address: The seller's EVR address
            name: Name of the listing
            description: Optional description
            image_ipfs_hash: Optional IPFS hash for listing image
            prices: List of price specifications, each containing:
                   - asset_name: Name of asset being sold
                   - price_evr: Optional EVR price
                   - price_asset_name: Optional asset name for pricing
                   - price_asset_amount: Optional asset amount for pricing
                   - ipfs_hash: Optional IPFS hash for price-specific content
        
        Returns:
            Dict containing the created listing details
        
        Raises:
            ListingError: If creation fails
            InvalidPriceError: If price specification is invalid or asset not found
        """
        await self.ensure_pool()
        
        try:
            # Validate all asset names first
            if prices:
                for price in prices:
                    asset_name = price['asset_name']
                    try:
                        # Get asset data from Evrmore node
                        asset_data = getassetdata(asset_name)
                        if asset_data is None:
                            raise InvalidPriceError(f"Asset not found: {asset_name}")
                            
                        # If user didn't provide ipfs_hash, use the one from asset data if available
                        if not price.get('ipfs_hash') and asset_data.get('ipfs_hash'):
                            price['ipfs_hash'] = asset_data['ipfs_hash']
                            
                    except Exception as e:
                        logger.error(f"Error validating asset {asset_name}: {e}")
                        raise InvalidPriceError(f"Failed to validate asset {asset_name}: {str(e)}")
            
            # Generate listing and deposit addresses
            listing_address = getnewaddress()
            deposit_address = getnewaddress()
            
            # Create the listing in its own transaction
            async with self.pool.acquire() as conn:
                listing_id = await conn.fetchval(
                    '''
                    INSERT INTO listings (
                        seller_address, listing_address, deposit_address, 
                        name, description, image_ipfs_hash
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    ''',
                    seller_address, listing_address, deposit_address,
                    name, description, image_ipfs_hash
                )
            
            # Add prices if specified
            if prices:
                for price in prices:
                    asset_name = price['asset_name']
                    
                    # Add price entry in its own transaction
                    async with self.pool.acquire() as conn:
                        await conn.execute(
                            '''
                            INSERT INTO listing_prices (
                                listing_id, asset_name, price_evr,
                                price_asset_name, price_asset_amount, ipfs_hash
                            ) VALUES ($1, $2, $3, $4, $5, $6)
                            ''',
                            listing_id,
                            asset_name,
                            price.get('price_evr'),
                            price.get('price_asset_name'),
                            price.get('price_asset_amount'),
                            price.get('ipfs_hash')
                        )
                    
                    # Initialize balance entry
                    async with self.pool.acquire() as conn:
                        await conn.execute(
                            '''
                            INSERT INTO listing_balances (
                                listing_id, asset_name, confirmed_balance,
                                pending_balance
                            ) VALUES ($1, $2, 0, 0)
                            ''',
                            listing_id,
                            asset_name
                        )
            
            # Return full listing details
            return await self.get_listing(listing_id)
            
        except InvalidPriceError:
            # Re-raise InvalidPriceError without wrapping
            raise
        except Exception as e:
            logger.error(f"Error creating listing: {e}")
            raise ListingError(f"Failed to create listing: {e}")
            
    async def get_listing(self, listing_id: Union[str, uuid.UUID]) -> Dict[str, Any]:
        """Get a listing by ID with all related data.
        
        Args:
            listing_id: The listing UUID
            
        Returns:
            Dict containing listing details including prices and balances
            
        Raises:
            ListingNotFoundError: If listing doesn't exist
        """
        await self.ensure_pool()
        
        async with self.pool.acquire() as conn:
            # Get base listing
            listing = await conn.fetchrow(
                'SELECT * FROM listings WHERE id = $1',
                listing_id
            )
            
            if not listing:
                raise ListingNotFoundError(f"Listing {listing_id} not found")
            
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
            
            # Get prices
            prices = await conn.fetch(
                'SELECT * FROM listing_prices WHERE listing_id = $1',
                listing_id
            )
            result['prices'] = [{
                'asset_name': p['asset_name'],
                'price_evr': str(p['price_evr']) if p['price_evr'] is not None else None,
                'price_asset_name': p['price_asset_name'],
                'price_asset_amount': str(p['price_asset_amount']) if p['price_asset_amount'] is not None else None,
                'ipfs_hash': p['ipfs_hash']
            } for p in prices]
            
            # Get balances
            balances = await conn.fetch(
                'SELECT * FROM listing_balances WHERE listing_id = $1',
                listing_id
            )
            result['balances'] = [{
                'asset_name': b['asset_name'],
                'confirmed_balance': str(b['confirmed_balance']) if b['confirmed_balance'] is not None else '0',
                'pending_balance': str(b['pending_balance']) if b['pending_balance'] is not None else '0',
                'last_confirmed_tx_hash': b['last_confirmed_tx_hash'],
                'last_confirmed_tx_time': b['last_confirmed_tx_time'].isoformat() if b['last_confirmed_tx_time'] else None
            } for b in balances]
            
            return result
            
    async def update_listing(
        self,
        listing_id: Union[str, uuid.UUID],
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update mutable listing fields.
        
        Args:
            listing_id: The listing UUID
            updates: Dict of fields to update
            
        Returns:
            Updated listing details
            
        Raises:
            ListingNotFoundError: If listing doesn't exist
            ListingError: If update contains invalid/immutable fields
        """
        await self.ensure_pool()
        
        # Validate update fields
        invalid_fields = set(updates.keys()) - MUTABLE_FIELDS
        if invalid_fields:
            raise ListingError(f"Cannot update fields: {invalid_fields}")
        
        async with self.pool.acquire() as conn:
            # Check listing exists
            exists = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM listings WHERE id = $1)',
                listing_id
            )
            if not exists:
                raise ListingNotFoundError(f"Listing {listing_id} not found")
            
            # Build update query
            fields = []
            values = []
            for i, (field, value) in enumerate(updates.items(), start=1):
                fields.append(f"{field} = ${i}")
                values.append(value)
            values.append(listing_id)
            
            # Execute update
            await conn.execute(
                f'''
                UPDATE listings 
                SET {', '.join(fields)}
                WHERE id = ${len(values)}
                ''',
                *values
            )
            
            # Return updated listing
            return await self.get_listing(listing_id)
            
    async def delete_listing(self, listing_id: Union[str, uuid.UUID]) -> None:
        """Delete a listing and all associated data.
        
        Args:
            listing_id: The listing UUID
            
        Raises:
            ListingNotFoundError: If listing doesn't exist
        """
        await self.ensure_pool()
        
        async with self.pool.acquire() as conn:
            # Check listing exists
            exists = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM listings WHERE id = $1)',
                listing_id
            )
            if not exists:
                raise ListingNotFoundError(f"Listing {listing_id} not found")
            
            # Delete all associated data in correct order
            # First delete balances
            await conn.execute(
                'DELETE FROM listing_balances WHERE listing_id = $1',
                listing_id
            )
            
            # Then delete prices
            await conn.execute(
                'DELETE FROM listing_prices WHERE listing_id = $1',
                listing_id
            )
            
            # Finally delete the listing itself
            await conn.execute(
                'DELETE FROM listings WHERE id = $1',
                listing_id
            )
            logger.info(f"Deleted listing {listing_id}")
            
    async def get_listing_by_deposit_address(self, deposit_address: str) -> Dict[str, Any]:
        """Get a listing by its deposit address.
        
        Args:
            deposit_address: The deposit address to look up
            
        Returns:
            Dict containing listing details
            
        Raises:
            ListingNotFoundError: If no listing found with the deposit address
        """
        await self.ensure_pool()
        
        async with self.pool.acquire() as conn:
            # Get listing ID from deposit address
            listing_id = await conn.fetchval(
                '''
                SELECT id 
                FROM listings 
                WHERE deposit_address = $1
                ''',
                deposit_address
            )
            
            if not listing_id:
                raise ListingNotFoundError(
                    f"No listing found for deposit address {deposit_address}"
                )
            
            # Return full listing details
            return await self.get_listing(listing_id)

    async def get_deposit_address(self, listing_id: Union[str, uuid.UUID]) -> str:
        """Get deposit address for a listing.
        
        Args:
            listing_id: The listing UUID
            
        Returns:
            The listing's deposit address
            
        Raises:
            ListingNotFoundError: If listing doesn't exist
        """
        await self.ensure_pool()
        
        async with self.pool.acquire() as conn:
            # Get deposit address
            deposit_address = await conn.fetchval(
                'SELECT deposit_address FROM listings WHERE id = $1',
                listing_id
            )
            
            if not deposit_address:
                raise ListingNotFoundError(f"Listing {listing_id} not found")
            
            return deposit_address
            
    async def get_balances(self, listing_id: Union[str, uuid.UUID]) -> Dict[str, Dict[str, Decimal]]:
        """Get balances for a listing, keyed by asset name.
        
        Args:
            listing_id: The listing UUID
            
        Returns:
            Dict mapping asset names to balance info containing:
                - confirmed_balance: Confirmed balance
                - pending_balance: Pending balance
            
        Raises:
            ListingNotFoundError: If listing doesn't exist
        """
        await self.ensure_pool()
        
        async with self.pool.acquire() as conn:
            # Check listing exists
            exists = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM listings WHERE id = $1)',
                listing_id
            )
            if not exists:
                raise ListingNotFoundError(f"Listing {listing_id} not found")
            
            # Get balances
            rows = await conn.fetch(
                '''
                SELECT 
                    asset_name,
                    confirmed_balance,
                    pending_balance
                FROM listing_balances 
                WHERE listing_id = $1
                ''',
                listing_id
            )
            
            return {
                row['asset_name']: {
                    'confirmed_balance': row['confirmed_balance'] or Decimal('0'),
                    'pending_balance': row['pending_balance'] or Decimal('0')
                }
                for row in rows
            }

    async def search_listings(
        self,
        search_term: Optional[str] = None,
        seller_address: Optional[str] = None,
        asset_name: Optional[str] = None,
        min_price_evr: Optional[Decimal] = None,
        max_price_evr: Optional[Decimal] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search listings with various filters.
        
        Args:
            search_term: Optional text to search in name and description
            seller_address: Optional seller address to filter by
            asset_name: Optional asset name to filter by
            min_price_evr: Optional minimum EVR price
            max_price_evr: Optional maximum EVR price
            status: Optional listing status to filter by
            limit: Maximum number of results to return (default: 50)
            offset: Number of results to skip (default: 0)
            
        Returns:
            List of matching listings with their details
        """
        await self.ensure_pool()
        
        try:
            # Build the base query
            query = """
                SELECT DISTINCT l.*
                FROM listings l
                LEFT JOIN listing_prices lp ON l.id = lp.listing_id
                WHERE 1=1
            """
            params = []
            param_idx = 1
            
            # Add search conditions
            if search_term:
                query += f" AND (l.name ILIKE ${param_idx} OR l.description ILIKE ${param_idx})"
                params.append(f"%{search_term}%")
                param_idx += 1
                
            if seller_address:
                query += f" AND l.seller_address = ${param_idx}"
                params.append(seller_address)
                param_idx += 1
                
            if asset_name:
                query += f" AND EXISTS (SELECT 1 FROM listing_prices WHERE listing_id = l.id AND asset_name = ${param_idx})"
                params.append(asset_name)
                param_idx += 1
                
            if min_price_evr is not None:
                query += f" AND EXISTS (SELECT 1 FROM listing_prices WHERE listing_id = l.id AND price_evr >= ${param_idx})"
                params.append(min_price_evr)
                param_idx += 1
                
            if max_price_evr is not None:
                query += f" AND EXISTS (SELECT 1 FROM listing_prices WHERE listing_id = l.id AND price_evr <= ${param_idx})"
                params.append(max_price_evr)
                param_idx += 1
                
            if status:
                query += f" AND l.status = ${param_idx}"
                params.append(status)
                param_idx += 1
                
            # Add ordering and pagination
            query += " ORDER BY l.created_at DESC LIMIT $" + str(param_idx) + " OFFSET $" + str(param_idx + 1)
            params.extend([limit, offset])
            
            logger.debug("Executing search query: %s with params: %r", query, params)
            
            async with self.pool.acquire() as conn:
                try:
                    # Execute search query
                    rows = await conn.fetch(query, *params)
                    logger.debug("Search query returned %d base results", len(rows))
                    
                    # Get full listing details for each result
                    results = []
                    for row in rows:
                        try:
                            listing = dict(row)
                            
                            # Get prices
                            prices = await conn.fetch(
                                'SELECT * FROM listing_prices WHERE listing_id = $1',
                                listing['id']
                            )
                            listing['prices'] = [dict(p) for p in prices]
                            
                            # Get balances
                            balances = await conn.fetch(
                                'SELECT * FROM listing_balances WHERE listing_id = $1',
                                listing['id']
                            )
                            listing['balances'] = [dict(b) for b in balances]
                            
                            results.append(listing)
                        except Exception as e:
                            logger.error("Error getting details for listing %s: %s", row.get('id'), str(e))
                            continue
                    
                    logger.debug("Returning %d listings with full details", len(results))
                    return results
                    
                except Exception as e:
                    logger.exception("Database error executing search query: %s", str(e))
                    raise ListingError(f"Database error: {str(e)}")
                    
        except Exception as e:
            logger.exception("Error in search_listings: %s", str(e))
            raise

    async def update_listing_prices(
        self,
        listing_id: Union[str, uuid.UUID],
        add_or_update_prices: List[Dict[str, Any]],
        remove_asset_names: List[str] = None
    ) -> Dict[str, Any]:
        """Update, insert, or remove prices for a listing.
        
        Args:
            listing_id: The listing UUID
            add_or_update_prices: List of price specifications to add or update, each containing:
                   - asset_name: Name of asset being sold
                   - price_evr: Optional EVR price
                   - price_asset_name: Optional asset name for pricing
                   - price_asset_amount: Optional asset amount for pricing
                   - ipfs_hash: Optional IPFS hash for price-specific content
            remove_asset_names: Optional list of asset names to remove pricing for
        
        Returns:
            Updated listing details
            
        Raises:
            ListingNotFoundError: If listing doesn't exist
            ListingError: If price specification is invalid
            InvalidPriceError: If price specification is invalid or asset not found
        """
        await self.ensure_pool()
        
        try:
            # First verify the listing exists
            async with self.pool.acquire() as conn:
                exists = await conn.fetchval(
                    'SELECT EXISTS(SELECT 1 FROM listings WHERE id = $1)',
                    listing_id
                )
                if not exists:
                    raise ListingNotFoundError(f"Listing {listing_id} not found")
            
            # Start transaction for all price updates
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Handle removals first
                    if remove_asset_names:
                        # Verify assets exist in the listing before removal
                        existing_assets = await conn.fetch(
                            '''
                            SELECT asset_name 
                            FROM listing_prices 
                            WHERE listing_id = $1 AND asset_name = ANY($2)
                            ''',
                            listing_id,
                            remove_asset_names
                        )
                        existing_asset_names = {row['asset_name'] for row in existing_assets}
                        
                        # Check for non-existent assets
                        invalid_assets = set(remove_asset_names) - existing_asset_names
                        if invalid_assets:
                            raise ListingError(f"Cannot remove prices for non-existent assets: {invalid_assets}")
                        
                        # Remove prices and balances
                        await conn.execute(
                            'DELETE FROM listing_prices WHERE listing_id = $1 AND asset_name = ANY($2)',
                            listing_id,
                            remove_asset_names
                        )
                        await conn.execute(
                            'DELETE FROM listing_balances WHERE listing_id = $1 AND asset_name = ANY($2)',
                            listing_id,
                            remove_asset_names
                        )
                    
                    # Handle adds/updates
                    if add_or_update_prices:
                        # Validate all asset names first
                        for price in add_or_update_prices:
                            asset_name = price['asset_name']
                            try:
                                # Get asset data from Evrmore node
                                asset_data = getassetdata(asset_name)
                                if asset_data is None:
                                    raise InvalidPriceError(f"Asset not found: {asset_name}")
                                    
                                # If user didn't provide ipfs_hash, use the one from asset data if available
                                if not price.get('ipfs_hash') and asset_data.get('ipfs_hash'):
                                    price['ipfs_hash'] = asset_data['ipfs_hash']
                                    
                                # Validate price specification
                                price_evr = price.get('price_evr')
                                price_asset_name = price.get('price_asset_name')
                                price_asset_amount = price.get('price_asset_amount')
                                
                                if price_evr is not None:
                                    if price_asset_name is not None or price_asset_amount is not None:
                                        raise InvalidPriceError(
                                            f"Cannot specify both EVR price and asset price for {asset_name}"
                                        )
                                else:
                                    if bool(price_asset_name) != bool(price_asset_amount):
                                        raise InvalidPriceError(
                                            f"Both price_asset_name and price_asset_amount must be provided for {asset_name}"
                                        )
                                    if price_asset_name is None:
                                        raise InvalidPriceError(
                                            f"Either price_evr or asset price must be specified for {asset_name}"
                                        )
                                        
                            except InvalidPriceError:
                                raise
                            except Exception as e:
                                logger.error(f"Error validating asset {asset_name}: {e}")
                                raise InvalidPriceError(f"Failed to validate asset {asset_name}: {str(e)}")
                        
                        # Update or insert prices
                        for price in add_or_update_prices:
                            # Use upsert (INSERT ... ON CONFLICT DO UPDATE) to handle both new and existing prices
                            await conn.execute(
                                '''
                                INSERT INTO listing_prices (
                                    listing_id, asset_name, price_evr,
                                    price_asset_name, price_asset_amount, ipfs_hash
                                ) VALUES ($1, $2, $3, $4, $5, $6)
                                ON CONFLICT (listing_id, asset_name) DO UPDATE
                                SET 
                                    price_evr = EXCLUDED.price_evr,
                                    price_asset_name = EXCLUDED.price_asset_name,
                                    price_asset_amount = EXCLUDED.price_asset_amount,
                                    ipfs_hash = EXCLUDED.ipfs_hash,
                                    updated_at = now()
                                ''',
                                listing_id,
                                price['asset_name'],
                                price.get('price_evr'),
                                price.get('price_asset_name'),
                                price.get('price_asset_amount'),
                                price.get('ipfs_hash')
                            )
                            
                            # Ensure we have a balance entry for this asset
                            await conn.execute(
                                '''
                                INSERT INTO listing_balances (
                                    listing_id, asset_name, confirmed_balance,
                                    pending_balance
                                ) VALUES ($1, $2, 0, 0)
                                ON CONFLICT (listing_id, asset_name) DO NOTHING
                                ''',
                                listing_id,
                                price['asset_name']
                            )
            
            # Return updated listing details
            return await self.get_listing(listing_id)
            
        except (ListingNotFoundError, InvalidPriceError):
            # Re-raise these exceptions without wrapping
            raise
        except Exception as e:
            logger.error(f"Error updating listing prices: {e}")
            raise ListingError(f"Failed to update listing prices: {e}")

# Export public interface
__all__ = [
    'ListingManager',
    'ListingError',
    'ListingNotFoundError',
    'InvalidPriceError',
    'MUTABLE_FIELDS',
    'SYSTEM_FIELDS',
    'BALANCE_FIELDS'
] 