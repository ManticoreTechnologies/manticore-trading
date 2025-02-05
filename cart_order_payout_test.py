"""Script to test the complete cart order lifecycle including payouts.

This test demonstrates:
1. Creating multiple listings with different assets and generated seller addresses
2. Depositing assets to the listings
3. Creating a cart order with generated buyer address
4. Processing payment for all items at once
5. Handling payouts to sellers
"""

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
    """Run the cart order payout test."""
    
    # Initialize database and get pool
    logger.info("Initializing database connection...")
    await init_db()
    
    # Create separate pools for monitor, payout and other operations
    monitor_pool = await get_pool()
    payout_pool = await get_pool()
    operations_pool = await get_pool()
    
    try:
        # Create manager instances with operations pool
        listing_manager = ListingManager(operations_pool)
        order_manager = OrderManager(operations_pool)
        payout_manager = PayoutManager(payout_pool)
        
        # Create monitor with its own pool
        monitor = TransactionMonitor(monitor_pool)
        
        # Generate seller addresses
        seller1_address = rpc_client.getnewaddress()
        seller2_address = rpc_client.getnewaddress()
        logger.info(f"Generated seller addresses:\nSeller 1: {seller1_address}\nSeller 2: {seller2_address}")
        
        # Create test listings with different assets and sellers
        logger.info("Creating test listings...")
        
        # First listing with CRONOS
        listing1 = await listing_manager.create_listing(
            seller_address=seller1_address,
            name="CRONOS Store", 
            description="Testing cart order with CRONOS",
            prices=[
                {
                    'asset_name': 'CRONOS',
                    'price_evr': 75
                }
            ]
        )
        deposit1 = await listing_manager.get_deposit_address(listing1['id'])

        # Second listing with ASTRA
        listing2 = await listing_manager.create_listing(
            seller_address=seller2_address,
            name="ASTRA Store", 
            description="Testing cart order with ASTRA",
            prices=[
                {
                    'asset_name': 'ASTRA',
                    'price_evr': 100
                }
            ]
        )
        deposit2 = await listing_manager.get_deposit_address(listing2['id'])

        print("\n=== Test Listings Created ===")
        print(f"Listing 1 (CRONOS):")
        print(f"  ID: {listing1['id']}")
        print(f"  Deposit: {deposit1}")
        print(f"  Seller: {seller1_address}")
        print(f"\nListing 2 (ASTRA):")
        print(f"  ID: {listing2['id']}")
        print(f"  Deposit: {deposit2}")
        print(f"  Seller: {seller2_address}")
        print("===========================\n")

        # Start the monitor and payout processor
        print("Starting blockchain monitor and payout processor...")
        monitor_task = asyncio.create_task(monitor.start())
        payout_task = asyncio.create_task(payout_manager.process_payouts())

        # Wait a moment for services to initialize
        await asyncio.sleep(2)

        # Send assets to the listings
        logger.info("Sending assets to listings...")
        try:
            # Send CRONOS to listing 1
            tx_hash1 = rpc_client.transfer(
                "CRONOS",  # Asset name
                2.0,      # Amount
                deposit1,  # To address
                "",       # Message
                0,        # Expire time
                "",      # Change address
                ""       # Asset change address
            )
            if isinstance(tx_hash1, list):
                tx_hash1 = tx_hash1[0]
            print(f"\nSent 2.0 CRONOS to listing 1 (tx: {tx_hash1})")
            
            # Send ASTRA to listing 2
            tx_hash2 = rpc_client.transfer(
                "ASTRA",  # Asset name
                3.0,      # Amount
                deposit2,  # To address
                "",       # Message
                0,        # Expire time
                "",      # Change address
                ""       # Asset change address
            )
            if isinstance(tx_hash2, list):
                tx_hash2 = tx_hash2[0]
            print(f"Sent 3.0 ASTRA to listing 2 (tx: {tx_hash2})")
            print("\nWaiting for confirmations...")
            
        except Exception as e:
            logger.error(f"Failed to send assets: {e}")
            raise

        # Wait for listing balances to be confirmed
        print("\nWaiting for listing balances to be confirmed...")
        while True:
            balances1 = await listing_manager.get_balances(listing1['id'])
            balances2 = await listing_manager.get_balances(listing2['id'])
            
            cronos_confirmed = balances1.get('CRONOS', {}).get('confirmed_balance', 0) >= 2.0
            astra_confirmed = balances2.get('ASTRA', {}).get('confirmed_balance', 0) >= 3.0
            
            if cronos_confirmed and astra_confirmed:
                print("\nAll listing balances confirmed!")
                break
                
            print(".", end="", flush=True)
            await asyncio.sleep(2)

        # Generate buyer address
        buyer_address = rpc_client.getnewaddress()
        logger.info(f"Generated buyer address: {buyer_address}")

        # Create a cart order for both items
        logger.info("\nCreating test cart order...")
        cart_order = await order_manager.create_cart_order(
            buyer_address=buyer_address,
            items=[
                {
                    'listing_id': listing1['id'],
                    'asset_name': 'CRONOS',
                    'amount': Decimal('1.5')
                },
                {
                    'listing_id': listing2['id'],
                    'asset_name': 'ASTRA',
                    'amount': Decimal('2.0')
                }
            ]
        )

        # Print cart receipt
        print("\n" + "="*50)
        print("                 CART ORDER RECEIPT")
        print("="*50)
        print(f"Order ID: {cart_order['id']}")
        print(f"Date: {cart_order['created_at']}")
        print("-"*50)
        print("ITEMS")

        total_price_evr = Decimal('0')
        total_fee_evr = Decimal('0')

        for item in cart_order['items']:
            seller_address = seller1_address if item['listing_id'] == listing1['id'] else seller2_address
            listing_name = "CRONOS Store" if item['listing_id'] == listing1['id'] else "ASTRA Store"
            print(f"\nListing: {listing_name}")
            print(f"Seller: {seller_address}")
            print(f"Asset: {item['asset_name']}")
            print(f"Amount: {item['amount']}")
            print(f"Price per unit: {item['price_evr']/item['amount']:.2f} EVR")
            print(f"Subtotal: {item['price_evr']:.2f} EVR")
            print(f"Item Fee: {item['fee_evr']:.2f} EVR")
            total_price_evr += item['price_evr']
            total_fee_evr += item['fee_evr']

        print("-"*50)
        print("PAYMENT INFORMATION")
        print(f"Subtotal: {total_price_evr:.2f} EVR")
        print(f"Total Platform Fee: {total_fee_evr:.2f} EVR")
        print(f"Total Amount Due: {(total_price_evr + total_fee_evr):.2f} EVR")
        print(f"\nPayment Address: {cart_order['payment_address']}")
        print("="*50)

        # Send EVR payment for the cart order
        logger.info("\nSending EVR payment for cart order...")
        try:
            tx_hash = rpc_client.sendtoaddress(
                cart_order['payment_address'], 
                float(cart_order['total_payment_evr'])
            )
            print(f"\nSent {cart_order['total_payment_evr']} EVR to cart order (tx: {tx_hash})")
            print("Waiting for confirmations and payout processing...")
            
        except Exception as e:
            logger.error(f"Failed to send EVR: {e}")
            raise

        try:
            print("\nMonitoring cart order status, balances, and payouts...")
            last_status = None
            
            while True:
                # Get updated cart order info
                updated_order = await order_manager.get_cart_order(cart_order['id'])
                balances = await order_manager.get_cart_order_balances(cart_order['id'])
                
                # Get payout info
                async with operations_pool.acquire() as conn:
                    payout = await conn.fetchrow('''
                        SELECT 
                            success,
                            failure_count,
                            total_fees_paid,
                            completed_at
                        FROM cart_order_payouts 
                        WHERE cart_order_id = $1
                    ''', cart_order['id'])
                    
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
                        WHERE cart_order_id = $1
                        ORDER BY sale_time DESC
                    ''', cart_order['id'])
                
                # Only print if status changed
                if updated_order['status'] != last_status:
                    print(f"\nCart Order Status: {updated_order['status']}")
                    
                    print("\nOrder Balances:")
                    for asset, balance in balances.items():
                        print(f"{asset}: Confirmed={balance['confirmed_balance']}, Pending={balance['pending_balance']}")
                    
                    if payout:
                        print("\nPayout Status:")
                        print(f"Success: {payout['success']}")
                        print(f"Attempts: {payout['failure_count']}")
                        if payout['total_fees_paid']:
                            print(f"Fees Paid: {payout['total_fees_paid']} EVR")
                        if payout['completed_at']:
                            print(f"Completed: {payout['completed_at']}")
                    
                    print("\nFulfillment Status:")
                    for item in updated_order['items']:
                        status = "Fulfilled" if item.get('fulfillment_tx_hash') else "Pending"
                        print(f"{item['asset_name']}: {status}")
                        if item.get('fulfillment_tx_hash'):
                            print(f"  TX Hash: {item['fulfillment_tx_hash']}")
                            print(f"  Time: {item.get('fulfillment_time')}")
                    
                    if sales:
                        print("\nSales History:")
                        for sale in sales:
                            print(f"\nAsset: {sale['asset_name']}")
                            print(f"Amount: {sale['amount']}")
                            print(f"Price: {sale['price_evr']} EVR")
                            print(f"Seller: {sale['seller_address']}")
                            print(f"Buyer: {sale['buyer_address']}")
                            print(f"Time: {sale['sale_time']}")
                    
                    last_status = updated_order['status']
                
                if updated_order['status'] == 'completed':
                    print("\n🎉 Cart order completed successfully! 🎉")
                    print("Assets transferred to buyer and EVR sent to sellers")
                    break
                    
                await asyncio.sleep(2)

        except KeyboardInterrupt:
            print("\nStopping services...")
        except Exception as e:
            logger.error(f"Error monitoring cart order: {e}")
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
        await monitor_pool.close()
        await payout_pool.close()
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