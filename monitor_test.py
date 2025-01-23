"""Script to test the monitor module's listing balance tracking functionality."""

import asyncio
import logging
from uuid import UUID

from database import init_db, close
from listings import ListingManager
from monitor import TransactionMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Run the monitor test."""
    
    # Initialize database
    logger.info("Initializing database connection...")
    await init_db()
    
    try:
        # Create manager instances
        listing_manager = ListingManager()
        monitor = TransactionMonitor()
        
        # Create a test listing with EVR price
        logger.info("Creating test listing...")
        listing = await listing_manager.create_listing(
            seller_address="EXS1RtxtkDN1XELcHuQQw3zxYEAEDNs8Hv",
            name="Test Asset Listing", 
            description="Testing real balance updates",
            prices=[
                {
                    'asset_name': 'EVR',
                    'price_evr': 50
                },
                {
                    'asset_name': 'TEST',
                    'price_evr': 100
                }
            ]
        )

        # Get the EVR deposit address
        deposit_addresses = await listing_manager.get_deposit_addresses(listing['id'])
        evr_address = deposit_addresses['EVR']
        
        print("\n=== Test Listing Created ===")
        print(f"Listing ID: {listing['id']}")
        print(f"EVR Deposit Address: {evr_address}")
        print("===========================\n")

        # Start the monitor
        print("Starting blockchain monitor...")
        monitor_task = asyncio.create_task(monitor.start())

        try:
            # Keep checking balances until user interrupts
            while True:
                balances = await listing_manager.get_balances(listing['id'])
                print(f"\nCurrent Balances for listing {listing['id']}:")
                for asset, balance in balances.items():
                    print(f"{asset}: Confirmed={balance['confirmed_balance']}, Pending={balance['pending_balance']}")
                await asyncio.sleep(5)

        except KeyboardInterrupt:
            print("\nStopping monitor...")
        except Exception as e:
            logger.error(f"Error monitoring balances: {e}")
        finally:
            monitor.stop()
            await monitor_task
            
    except Exception as e:
        logger.error(f"Error in test: {e}")
        raise
    finally:
        # Cleanup database connection
        logger.info("Closing database connection...")
        await close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 