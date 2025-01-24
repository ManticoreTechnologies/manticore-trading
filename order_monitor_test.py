"""Script to test order creation and monitoring with pre-confirmed balances."""

import asyncio
import logging
from uuid import uuid4
from decimal import Decimal

from database import init_db, get_pool
from listings import ListingManager
from orders import OrderManager
from monitor import TransactionMonitor
from rpc import client as rpc_client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def print_balances(listing_balances, order_balances):
    """Print balances in a clear format."""
    print("\nListing Balances:")
    print("-" * 50)
    for asset, balance in listing_balances.items():
        print(f"{asset}: Confirmed={balance['confirmed_balance']}")
    
    print("\nOrder Balances:")
    print("-" * 50)
    for asset, balance in order_balances.items():
        print(f"{asset}: Confirmed={balance['confirmed_balance']}")
    print("-" * 50)

async def main():
    """Run the test."""
    logger.info("Initializing database connection...")
    await init_db()
    pool = await get_pool()
    
    # Create managers
    listing_manager = ListingManager(pool)
    order_manager = OrderManager(pool)
    monitor = TransactionMonitor(pool)
    
    # Start monitor
    logger.info("Starting blockchain monitor...")
    monitor_task = asyncio.create_task(monitor.start())
    
    try:
        # Create test listing
        logger.info("Creating test listing...")
        listing = await listing_manager.create_listing(
            seller_address="EVRSellerAddressGoesHere",
            name="Test Listing",
            description="A test listing",
            prices=[{
                "asset_name": "CRONOS",
                "price_evr": Decimal("10.0")
            }]
        )
        listing_id = listing['id']
        deposit_address = listing['deposit_address']
        
        # Send CRONOS to listing
        logger.info("Sending CRONOS to listing...")
        print(f"\nSending 2.0 CRONOS to listing...")
        tx_hash = rpc_client.transfer(
            "CRONOS",
            2.0,
            deposit_address
        )
        print(f"Sent 2.0 CRONOS to listing (tx: {[tx_hash]})")
        print("Waiting for confirmations...")
        
        # Wait for initial balance to show up
        while True:
            balances = await listing_manager.get_balances(listing_id)
            print(f"\nCurrent Balances for listing {listing_id}:")
            for asset, balance in balances.items():
                print(f"{asset}: Confirmed={balance['confirmed_balance']}")
            
            if balances.get('CRONOS', {}).get('confirmed_balance', Decimal('0')) >= Decimal('2.0'):
                break
            await asyncio.sleep(5)
        
        logger.info("Creating test order...")
        order = await order_manager.create_order(
            listing_id=listing_id,
            buyer_address="EVRBuyerAddressGoesHere",
            items=[{
                "asset_name": "CRONOS", 
                "amount": Decimal("1.0")
            }]
        )
        
        logger.info(f"Created order {order['id']}, monitoring status...")
        
        # Monitor order status until completion or Ctrl+C
        try:
            # Get total payment amount needed
            payment_amount = float(order['total_payment_evr'])
            logger.info(f"Required payment: {payment_amount} EVR")
            
            try:
                tx_hash = rpc_client.sendtoaddress(order['payment_address'], payment_amount)
                logger.info(f"Payment sent in transaction {tx_hash}")
            except Exception as e:
                logger.error(f"Failed to send payment: {e}")
                logger.info("Continuing test without payment...")
            
            while True:
                order = await order_manager.get_order(order['id'])
                logger.info(f"Order status: {order['status']}")
                logger.info(f"Total price: {order['total_price_evr']} EVR")
                logger.info(f"Total fee: {order['total_fee_evr']} EVR")
                logger.info(f"Required payment: {order['total_payment_evr']} EVR")
                
                # Get and display current balances
                listing_balances = await listing_manager.get_balances(listing_id)
                order_balances = await order_manager.get_order_balances(order['id'])
                
                print_balances(listing_balances, order_balances)
                
                if order['status'] in ('paid', 'completed', 'cancelled', 'refunded'):
                    logger.info(f"Order reached final status: {order['status']}")
                    break
                    
                await asyncio.sleep(10)
                
        except KeyboardInterrupt:
            logger.info("Test interrupted")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
    finally:
        # Clean up
        logger.info("Cleaning up...")
        # First stop the monitor
        monitor.stop()
        # Wait for monitor task to complete
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        # Finally close the pool
        await pool.close()

if __name__ == '__main__':
    asyncio.run(main()) 