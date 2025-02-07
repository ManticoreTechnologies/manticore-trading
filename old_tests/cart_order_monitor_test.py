"""Script to test cart order creation and payment functionality."""

import asyncio
import logging
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
    """Run the cart order test."""
    
    # Initialize database and get pool
    logger.info("Initializing database connection...")
    await init_db()
    pool = await get_pool()
    payout_pool = await get_pool()  # Separate pool for payout manager
    
    try:
        # Create manager instances
        listing_manager = ListingManager(pool)
        order_manager = OrderManager(pool)
        monitor = TransactionMonitor(pool)
        payout_manager = PayoutManager(payout_pool)
        
        # Generate seller addresses
        logger.info("Generating seller addresses...")
        seller1_address = rpc_client.getnewaddress()
        seller2_address = rpc_client.getnewaddress()
        print(f"\nSeller 1 Address: {seller1_address}")
        print(f"Seller 2 Address: {seller2_address}")
        
        # Create test listings with different assets
        logger.info("\nCreating test listings...")
        
        # First listing with CRONOS
        listing1 = await listing_manager.create_listing(
            seller_address=seller1_address,
            name="Test CRONOS Listing", 
            description="Testing cart order with CRONOS",
            prices=[{
                'asset_name': 'CRONOS',
                'price_evr': 75
            }]
        )
        print(f"Created CRONOS listing: {listing1['id']}")

        # Second listing with ASTRA
        listing2 = await listing_manager.create_listing(
            seller_address=seller2_address,
            name="Test ASTRA Listing", 
            description="Testing cart order with ASTRA",
            prices=[{
                'asset_name': 'ASTRA',
                'price_evr': 100
            }]
        )
        print(f"Created ASTRA listing: {listing2['id']}")

        # Update listing balances directly for testing
        logger.info("\nUpdating listing balances...")
        async with pool.acquire() as conn:
            # Update CRONOS balance
            await conn.execute(
                '''
                UPDATE listing_balances 
                SET confirmed_balance = $1,
                    updated_at = now()
                WHERE listing_id = $2 AND asset_name = $3
                ''',
                Decimal('2.0'),
                listing1['id'],
                'CRONOS'
            )
            print("Set listing 1 balance: 2.0 CRONOS")

            # Update ASTRA balance
            await conn.execute(
                '''
                UPDATE listing_balances 
                SET confirmed_balance = $1,
                    updated_at = now()
                WHERE listing_id = $2 AND asset_name = $3
                ''',
                Decimal('3.0'),
                listing2['id'],
                'ASTRA'
            )
            print("Set listing 2 balance: 3.0 ASTRA")

        # Generate buyer address
        logger.info("\nGenerating buyer address...")
        buyer_address = rpc_client.getnewaddress()
        print(f"Buyer Address: {buyer_address}")

        # Create the cart order
        logger.info("\nCreating cart order...")
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

        # Print cart order details
        print("\n" + "="*50)
        print("                 CART ORDER RECEIPT")
        print("="*50)
        print(f"Order ID: {cart_order['id']}")
        print(f"Buyer Address: {buyer_address}")
        print(f"Date: {cart_order['created_at']}")
        print("-"*50)
        print("ITEMS")
        for item in cart_order['items']:
            print(f"\nListing: {item['listing_id']}")
            print(f"Seller Address: {item['seller_address']}")
            print(f"Asset: {item['asset_name']}")
            print(f"Amount: {item['amount']}")
            print(f"Price: {item['price_evr']:.2f} EVR")
            print(f"Fee: {item['fee_evr']:.2f} EVR")
        print("-"*50)
        print("PAYMENT DETAILS")
        print(f"Subtotal: {cart_order['total_price_evr']:.2f} EVR")
        print(f"Total Fee: {cart_order['total_fee_evr']:.2f} EVR")
        print(f"Total Due: {cart_order['total_payment_evr']:.2f} EVR")
        print(f"\nPayment Address: {cart_order['payment_address']}")
        print("="*50)

        # Start monitoring and payout processing
        logger.info("\nStarting blockchain monitor and payout processor...")
        monitor_task = asyncio.create_task(monitor.start())
        payout_task = asyncio.create_task(payout_manager.process_payouts())
        await asyncio.sleep(2)

        # Send payment
        logger.info("\nSending payment for cart order...")
        try:
            tx_hash = rpc_client.sendtoaddress(
                cart_order['payment_address'], 
                float(cart_order['total_payment_evr'])
            )
            print(f"\nPayment sent! Transaction hash: {tx_hash}")
            print("\nMonitoring order status (Ctrl+C to stop)...")
            
            while True:
                # Check order status
                updated_order = await order_manager.get_cart_order(cart_order['id'])
                balances = await order_manager.get_cart_order_balances(cart_order['id'])
                
                # Get payout info
                async with pool.acquire() as conn:
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
                
                print(f"\nOrder Status: {updated_order['status']}")
                print("EVR Balance:", balances.get('EVR', {'confirmed_balance': 0})['confirmed_balance'])
                
                # Check fulfillment status
                all_fulfilled = True
                for item in updated_order['items']:
                    status = "Fulfilled" if item.get('fulfillment_tx_hash') else "Pending"
                    print(f"{item['asset_name']}: {status}")
                    if not item.get('fulfillment_tx_hash'):
                        all_fulfilled = False
                
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
                    for sale in sales:
                        print(f"\nAsset: {sale['asset_name']}")
                        print(f"Amount: {sale['amount']}")
                        print(f"Price: {sale['price_evr']} EVR")
                        print(f"Seller: {sale['seller_address']}")
                        print(f"Buyer: {sale['buyer_address']}")
                        print(f"Time: {sale['sale_time']}")
                
                if updated_order['status'] == 'completed' and all_fulfilled:
                    print("\nCart order completed successfully!")
                    break
                    
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        except Exception as e:
            logger.error(f"Error processing payment: {e}")
        finally:
            monitor.stop()
            payout_manager.stop()
            await monitor_task
            await payout_task
            
    except Exception as e:
        logger.error(f"Test error: {e}")
        raise
    finally:
        await payout_pool.close()
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