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


def print_header(text: str, char: str = "=", width: int = 50):
    """Print a centered header with decorative borders."""
    print(f"\n{char * width}")
    print(f"{text:^{width}}")
    print(f"{char * width}\n")


def print_section(text: str, char: str = "-", width: int = 50):
    """Print a section divider with text."""
    print(f"\n{char * width}")
    print(f"{text}")
    print(f"{char * width}")


async def main():
    """Run the cart order payout test."""
    
    print_header("CART ORDER PAYOUT TEST", "=", 70)
    
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
        print_section("SELLER ADDRESSES")
        print(f"Seller 1: {seller1_address}")
        print(f"Seller 2: {seller2_address}")
        
        # Create test listings with different assets and sellers
        print_section("CREATING TEST LISTINGS")
        
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

        print("\n🏪 Listing 1 (CRONOS):")
        print(f"  ID: {listing1['id']}")
        print(f"  Deposit: {deposit1}")
        print(f"  Seller: {seller1_address}")
        print(f"\n🏪 Listing 2 (ASTRA):")
        print(f"  ID: {listing2['id']}")
        print(f"  Deposit: {deposit2}")
        print(f"  Seller: {seller2_address}")

        # Start the monitor and payout processor
        print_section("STARTING SERVICES")
        print("Starting blockchain monitor and payout processor...")
        monitor_task = asyncio.create_task(monitor.start())
        payout_task = asyncio.create_task(payout_manager.process_payouts())

        # Wait a moment for services to initialize
        await asyncio.sleep(2)

        # Check initial balances
        print_section("INITIAL BALANCES")
        balances1 = await listing_manager.get_balances(listing1['id'])
        balances2 = await listing_manager.get_balances(listing2['id'])
        
        print("Listing 1 (CRONOS Store):")
        for asset, balance in balances1.items():
            print(f"  {asset}: {balance['confirmed_balance']} (confirmed), {balance['pending_balance']} (pending)")
        
        print("\nListing 2 (ASTRA Store):")
        for asset, balance in balances2.items():
            print(f"  {asset}: {balance['confirmed_balance']} (confirmed), {balance['pending_balance']} (pending)")

        # Generate buyer address first
        print_section("GENERATING BUYER ADDRESS")
        buyer_address = rpc_client.getnewaddress()
        print(f"Buyer Address: {buyer_address}")

        # First try to create orders that should fail due to no balance
        print_section("TESTING INSUFFICIENT BALANCE")
        try:
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
            print("❌ ERROR: Cart order creation should have failed!")
        except Exception as e:
            print(f"✅ Expected error: {e}")

        # Send assets to the listing addresses
        print_section("FUNDING LISTING ADDRESSES")
        try:
            # First send CRONOS to seller1
            print("\n💰 Sending CRONOS to seller 1...")
            tx_hash1 = rpc_client.transfer("CRONOS", 2.0, seller1_address)
            if isinstance(tx_hash1, list):
                tx_hash1 = tx_hash1[0]
            print(f"✅ Sent 2.0 CRONOS to seller 1")
            print(f"   TX: {tx_hash1}")
            
            # Then send ASTRA to seller2
            print("\n💰 Sending ASTRA to seller 2...")
            tx_hash2 = rpc_client.transfer("ASTRA", 3.0, seller2_address)
            if isinstance(tx_hash2, list):
                tx_hash2 = tx_hash2[0]
            print(f"✅ Sent 3.0 ASTRA to seller 2")
            print(f"   TX: {tx_hash2}")
            
            print("\n⏳ Waiting for confirmations...")
            
            # Wait for confirmations
            dots = 0
            while True:
                # Get balances using listassetbalancesbyaddress
                cronos_balances = rpc_client.listassetbalancesbyaddress(seller1_address)
                astra_balances = rpc_client.listassetbalancesbyaddress(seller2_address)
                
                cronos_balance = float(cronos_balances.get('CRONOS', 0))
                astra_balance = float(astra_balances.get('ASTRA', 0))
                
                if cronos_balance >= 2.0 and astra_balance >= 3.0:
                    print("\n\n✅ Assets confirmed in seller addresses!")
                    print("\nSeller 1 Balances:")
                    for asset, amount in cronos_balances.items():
                        print(f"  {asset}: {amount}")
                    print("\nSeller 2 Balances:")
                    for asset, amount in astra_balances.items():
                        print(f"  {asset}: {amount}")
                    break
                    
                dots = (dots + 1) % 4
                print(f"\rWaiting for confirmations{'.' * dots + ' ' * (3-dots)}", end="", flush=True)
                await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Failed to send assets to sellers: {e}")
            raise

        # Now send assets from sellers to listing deposit addresses
        print_section("FUNDING LISTING DEPOSIT ADDRESSES")
        try:
            print("\n💰 Sending CRONOS from seller 1 to listing 1...")
            tx_hash3 = rpc_client.transferfromaddress(
                "CRONOS",          # Asset name
                seller1_address,   # From address
                2.0,              # Amount
                deposit1,         # To address
                "",               # Message
                0,               # Expire time
                seller1_address,  # EVR change address
                seller1_address   # Asset change address
            )
            if isinstance(tx_hash3, list):
                tx_hash3 = tx_hash3[0]
            print(f"✅ Sent 2.0 CRONOS to listing 1 deposit address")
            print(f"   TX: {tx_hash3}")
            
            print("\n💰 Sending ASTRA from seller 2 to listing 2...")
            tx_hash4 = rpc_client.transferfromaddress(
                "ASTRA",           # Asset name
                seller2_address,   # From address
                3.0,              # Amount
                deposit2,         # To address
                "",               # Message
                0,               # Expire time
                seller2_address,  # EVR change address
                seller2_address   # Asset change address
            )
            if isinstance(tx_hash4, list):
                tx_hash4 = tx_hash4[0]
            print(f"✅ Sent 3.0 ASTRA to listing 2 deposit address")
            print(f"   TX: {tx_hash4}")
            
            print("\n⏳ Waiting for listing balances to be confirmed...")
            
        except Exception as e:
            logger.error(f"Failed to send assets to listing deposit addresses: {e}")
            raise

        # Wait for listing balances to be confirmed
        dots = 0
        while True:
            balances1 = await listing_manager.get_balances(listing1['id'])
            balances2 = await listing_manager.get_balances(listing2['id'])
            
            cronos_confirmed = balances1.get('CRONOS', {}).get('confirmed_balance', 0) >= 2.0
            astra_confirmed = balances2.get('ASTRA', {}).get('confirmed_balance', 0) >= 3.0
            
            if cronos_confirmed and astra_confirmed:
                print("\n\n✅ All listing balances confirmed!")
                print("\nListing 1 (CRONOS Store) Final Balances:")
                for asset, balance in balances1.items():
                    print(f"  {asset}: {balance['confirmed_balance']} (confirmed), {balance['pending_balance']} (pending)")
                print("\nListing 2 (ASTRA Store) Final Balances:")
                for asset, balance in balances2.items():
                    print(f"  {asset}: {balance['confirmed_balance']} (confirmed), {balance['pending_balance']} (pending)")
                break
                
            dots = (dots + 1) % 4
            print(f"\rWaiting for confirmations{'.' * dots + ' ' * (3-dots)}", end="", flush=True)
            await asyncio.sleep(2)

        # Create a cart order for both items
        print_section("CREATING CART ORDER")
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
        print_header("CART ORDER RECEIPT", "=", 70)
        print(f"Order ID: {cart_order['id']}")
        print(f"Date: {cart_order['created_at']}")
        print("\n📦 ITEMS")

        total_price_evr = Decimal('0')
        total_fee_evr = Decimal('0')

        for item in cart_order['items']:
            seller_address = seller1_address if item['listing_id'] == listing1['id'] else seller2_address
            listing_name = "CRONOS Store" if item['listing_id'] == listing1['id'] else "ASTRA Store"
            print(f"\n🏪 {listing_name}")
            print(f"   Seller: {seller_address}")
            print(f"   Asset: {item['asset_name']}")
            print(f"   Amount: {item['amount']}")
            print(f"   Price per unit: {item['price_evr']/item['amount']:.2f} EVR")
            print(f"   Subtotal: {item['price_evr']:.2f} EVR")
            print(f"   Item Fee: {item['fee_evr']:.2f} EVR")
            total_price_evr += item['price_evr']
            total_fee_evr += item['fee_evr']

        print("\n💰 PAYMENT INFORMATION")
        print(f"Subtotal: {total_price_evr:.2f} EVR")
        print(f"Total Platform Fee: {total_fee_evr:.2f} EVR")
        print(f"Total Amount Due: {(total_price_evr + total_fee_evr):.2f} EVR")
        print(f"\nPayment Address: {cart_order['payment_address']}")

        # Send EVR payment for the cart order
        print_section("PROCESSING PAYMENT")
        try:
            tx_hash = rpc_client.sendtoaddress(
                cart_order['payment_address'], 
                float(cart_order['total_payment_evr'])
            )
            print(f"✅ Sent {cart_order['total_payment_evr']} EVR")
            print(f"   TX: {tx_hash}")
            print("\nWaiting for confirmations and payout processing...")
            
        except Exception as e:
            logger.error(f"Failed to send EVR: {e}")
            raise

        try:
            print_section("MONITORING ORDER STATUS")
            last_status = None
            last_sale_count = 0
            
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
                
                # Clear screen for better visibility
                print("\033[H\033[J")
                
                print_header("CART ORDER STATUS", "=", 70)
                print(f"Status: {updated_order['status']}")
                
                print("\n💰 Payment Balances:")
                for asset, balance in balances.items():
                    print(f"  {asset}: {balance['confirmed_balance']} (confirmed), {balance['pending_balance']} (pending)")
                
                if payout:
                    print("\n📦 Payout Status:")
                    print(f"  Success: {'✅' if payout['success'] else '❌'}")
                    print(f"  Attempts: {payout['failure_count'] or 0}")
                    if payout['total_fees_paid']:
                        print(f"  Fees Paid: {payout['total_fees_paid']} EVR")
                    if payout['completed_at']:
                        print(f"  Completed: {payout['completed_at']}")
                
                print("\n🚚 Fulfillment Status:")
                for item in updated_order['items']:
                    status = "✅ Fulfilled" if item.get('fulfillment_tx_hash') else "⏳ Pending"
                    print(f"\n  {item['asset_name']}: {status}")
                    if item.get('fulfillment_tx_hash'):
                        print(f"    TX: {item['fulfillment_tx_hash']}")
                        print(f"    Time: {item.get('fulfillment_time')}")
                
                if sales:
                    if len(sales) > last_sale_count:
                        print("\n🎉 NEW SALE RECORDED! 🎉")
                        last_sale_count = len(sales)
                    
                    print("\n📊 Sales History:")
                    for sale in sales:
                        print(f"\n  Asset: {sale['asset_name']}")
                        print(f"  Amount: {sale['amount']}")
                        print(f"  Price: {sale['price_evr']} EVR")
                        print(f"  Seller: {sale['seller_address']}")
                        print(f"  Buyer: {sale['buyer_address']}")
                        print(f"  Time: {sale['sale_time']}")
                
                if updated_order['status'] == 'completed':
                    print_header("TEST COMPLETED SUCCESSFULLY!", "=", 70)
                    print("✅ Cart order payment received and confirmed")
                    print("✅ Assets transferred to buyer")
                    print("✅ EVR payments sent to sellers")
                    print("✅ Sales recorded in history")
                    break
                    
                await asyncio.sleep(2)

        except KeyboardInterrupt:
            print("\nStopping services...")
        except Exception as e:
            logger.error(f"Error monitoring cart order: {e}")
        finally:
            # Stop services
            print_section("CLEANUP")
            print("Stopping blockchain monitor and payout processor...")
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