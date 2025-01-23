"""Script to test order creation and monitoring with pre-confirmed balances."""

import asyncio
import logging
from uuid import uuid4
from decimal import Decimal

from database import init_db, get_pool
from listings import ListingManager
from orders import OrderManager, OrderExpirationMonitor
from monitor import TransactionMonitor

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def main():
    """Run the order monitor test."""
    try:
        logger.info("Initializing database connection...")
        await init_db()
        
        # Get database pool and keep reference to prevent GC
        pool = await get_pool()
        
        try:
            # Initialize managers
            listing_manager = ListingManager(pool)
            order_manager = OrderManager(pool)
            tx_monitor = TransactionMonitor(pool)
            expiration_monitor = OrderExpirationMonitor(pool)
            
            # Start monitors
            logger.info("Starting blockchain monitor...")
            monitor_task = asyncio.create_task(tx_monitor.start())
            
            logger.info("Starting order expiration monitor...")
            await expiration_monitor.start()
            
            await asyncio.sleep(2)  # Wait for monitors to initialize
            
            # Create test listing
            logger.info("Creating test listing...")
            listing = await listing_manager.create_listing(
                "EVRSellerAddressGoesHere",  # seller_address
                "Test Listing",  # name
                "Testing order expiration",  # description
                None,  # image_ipfs_hash
                [{"asset_name": "CRONOS", "price_evr": Decimal("2.0")}]  # price as Decimal
            )
            listing_id = listing['id']
            
            logger.info("Setting initial confirmed balance...")
            # Set initial confirmed balance
            await listing_manager.update_listing_balance(
                listing_id,
                "CRONOS",
                confirmed_delta=Decimal("2.0"),
                pending_delta=Decimal("0")
            )
            
            logger.info("Creating test order...")
            # Create order that will expire in 1 minute
            order = await order_manager.create_order(
                listing_id=listing_id,
                buyer_address="EVRBuyerAddressGoesHere",
                items=[{"asset_name": "CRONOS", "amount": Decimal("1.0")}]
            )
            
            logger.info(f"Created order {order['id']}, waiting for expiration...")
            
            # Monitor order status until it expires or Ctrl+C
            try:
                while True:
                    order = await order_manager.get_order(order['id'])
                    logger.info(f"Order status: {order['status']}")
                    
                    # Get and display current balances
                    balances = await listing_manager.get_balances(listing_id)
                    print(f"\nCurrent Balances for listing {listing_id}:")
                    for asset, balance in balances.items():
                        print(f"{asset}: Confirmed={balance['confirmed_balance']}, Pending={balance['pending_balance']}")
                    
                    # Get and display order payment address balance
                    order_balance = await order_manager.get_order_balance(order['id'])
                    print(f"\nOrder Payment Address Balance:")
                    for asset, balance in order_balance.items():
                        print(f"{asset}: {balance}")
                    
                    if order['status'] == 'expired':
                        break
                    await asyncio.sleep(10)
            except KeyboardInterrupt:
                logger.info("Test interrupted")
            
            # Stop monitors
            await expiration_monitor.stop()
            tx_monitor.stop()
            await monitor_task
            
        finally:
            # Close pool in finally block
            logger.info("Closing database pool...")
            await pool.close()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 