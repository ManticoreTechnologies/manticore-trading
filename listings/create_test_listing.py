"""Create a test listing with real addresses for testing purposes."""

import logging
from typing import Dict, Any
from decimal import Decimal
import uuid

from database import get_pool
from rpc import getnewaddress, RPCError

logger = logging.getLogger(__name__)

async def create_test_listing() -> Dict[str, Any]:
    """Create a test listing with real addresses.
    
    This function:
    1. Generates new Evrmore addresses for seller and listing
    2. Creates a test listing with sample data
    3. Sets up test prices and balances
    
    Returns:
        Dict containing the created test listing details
        
    Raises:
        RPCError: If address generation fails
        Exception: If database operations fail
    """
    try:
        # Generate new addresses using RPC
        seller_address = getnewaddress()
        listing_address = getnewaddress()
        deposit_address = getnewaddress()
        
        # Get database pool
        pool = await get_pool()
        
        # Create test listing data
        listing_id = uuid.uuid4()
        
        async with pool.acquire() as conn:
            # Insert test listing
            await conn.execute(
                '''
                INSERT INTO listings (
                    id, seller_address, listing_address, deposit_address,
                    name, description, image_ipfs_hash, tags,
                    status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ''',
                listing_id,
                seller_address,
                listing_address,
                deposit_address,
                "Test NFT Collection",
                "A collection of unique test NFTs for development and testing",
                "QmTestImageHash",
                "test,nft,development",
                "active"
            )
            
            # Add test prices
            test_prices = [
                {
                    "asset_name": "EVR",
                    "price_evr": Decimal("100.0"),
                    "units": 8
                },
                {
                    "asset_name": "TEST/ASSET",
                    "price_evr": Decimal("50.0"),
                    "units": 8
                },
                {
                    "asset_name": "TEST/NFT",
                    "price_asset_name": "EVR",
                    "price_asset_amount": Decimal("75.0"),
                    "units": 0
                }
            ]
            
            for price in test_prices:
                await conn.execute(
                    '''
                    INSERT INTO listing_prices (
                        listing_id, asset_name, price_evr,
                        price_asset_name, price_asset_amount,
                        units
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ''',
                    listing_id,
                    price["asset_name"],
                    price.get("price_evr"),
                    price.get("price_asset_name"),
                    price.get("price_asset_amount"),
                    price["units"]
                )
                
                # Initialize balance entry
                await conn.execute(
                    '''
                    INSERT INTO listing_balances (
                        listing_id, asset_name, confirmed_balance,
                        pending_balance, units
                    ) VALUES ($1, $2, 0, 0, $3)
                    ''',
                    listing_id,
                    price["asset_name"],
                    price["units"]
                )
        
        # Get full listing details to return
        from listings import ListingManager
        manager = ListingManager(pool)
        return await manager.get_listing(listing_id)
        
    except RPCError as e:
        logger.error(f"RPC error creating test listing: {e}")
        raise
    except Exception as e:
        logger.error(f"Error creating test listing: {e}")
        raise
