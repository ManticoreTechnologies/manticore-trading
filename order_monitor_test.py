"""Script to test order creation and monitoring with pre-confirmed balances."""

import asyncio
import logging
from uuid import UUID
from decimal import Decimal

from database import init_db, close, get_pool
from listings import ListingManager
from monitor import TransactionMonitor
from orders import OrderManager
from rpc import client as rpc_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Run the order monitor test."""
    
    # Initialize database and get pool - keep reference to prevent GC
    logger.info("Initializing database connection...")
    await init_db()
    
    # Create a single pool for all operations
    pool = await get_pool()
    
    try:
        # Create manager instances with the same pool
        listing_manager = ListingManager(pool)
        order_manager = OrderManager(pool)
        monitor = TransactionMonitor(pool)
        
        # Start monitor first
        print("Starting blockchain monitor...")
        monitor_task = asyncio.create_task(monitor.start())
        
        # Wait a moment for monitor to initialize
        await asyncio.sleep(2)
        
        # Create a test listing with EVR and asset prices
        logger.info("Creating test listing...")
        listing = await listing_manager.create_listing(
            seller_address="EXS1RtxtkDN1XELcHuQQw3zxYEAEDNs8Hv",
            name="Test Asset Listing", 
            description="Testing order creation and monitoring",
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

        # Set initial confirmed balance for CRONOS
        logger.info("Setting initial confirmed balance...")
        await listing_manager.update_listing_balance(
            listing_id=listing['id'],
            asset_name='CRONOS',
            confirmed_delta=Decimal('2.0'),
            tx_hash='dummy_tx_hash'
        )

        # Create the order
        logger.info("Creating test order...")
        order = await order_manager.create_order(
            listing_id=listing['id'],
            buyer_address="EXS2RtxtkDN1XELcHuQQw3zxYEAEDNs8Hv",  # Test buyer address
            items=[
                {
                    'asset_name': 'CRONOS',
                    'amount': Decimal('1.0')
                }
            ]
        )

        print("\n=== Test Order Created ===")
        print(f"Order ID: {order['id']}")
        print(f"Total Price: {order['total_price_evr']} EVR")
        print(f"Payment Address: {order['payment_address']}")
        print("=========================\n")

        try:
            # Keep checking balances and order status until user interrupts
            while True:
                # Check listing balances
                balances = await listing_manager.get_balances(listing['id'])
                print(f"\nCurrent Balances for listing {listing['id']}:")
                for asset, balance in balances.items():
                    print(f"{asset}: Confirmed={balance['confirmed_balance']}, Pending={balance['pending_balance']}")
                
                # Check order status
                order_status = await order_manager.get_order(order['id'])
                print(f"\nOrder Status:")
                print(f"Status: {order_status['status']}")
                if order_status['status'] == 'completed':
                    print("Order has been fulfilled!")
                    break
                
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
        # Close the single pool
        logger.info("Closing database connection...")
        await pool.close()
        await close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 