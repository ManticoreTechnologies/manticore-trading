"""Test the monitor module's listing balance tracking functionality."""

import asyncio
import logging
import pytest
import pytest_asyncio
from uuid import UUID

from database import init_db, close
from listings import ListingManager
from monitor import TransactionMonitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest_asyncio.fixture
async def db_pool():
    """Setup and teardown the database connection pool."""
    await init_db()
    yield
    await close()

@pytest_asyncio.fixture
async def listing_manager(db_pool):
    """Create and return a ListingManager instance."""
    return ListingManager()

@pytest_asyncio.fixture
async def monitor(db_pool):
    """Create and return a TransactionMonitor instance."""
    monitor = TransactionMonitor()
    yield monitor
    monitor.stop()

@pytest.mark.asyncio
async def test_real_listing_monitor(listing_manager, monitor):
    """Create a real listing and monitor its balance updates."""

    try:
        # Create a test listing with EVR price
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
                    'asset_name': 'CRONOS',
                    'price_evr': 75
                },
                {
                    'asset_name': 'TEST',
                    'price_evr': 100
                }
            ]
        )

        # Get the listing's deposit address
        deposit_address = await listing_manager.get_deposit_address(listing['id'])
        
        print("\n=== Test Listing Created ===")
        print(f"Listing ID: {listing['id']}")
        print(f"Deposit Address: {deposit_address}")
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