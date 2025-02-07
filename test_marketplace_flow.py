"""Comprehensive test script for the entire marketplace system.

This test covers:
1. Database initialization and connection
2. Listing creation with multiple assets
3. Asset transfers to listings
4. Order creation and payment processing
5. Cart order creation and multi-asset payments
6. Payout processing to sellers
7. Balance tracking and verification
8. Transaction monitoring and confirmation
9. Sales history tracking
"""

import asyncio
import logging
import random
from decimal import Decimal
from typing import Dict, List, Optional
import uuid
from datetime import datetime

from database import init_db, close, get_pool
from listings import ListingManager
from orders import OrderManager, PayoutManager
from monitor import TransactionMonitor
from rpc import client as rpc_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MarketplaceTest:
    """Test harness for marketplace functionality."""

    def __init__(self):
        """Initialize test harness."""
        self.pool = None
        self.listing_manager = None
        self.order_manager = None
        self.payout_manager = None
        self.monitor = None
        
        # Test data
        self.seller_addresses = []
        self.buyer_addresses = []
        self.listings = []
        self.orders = []
        self.cart_orders = []
        
        # Test assets
        self.test_assets = ['CREDITS', 'ASTRA']
        
    async def setup(self):
        """Set up test environment."""
        logger.info("Setting up test environment...")
        
        # Initialize database
        await init_db()
        self.pool = await get_pool()
        
        # Initialize managers
        self.listing_manager = ListingManager(self.pool)
        self.order_manager = OrderManager(self.pool)
        self.payout_manager = PayoutManager(self.pool)
        
        # Create monitor
        self.monitor = TransactionMonitor(self.pool)
        
        try:
            # Generate seller addresses
            for i in range(3):
                address = rpc_client.getnewaddress()
                self.seller_addresses.append(address)
                logger.info(f"Generated seller {i+1} address: {address}")
            
            # Generate buyer addresses and fund them
            random.seed(42)  # For reproducible tests
            for i in range(5):
                address = rpc_client.getnewaddress()
                self.buyer_addresses.append(address)
                
                # Fund with random amount between 100-200 EVR
                amount = random.randint(100, 200)
                try:
                    # Try to unlock wallet if encrypted
                    try:
                        rpc_client.walletpassphrase("your_wallet_password", 3600)
                    except Exception as e:
                        if "unencrypted wallet" not in str(e).lower():
                            raise
                    
                    # Send funds
                    tx_hash = rpc_client.sendtoaddress(address, float(amount))
                    logger.info(f"Funded buyer {i+1} address {address} with {amount} EVR (tx: {tx_hash})")
                    
                    # Generate a block to confirm the transaction
                    await self.generate_blocks(1)
                    
                    # Verify the balance
                    balance = float(rpc_client.getbalance())
                    logger.info(f"Wallet balance after funding: {balance} EVR")
                    
                except Exception as e:
                    logger.error(f"Error funding buyer address {address}: {e}")
                    raise
            
            # Create test assets if they don't exist
            for asset_name in self.test_assets:
                try:
                    # Check if asset exists
                    asset_data = rpc_client.getassetdata(asset_name)
                    logger.info(f"Asset {asset_name} already exists")
                except:
                    # Create asset
                    rpc_client.issue(asset_name, 1000, f"Test {asset_name} Asset")
                    logger.info(f"Created {asset_name} test asset")
                    await self.generate_blocks(1)
            
            logger.info("Test environment setup complete")
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            raise

    async def cleanup(self):
        """Clean up test environment."""
        logger.info("Cleaning up test environment...")
        if self.monitor:
            self.monitor.stop()
        await close()

    async def print_balances(self, title: str, listing_id: Optional[uuid.UUID] = None, 
                           order_id: Optional[uuid.UUID] = None):
        """Print current balances for a listing or order."""
        print(f"\n=== {title} ===")
        
        if listing_id:
            balances = await self.listing_manager.get_balances(listing_id)
            print("Listing Balances:")
        elif order_id:
            balances = await self.order_manager.get_order_balances(order_id)
            print("Order Balances:")
        else:
            return
            
        for asset, balance in balances.items():
            print(f"{asset}:")
            print(f"  Confirmed: {balance['confirmed_balance']}")
            print(f"  Pending: {balance['pending_balance']}")
        print("=" * 40)

    async def print_order_status(self, order_id: uuid.UUID, is_cart: bool = False):
        """Print detailed order status information."""
        print(f"\n=== Order Status: {order_id} ===")
        
        if is_cart:
            order = await self.order_manager.get_cart_order(order_id)
            prefix = "Cart "
        else:
            order = await self.order_manager.get_order(order_id)
            prefix = ""
            
        print(f"{prefix}Order Status: {order['status']}")
        print(f"Created: {order['created_at']}")
        print(f"Updated: {order['updated_at']}")
        print(f"Buyer: {order['buyer_address']}")
        print(f"Payment Address: {order['payment_address']}")
        print("\nItems:")
        for item in order['items']:
            print(f"- {item['asset_name']}: {item['amount']}")
            print(f"  Price: {item['price_evr']} EVR")
            print(f"  Fee: {item['fee_evr']} EVR")
            if 'fulfillment_tx_hash' in item:
                print(f"  Fulfillment TX: {item.get('fulfillment_tx_hash', 'Pending')}")
                
        print(f"\nTotal Price: {order['total_price_evr']} EVR")
        print(f"Total Fee: {order['total_fee_evr']} EVR")
        print(f"Total Payment: {order['total_payment_evr']} EVR")
        print("=" * 40)

    async def run_test(self):
        """Run the comprehensive marketplace test."""
        try:
            # Start blockchain monitor
            logger.info("Starting blockchain monitor...")
            monitor_task = asyncio.create_task(self.monitor.start())
            
            # Start payout processor
            logger.info("Starting payout processor...")
            payout_task = asyncio.create_task(self.payout_manager.process_payouts())
            
            # Wait for services to initialize
            await asyncio.sleep(2)
            
            # Create listings
            logger.info("\nCreating test listings...")
            listing_data = [
                {
                    "name": "CREDITS Store",
                    "description": "Test listing for CREDITS",
                    "prices": [{"asset_name": "CREDITS", "price_evr": 50}]
                },
                {
                    "name": "ASTRA Store",
                    "description": "Test listing for ASTRA",
                    "prices": [{"asset_name": "ASTRA", "price_evr": 75}]
                },
                {
                    "name": "Multi-Asset Store",
                    "description": "Test listing with multiple assets",
                    "prices": [
                        {"asset_name": "CREDITS", "price_evr": 45},
                        {"asset_name": "ASTRA", "price_evr": 70}
                    ]
                }
            ]
            
            for i, data in enumerate(listing_data):
                seller_address = self.seller_addresses[i % len(self.seller_addresses)]
                listing = await self.listing_manager.create_listing(
                    seller_address=seller_address,
                    name=data["name"],
                    description=data["description"],
                    prices=data["prices"]
                )
                self.listings.append(listing)
                
                print(f"\n=== Created Listing {i+1} ===")
                print(f"ID: {listing['id']}")
                print(f"Name: {listing['name']}")
                print(f"Seller: {seller_address}")
                print("Prices:")
                for price in data["prices"]:
                    print(f"  {price['asset_name']}: {price['price_evr']} EVR")
                print("=" * 40)
            
            # Fund listings with assets
            logger.info("\nFunding listings with assets...")
            for listing in self.listings:
                deposit_address = await self.listing_manager.get_deposit_address(listing['id'])
                
                for price in listing['prices']:
                    asset_name = price['asset_name']
                    try:
                        # Send 5 units of each asset
                        tx_hash = rpc_client.transfer(
                            asset_name,
                            5.0,
                            deposit_address,
                            "",  # Message
                            0,   # Expire time
                            "",  # Change address
                            ""   # Asset change address
                        )
                        if isinstance(tx_hash, list):
                            tx_hash = tx_hash[0]
                        logger.info(f"Sent 5.0 {asset_name} to listing {listing['id']} (tx: {tx_hash})")
                    except Exception as e:
                        logger.error(f"Failed to send {asset_name}: {e}")
                        raise
            
            # Wait for listing balances to be confirmed
            logger.info("\nWaiting for listing balances to be confirmed...")
            while True:
                all_confirmed = True
                for listing in self.listings:
                    await self.print_balances(f"Listing {listing['id']} Balances", listing_id=listing['id'])
                    
                    balances = await self.listing_manager.get_balances(listing['id'])
                    for price in listing['prices']:
                        asset_name = price['asset_name']
                        if balances.get(asset_name, {}).get('confirmed_balance', 0) < 5.0:
                            all_confirmed = False
                            break
                
                if all_confirmed:
                    logger.info("All listing balances confirmed!")
                    break
                    
                await asyncio.sleep(5)
            
            # Create regular orders
            logger.info("\nCreating regular orders...")
            for i, listing in enumerate(self.listings[:2]):  # Use first two listings for regular orders
                buyer_address = self.buyer_addresses[i]
                
                # Create order for first asset in listing
                asset_name = listing['prices'][0]['asset_name']
                order = await self.order_manager.create_order(
                    listing_id=listing['id'],
                    buyer_address=buyer_address,
                    items=[{
                        'asset_name': asset_name,
                        'amount': Decimal('1.5')
                    }]
                )
                self.orders.append(order)
                
                await self.print_order_status(order['id'])
            
            # Create cart order
            logger.info("\nCreating cart order...")
            multi_listing = self.listings[2]  # Use multi-asset listing
            cart_order = await self.order_manager.create_cart_order(
                buyer_address=self.buyer_addresses[2],
                items=[
                    {
                        'listing_id': multi_listing['id'],
                        'asset_name': 'CREDITS',
                        'amount': Decimal('1.0')
                    },
                    {
                        'listing_id': multi_listing['id'],
                        'asset_name': 'ASTRA',
                        'amount': Decimal('1.0')
                    }
                ]
            )
            self.cart_orders.append(cart_order)
            
            await self.print_order_status(cart_order['id'], is_cart=True)
            
            # Process payments
            logger.info("\nProcessing payments...")
            
            # Pay regular orders
            for order in self.orders:
                try:
                    tx_hash = rpc_client.sendtoaddress(
                        order['payment_address'],
                        float(order['total_payment_evr'])
                    )
                    logger.info(f"Sent {order['total_payment_evr']} EVR for order {order['id']} (tx: {tx_hash})")
                except Exception as e:
                    logger.error(f"Failed to pay order {order['id']}: {e}")
                    raise
            
            # Pay cart order
            for cart_order in self.cart_orders:
                try:
                    tx_hash = rpc_client.sendtoaddress(
                        cart_order['payment_address'],
                        float(cart_order['total_payment_evr'])
                    )
                    logger.info(f"Sent {cart_order['total_payment_evr']} EVR for cart order {cart_order['id']} (tx: {tx_hash})")
                except Exception as e:
                    logger.error(f"Failed to pay cart order {cart_order['id']}: {e}")
                    raise
            
            # Monitor order statuses and payouts
            logger.info("\nMonitoring order statuses and payouts...")
            try:
                while True:
                    all_completed = True
                    
                    # Check regular orders
                    for order in self.orders:
                        await self.print_order_status(order['id'])
                        await self.print_balances(f"Order {order['id']} Balances", order_id=order['id'])
                        
                        updated_order = await self.order_manager.get_order(order['id'])
                        if updated_order['status'] != 'completed':
                            all_completed = False
                    
                    # Check cart orders
                    for cart_order in self.cart_orders:
                        await self.print_order_status(cart_order['id'], is_cart=True)
                        await self.print_balances(f"Cart Order {cart_order['id']} Balances", order_id=cart_order['id'])
                        
                        updated_order = await self.order_manager.get_cart_order(cart_order['id'])
                        if updated_order['status'] != 'completed':
                            all_completed = False
                    
                    # Check listing balances
                    for listing in self.listings:
                        await self.print_balances(f"Listing {listing['id']} Final Balances", listing_id=listing['id'])
                    
                    if all_completed:
                        logger.info("All orders completed successfully!")
                        break
                        
                    await asyncio.sleep(5)
                
            except KeyboardInterrupt:
                logger.info("Monitoring interrupted by user")
            
            # Print final sales history
            logger.info("\nFinal Sales History:")
            async with self.pool.acquire() as conn:
                sales = await conn.fetch('''
                    SELECT 
                        listing_id,
                        asset_name,
                        amount,
                        price_evr,
                        seller_address,
                        buyer_address,
                        sale_time,
                        order_id,
                        cart_order_id
                    FROM sale_history 
                    ORDER BY sale_time DESC
                ''')
                
                for sale in sales:
                    print("\n--- Sale Record ---")
                    print(f"Asset: {sale['asset_name']}")
                    print(f"Amount: {sale['amount']}")
                    print(f"Price: {sale['price_evr']} EVR")
                    print(f"Seller: {sale['seller_address']}")
                    print(f"Buyer: {sale['buyer_address']}")
                    print(f"Time: {sale['sale_time']}")
                    if sale['order_id']:
                        print(f"Order ID: {sale['order_id']}")
                    if sale['cart_order_id']:
                        print(f"Cart Order ID: {sale['cart_order_id']}")
                    print("-" * 20)
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            raise
        finally:
            # Stop services
            logger.info("Stopping services...")
            self.monitor.stop()
            self.payout_manager.stop()
            await monitor_task
            await payout_task

    async def generate_blocks(self, num_blocks: int = 6):
        """Generate specified number of blocks to get confirmations."""
        try:
            for _ in range(num_blocks):
                rpc_client.generate(1)
                await asyncio.sleep(1)  # Brief delay between blocks
        except Exception as e:
            logger.error(f"Error generating blocks: {e}")
            raise

async def run_test():
    """Run the marketplace test."""
    test = MarketplaceTest()
    try:
        await test.setup()
        await test.run_test()
    finally:
        await test.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 