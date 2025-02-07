"""Script to test the monitor module's order payment tracking functionality."""

import asyncio
import logging
from uuid import UUID
from decimal import Decimal

from database import init_db, close, get_pool
from listings import ListingManager
from orders import OrderManager, PayoutManager
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
    payout_pool = await get_pool()
    
    try:
        # Create manager instances with operations pool
        listing_manager = ListingManager(operations_pool)
        order_manager = OrderManager(operations_pool)
        
        # Create monitor and payout manager with their own pools
        monitor = TransactionMonitor(monitor_pool)
        payout_manager = PayoutManager(payout_pool)
        
        # Generate seller address
        logger.info("Generating seller address...")
        seller_address = rpc_client.getnewaddress()
        print(f"\nSeller Address: {seller_address}")
        
        # Create a test listing with CRONOS price
        logger.info("Creating test listing...")
        listing = await listing_manager.create_listing(
            seller_address=seller_address,
            name="Test Asset Listing", 
            description="Testing order payment tracking",
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

        # Start the monitor and payout processor
        print("Starting blockchain monitor and payout processor...")
        monitor_task = asyncio.create_task(monitor.start())
        payout_task = asyncio.create_task(payout_manager.process_payouts())

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

        # Generate buyer address
        logger.info("\nGenerating buyer address...")
        buyer_address = rpc_client.getnewaddress()
        print(f"Buyer Address: {buyer_address}")

        # First try to create an order that should fail due to no balance
        logger.info("Attempting to create order with insufficient listing balance...")
        try:
            order = await order_manager.create_order(
                listing_id=listing['id'],
                buyer_address=buyer_address,
                items=[{
                    'asset_name': 'CRONOS',
                    'amount': Decimal('2.5')  # More than available
                }]
            )
            print("ERROR: Order creation should have failed!")
        except Exception as e:
            print(f"\n=== Expected Error ===")
            print(f"Order creation failed as expected: {e}")
            print("=====================\n")

        # Now create a valid order for 1.5 CRONOS
        logger.info("\nCreating test order...")
        order = await order_manager.create_order(
            listing_id=listing['id'],
            buyer_address=buyer_address,
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
        print(f"Seller Address: {seller_address}")
        print(f"Listing: {listing['name']}")
        print("-"*50)
        print("BUYER INFORMATION")
        print(f"Buyer Address: {buyer_address}")
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
            print("\nMonitoring order status, balances, payouts and sales...")
            last_sale_count = 0
            
            while True:
                # Get updated order info
                updated_order = await order_manager.get_order(order['id'])
                order_balances = await order_manager.get_order_balances(order['id'])
                listing_balances = await listing_manager.get_balances(listing['id'])
                
                # Get payout and sales info
                async with operations_pool.acquire() as conn:
                    # Check payout status
                    payout = await conn.fetchrow('''
                        SELECT 
                            success,
                            failure_count,
                            total_fees_paid,
                            completed_at
                        FROM order_payouts 
                        WHERE order_id = $1
                    ''', order['id'])
                    
                    # Get sales history
                    sales = await conn.fetch('''
                        SELECT 
                            asset_name,
                            amount,
                            price_evr,
                            seller_address,
                            buyer_address,
                            sale_time
                        FROM sale_history 
                        WHERE order_id = $1
                        ORDER BY sale_time DESC
                    ''', order['id'])
                
                # Clear screen for better visibility
                print("\033[H\033[J")  # ANSI escape codes to clear screen
                
                print(f"\nOrder Status: {updated_order['status']}")
                
                print("\nOrder Payment Balances:")
                for asset, balance in order_balances.items():
                    print(f"{asset}: Confirmed={balance['confirmed_balance']}, Pending={balance['pending_balance']}")
                
                print("\nListing Asset Balances:")
                for asset, balance in listing_balances.items():
                    print(f"{asset}: Confirmed={balance['confirmed_balance']}, Pending={balance['pending_balance']}")
                
                if payout:
                    print("\nPayout Status:")
                    print(f"Success: {payout['success']}")
                    print(f"Attempts: {payout['failure_count']}")
                    if payout['total_fees_paid']:
                        print(f"Fees Paid: {payout['total_fees_paid']} EVR")
                    if payout['completed_at']:
                        print(f"Completed: {payout['completed_at']}")
                
                if sales:
                    print("\nSales History:")
                    if len(sales) > last_sale_count:
                        print("\n🎉 NEW SALE RECORDED! 🎉")
                        last_sale_count = len(sales)
                    
                    for sale in sales:
                        print(f"\nAsset: {sale['asset_name']}")
                        print(f"Amount: {sale['amount']}")
                        print(f"Price: {sale['price_evr']} EVR")
                        print(f"Seller: {sale['seller_address']}")
                        print(f"Buyer: {sale['buyer_address']}")
                        print(f"Time: {sale['sale_time']}")
                        print("-" * 30)
                
                # Check if order is complete
                if (updated_order['status'] == 'completed' and 
                    payout and payout['success'] and 
                    len(sales) > 0):
                    print("\n🎉 Test completed successfully! 🎉")
                    print("- Order payment received and confirmed")
                    print("- Assets transferred to buyer")
                    print("- Payment sent to seller")
                    print("- Sale recorded in history")
                    break
                    
                await asyncio.sleep(5)

        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        except Exception as e:
            logger.error(f"Error monitoring order: {e}")
        finally:
            # Stop services
            monitor.stop()
            payout_manager.stop()
            await monitor_task
            await payout_task
            
    except Exception as e:
        logger.error(f"Error in test: {e}")
        raise
    finally:
        # Cleanup database connections in reverse order
        logger.info("Closing database connections...")
        await payout_pool.close()
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