"""Script to test the monitor module's listing balance tracking functionality."""

import asyncio
import logging
from uuid import UUID
from decimal import Decimal

from database import init_db, close, get_pool
from listings import ListingManager
from monitor import TransactionMonitor
from rpc import client as rpc_client


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Run the monitor test."""
    
    # Initialize database and get pool - keep reference to prevent GC
    logger.info("Initializing database connection...")
    await init_db()
    
    # Create separate pools for monitor and other operations
    monitor_pool = await get_pool()
    operations_pool = await get_pool()
    
    try:
        # Create manager instances with operations pool
        listing_manager = ListingManager(operations_pool)
        
        # Create monitor with its own pool
        monitor = TransactionMonitor(monitor_pool)
        
        # Create a test listing with just CRONOS price
        logger.info("Creating test listing...")
        listing = await listing_manager.create_listing(
            seller_address="EXS1RtxtkDN1XELcHuQQw3zxYEAEDNs8Hv",
            name="Test Asset Listing", 
            description="Testing balance tracking",
            prices=[
                {
                    'asset_name': 'CRONOS',
                    'price_evr': 75
                }
            ]
        )

        # Get the listing's deposit address
        deposit_address = await listing_manager.get_deposit_address(listing['id'])
        
        print("\n=== Test Listing Created ===")
        print(f"Listing ID: {listing['id']}")
        print(f"Deposit Address: {deposit_address}")
        print("===========================\n")

        # Start the monitor first so we don't miss any transactions
        print("Starting blockchain monitor...")
        monitor_task = asyncio.create_task(monitor.start())

        # Wait a moment for monitor to initialize
        await asyncio.sleep(2)

        # Send some CRONOS to the listing
        logger.info("Sending CRONOS to listing...")
        try:
            # The RPC call returns the transaction hash directly
            tx_hash = rpc_client.transfer("CRONOS", 2.0, deposit_address)
            if tx_hash:
                print(f"\nSent 2.0 CRONOS to listing (tx: {tx_hash})")
                print("Waiting for confirmations...")
            else:
                raise Exception("Transfer failed - no transaction hash returned")
            
        except Exception as e:
            logger.error(f"Failed to send CRONOS: {e}")
            raise

        try:
            # Keep checking balances until user interrupts
            while True:
                # Check listing balances
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
        # Cleanup database connections in reverse order
        logger.info("Closing database connections...")
        await monitor_pool.close()
        await operations_pool.close()
        await close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 