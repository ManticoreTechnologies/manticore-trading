"""Script to test the monitor module's listing, order and sales tracking functionality."""

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
        order_manager = OrderManager(operations_pool)
        
        # Create monitor with its own pool
        monitor = TransactionMonitor(monitor_pool)
        
        # Create a test listing with CRONOS price
        logger.info("Creating test listing...")
        listing = await listing_manager.create_listing(
            seller_address="EXS1RtxtkDN1XELcHuQQw3zxYEAEDNs8Hv",
            name="Test Asset Listing", 
            description="Testing full sales cycle",
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

        # Wait for listing balance to be updated
        print("\nWaiting for listing balance to be confirmed...")
        while True:
            balances = await listing_manager.get_balances(listing['id'])
            if balances.get('CRONOS', {}).get('confirmed_balance', 0) >= 2.0:
                print("\nListing balance confirmed!")
                break
            print(".", end="", flush=True)
            await asyncio.sleep(2)

        # Create an order for 1.5 CRONOS
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

        # Send EVR payment for the order
        logger.info("\nSending EVR payment for order...")
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
            print("\nMonitoring order status, balances and sales...")
            last_sale_count = 0
            
            while True:
                # Get updated order info
                updated_order = await order_manager.get_order(order['id'])
                balances = updated_order['balances']
                
                # Get sales history for the listing
                async with operations_pool.acquire() as conn:
                    sales = await conn.fetch('''
                        SELECT 
                            asset_name,
                            amount,
                            price_evr,
                            buyer_address,
                            sale_time
                        FROM sale_history 
                        WHERE listing_id = $1 
                        ORDER BY sale_time DESC
                    ''', listing['id'])
                
                # Clear screen for better visibility
                print("\033[H\033[J")  # ANSI escape codes to clear screen
                
                print(f"\nOrder Status: {updated_order['status']}")
                print("\nOrder Balances:")
                for balance in balances:
                    print(f"{balance['asset_name']}: Confirmed={balance['confirmed_balance']}, Pending={balance['pending_balance']}")
                
                print("\nSales History:")
                if len(sales) > last_sale_count:
                    # New sales detected!
                    print("\n🎉 NEW SALE DETECTED! 🎉")
                    last_sale_count = len(sales)
                
                for sale in sales:
                    print(f"\nAsset: {sale['asset_name']}")
                    print(f"Amount: {sale['amount']}")
                    print(f"Price: {sale['price_evr']} EVR")
                    print(f"Buyer: {sale['buyer_address']}")
                    print(f"Time: {sale['sale_time']}")
                    print("-" * 30)
                
                if updated_order['status'] == 'paid' and len(sales) > 0:
                    print("\nTest completed successfully! Order paid and sale recorded.")
                    break
                    
                await asyncio.sleep(5)

        except KeyboardInterrupt:
            print("\nStopping monitor...")
        except Exception as e:
            logger.error(f"Error monitoring order and sales: {e}")
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