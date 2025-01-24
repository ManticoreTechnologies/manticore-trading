"""Script to test the monitor module's order payment tracking functionality."""

import asyncio
import logging
from uuid import UUID
from decimal import Decimal

from database import init_db, close, get_pool
from listings import ListingManager
from orders import OrderManager
from monitor import TransactionMonitor
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
    
    # Create separate pools for monitor and other operations
    monitor_pool = await get_pool()
    operations_pool = await get_pool()
    
    try:
        # Create manager instances with operations pool
        listing_manager = ListingManager(operations_pool)
        order_manager = OrderManager(operations_pool)
        
        # Create monitor with its own pool
        monitor = TransactionMonitor(monitor_pool)
        
        # Create a test listing with CRONOS price first
        logger.info("Creating test listing...")
        listing = await listing_manager.create_listing(
            seller_address="EXS1RtxtkDN1XELcHuQQw3zxYEAEDNs8Hv",
            name="Test Asset Listing", 
            description="Testing order payment tracking",
            prices=[
                {
                    'asset_name': 'CRONOS',
                    'price_evr': 75
                }
            ]
        )

        # Start the monitor first so we don't miss any transactions
        print("Starting blockchain monitor...")
        monitor_task = asyncio.create_task(monitor.start())

        # Wait a moment for monitor to initialize
        await asyncio.sleep(2)

        # First try to create an order that should fail due to no balance
        logger.info("Attempting to create order with insufficient listing balance...")
        try:
            order = await order_manager.create_order(
                listing_id=listing['id'],
                buyer_address="EXS2BuyerAddressHere",
                items=[{
                    'asset_name': 'CRONOS',
                    'amount': Decimal('1.5')
                }]
            )
            print("ERROR: Order creation should have failed!")
        except Exception as e:
            print(f"\n=== Expected Error ===")
            print(f"Order creation failed as expected: {e}")
            print("=====================\n")

        # Directly update the listing's CRONOS balance in the database
        logger.info("Updating listing balance directly in database...")
        async with operations_pool.acquire() as conn:
            await conn.execute(
                '''
                UPDATE listing_balances 
                SET confirmed_balance = $1,
                    updated_at = now()
                WHERE listing_id = $2 AND asset_name = $3
                ''',
                Decimal('2.0'),  # Set confirmed balance to 2.0 CRONOS
                listing['id'],
                'CRONOS'
            )
            print("\nUpdated listing balance: 2.0 CRONOS confirmed")

        # Now create the order with sufficient balance
        logger.info("\nCreating test order...")
        order = await order_manager.create_order(
            listing_id=listing['id'],
            buyer_address="EXS2BuyerAddressHere",
            items=[{
                'asset_name': 'CRONOS',
                'amount': Decimal('1.5')
            }]
        )

        print("\n" + "="*50)
        print("                 ORDER RECEIPT")
        print("="*50)
        print(f"Order ID: {order['id']}")
        print(f"Date: {order['created_at']}")
        print("-"*50)
        print("SELLER INFORMATION")
        print(f"Seller Address: {listing['seller_address']}")
        print(f"Listing: {listing['name']}")
        print("-"*50)
        print("BUYER INFORMATION")
        print(f"Buyer Address: {order['buyer_address']}")
        print("-"*50)
        print("ORDER DETAILS")
        for item in order['items']:
            print(f"\nItem: {item['asset_name']}")
            print(f"Amount: {item['amount']}")
            print(f"Price per unit: {item['price_evr']/item['amount']:.2f} EVR")
            print(f"Subtotal: {item['price_evr']:.2f} EVR")
            print(f"Item Fee: {item['fee_evr']:.2f} EVR")
        print("-"*50)
        print("PAYMENT INFORMATION")
        print(f"Subtotal: {order['total_price_evr']:.2f} EVR")
        print(f"Platform Fee (1%): {order['total_fee_evr']:.2f} EVR")
        print(f"Total Amount Due: {order['total_payment_evr']:.2f} EVR")
        print(f"\nPayment Address: {order['payment_address']}")
        print("="*50)
        print("Thank you for your order!")
        print("="*50 + "\n")

        # Send EVR payment for the order
        logger.info("Sending EVR payment for order...")
        try:
            # Send EVR using sendtoaddress
            tx_hash = rpc_client.sendtoaddress(order['payment_address'], float(order['total_payment_evr']))
            if tx_hash:
                print(f"\nSent {order['total_payment_evr']} EVR to order (tx: {tx_hash})")
                print("Waiting for confirmations...")
            else:
                raise Exception("Transfer failed - no transaction hash returned")
            
        except Exception as e:
            logger.error(f"Failed to send EVR: {e}")
            raise

        try:
            # Keep checking order balances until user interrupts
            while True:
                # Check order balances and status
                balances = await order_manager.get_order_balances(order['id'])
                updated_order = await order_manager.get_order(order['id'])
                
                print(f"\nCurrent Order Status: {updated_order['status']}")
                print(f"Order Balances:")
                for asset, balance in balances.items():
                    print(f"{asset}: Confirmed={balance['confirmed_balance']}, Pending={balance['pending_balance']}")
                await asyncio.sleep(5)

        except KeyboardInterrupt:
            print("\nStopping monitor...")
        except Exception as e:
            logger.error(f"Error monitoring order: {e}")
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