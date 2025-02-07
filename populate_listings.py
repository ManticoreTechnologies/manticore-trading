"""Script to populate the marketplace with test listings using Astra and Cronos assets.

This script creates multiple listings with:
- Different asset combinations (Astra and Cronos)
- Various price points
- Tags for categorization
- Descriptive metadata
- Multiple seller addresses
"""

import asyncio
import logging
from decimal import Decimal
from typing import List, Dict, Any

from database import init_db, close, get_pool
from listings import ListingManager
from rpc import client as rpc_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test data for listings
LISTINGS_DATA = [
    {
        "name": "Premium Astra Collection",
        "description": "High-value Astra assets for serious collectors",
        "tags": ["premium", "astra", "collection", "rare"],
        "prices": [
            {
                "asset_name": "ASTRA",
                "price_evr": 150
            }
        ]
    },
    {
        "name": "Credits Starter Pack",
        "description": "Perfect for getting started with Credits assets",
        "tags": ["starter", "credits", "beginner", "bundle"],
        "prices": [
            {
                "asset_name": "CREDITS",
                "price_evr": 50
            }
        ]
    },
    {
        "name": "Astra & Credits Bundle",
        "description": "Best of both worlds - get both assets at a great price",
        "tags": ["bundle", "astra", "credits", "combo", "deal"],
        "prices": [
            {
                "asset_name": "ASTRA",
                "price_evr": 120
            },
            {
                "asset_name": "CREDITS",
                "price_evr": 45
            }
        ]
    },
    {
        "name": "Bulk Credits Package",
        "description": "Large quantity of Credits at wholesale prices",
        "tags": ["bulk", "credits", "wholesale", "discount"],
        "prices": [
            {
                "asset_name": "CREDITS",
                "price_evr": 40
            }
        ]
    },
    {
        "name": "Limited Edition Astra",
        "description": "Exclusive Astra offering with premium support",
        "tags": ["limited", "astra", "exclusive", "premium"],
        "prices": [
            {
                "asset_name": "ASTRA",
                "price_evr": 200
            }
        ]
    },
    {
        "name": "Credits Pro Pack",
        "description": "Professional grade Credits assets with documentation",
        "tags": ["pro", "credits", "professional", "documentation"],
        "prices": [
            {
                "asset_name": "CREDITS",
                "price_evr": 75
            }
        ]
    },
    {
        "name": "Astra Trading Set",
        "description": "Perfect for traders - includes market analysis",
        "tags": ["trading", "astra", "analysis", "market"],
        "prices": [
            {
                "asset_name": "ASTRA",
                "price_evr": 160
            }
        ]
    },
    {
        "name": "Credits Development Kit",
        "description": "Complete toolkit for Credits developers",
        "tags": ["development", "credits", "toolkit", "technical"],
        "prices": [
            {
                "asset_name": "CREDITS",
                "price_evr": 85
            }
        ]
    }
]

async def create_listing_with_balance(
    listing_manager: ListingManager,
    seller_address: str,
    listing_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a listing and set its initial balance for testing.
    
    Args:
        listing_manager: The listing manager instance
        seller_address: Address of the seller
        listing_data: Data for the listing
        
    Returns:
        The created listing details
    """
    # Create the listing
    listing = await listing_manager.create_listing(
        seller_address=seller_address,
        name=listing_data["name"],
        description=listing_data["description"],
        prices=listing_data["prices"],
        tags=",".join(listing_data["tags"])  # Convert list to comma-separated string
    )
    
    # Get deposit address
    deposit_address = await listing_manager.get_deposit_address(listing['id'])
    
    # Send assets to the listing
    for price in listing_data["prices"]:
        asset_name = price["asset_name"]
        # Send 5 units of each asset for testing
        amount = 5.0
        
        try:
            tx_hash = rpc_client.transfer(
                asset_name,  # Asset name
                amount,     # Amount
                deposit_address,  # To address
                "",       # Message
                0,        # Expire time
                "",      # Change address
                ""       # Asset change address
            )
            if isinstance(tx_hash, list):
                tx_hash = tx_hash[0]
            logger.info(f"Sent {amount} {asset_name} to listing {listing['id']} (tx: {tx_hash})")
            
        except Exception as e:
            logger.error(f"Failed to send {asset_name}: {e}")
            raise
    
    return listing

async def main():
    """Create multiple test listings with various assets and tags."""
    
    # Initialize database
    logger.info("Initializing database connection...")
    await init_db()
    pool = await get_pool()
    
    try:
        # Create listing manager
        listing_manager = ListingManager(pool)
        
        # Generate seller addresses (one for every two listings)
        num_sellers = (len(LISTINGS_DATA) + 1) // 2
        seller_addresses = []
        
        logger.info(f"Generating {num_sellers} seller addresses...")
        for i in range(num_sellers):
            address = rpc_client.getnewaddress()
            seller_addresses.append(address)
            logger.info(f"Generated seller {i+1} address: {address}")
        
        # Create all listings
        logger.info("\nCreating listings...")
        created_listings = []
        
        for i, listing_data in enumerate(LISTINGS_DATA):
            # Use seller addresses round-robin
            seller_address = seller_addresses[i % len(seller_addresses)]
            
            try:
                listing = await create_listing_with_balance(
                    listing_manager,
                    seller_address,
                    listing_data
                )
                created_listings.append(listing)
                
                print(f"\nCreated Listing {i+1}:")
                print(f"ID: {listing['id']}")
                print(f"Name: {listing['name']}")
                print(f"Seller: {seller_address}")
                print(f"Tags: {listing_data['tags']}")  # Show original list for better readability
                print("Prices:")
                for price in listing_data["prices"]:
                    print(f"  {price['asset_name']}: {price['price_evr']} EVR")
                
            except Exception as e:
                logger.error(f"Failed to create listing {listing_data['name']}: {e}")
                continue
        
        print("\nWaiting for listing balances to be confirmed...")
        confirmed_count = 0
        
        while confirmed_count < len(created_listings):
            confirmed_count = 0
            
            for listing in created_listings:
                balances = await listing_manager.get_balances(listing['id'])
                all_confirmed = True
                
                for price in listing['prices']:
                    asset_name = price['asset_name']
                    if balances.get(asset_name, {}).get('confirmed_balance', 0) < 5.0:
                        all_confirmed = False
                        break
                
                if all_confirmed:
                    confirmed_count += 1
            
            print(f"\rConfirmed: {confirmed_count}/{len(created_listings)}", end="", flush=True)
            await asyncio.sleep(2)
        
        print("\n\nAll listings created and funded successfully!")
        print("\nSummary:")
        print(f"Total Listings: {len(created_listings)}")
        print(f"Total Sellers: {len(seller_addresses)}")
        print("\nUnique Tags:")
        all_tags = set()
        for data in LISTINGS_DATA:
            all_tags.update(data['tags'])
        print(", ".join(sorted(all_tags)))
        
    except Exception as e:
        logger.error(f"Error in populate script: {e}")
        raise
    finally:
        await pool.close()
        await close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPopulation interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 