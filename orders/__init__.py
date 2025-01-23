"""Orders module for managing marketplace orders.

This module handles order creation, validation, and fulfillment.
It ensures orders have sufficient listing balances and tracks payment status.
"""
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID
import traceback

from asyncpg.pool import Pool
from asyncpg.exceptions import PostgresError

from database.exceptions import DatabaseError
from rpc import client as rpc_client

logger = logging.getLogger(__name__)

# Default marketplace settings
DEFAULT_FEE_PERCENT = Decimal('0.01')  # 1% fee
DEFAULT_FEE_ADDRESS = "EVRFeeAddressGoesHere"  # TODO: Update with actual fee address

class OrderError(Exception):
    """Base class for order-related errors."""
    pass

class InsufficientBalanceError(OrderError):
    """Raised when a listing has insufficient balance for order items."""
    def __init__(self, asset_name: str, available: Decimal, requested: Decimal):
        self.asset_name = asset_name
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient balance for {asset_name}: "
            f"available {available}, requested {requested}"
        )

class InvalidOrderStatusError(OrderError):
    """Raised when attempting invalid order status transitions."""
    pass

class OrderManager:
    """Manages order operations and state transitions."""
    
    def __init__(self, pool: Pool) -> None:
        """Initialize order manager.
        
        Args:
            pool: Database connection pool
        """
        self.pool = pool
        
    async def create_order(
        self,
        listing_id: UUID,
        buyer_address: str,
        items: List[Dict[str, Decimal]]
    ) -> Dict:
        """Create a new order for listing items.
        
        Args:
            listing_id: UUID of the listing to order from
            buyer_address: Buyer's payment address
            items: List of items to order with asset_name and amount
            
        Returns:
            Dict containing the created order details
            
        Raises:
            InsufficientBalanceError: If listing has insufficient balance
            DatabaseError: If database operation fails
        """
        logger.info(f"Starting order creation for listing {listing_id}")
        
        # Get payment address before starting transaction
        try:
            logger.debug("Getting new payment address from RPC")
            payment_address = rpc_client.getnewaddress()
            logger.debug(f"Got payment address: {payment_address}")
        except Exception as e:
            logger.error(f"RPC error getting payment address: {e}")
            raise OrderError(f"Failed to get payment address: {e}")

        try:
            # First verify listing exists in its own transaction
            async with self.pool.acquire() as conn:
                listing = await conn.fetchrow(
                    '''
                    SELECT id, seller_address 
                    FROM listings 
                    WHERE id = $1 AND status = 'active'
                    ''',
                    listing_id
                )
                
            if not listing:
                raise OrderError(f"Listing {listing_id} not found or inactive")
            
            logger.debug(f"Found active listing: {listing['id']}")
            
            # Check balances and get prices for all items in separate transaction
            total_price = Decimal(0)
            order_items = []
            
            async with self.pool.acquire() as conn:
                for item in items:
                    asset_name = item['asset_name']
                    amount = item['amount']
                    
                    logger.debug(f"Checking balance for {asset_name}")
                    
                    # Get current balance and price
                    row = await conn.fetchrow(
                        '''
                        SELECT 
                            lb.confirmed_balance,
                            lp.price_evr
                        FROM listing_balances lb
                        JOIN listing_prices lp ON 
                            lp.listing_id = lb.listing_id AND
                            lp.asset_name = lb.asset_name
                        WHERE lb.listing_id = $1 AND lb.asset_name = $2
                        ''',
                        listing_id,
                        asset_name
                    )
                    
                    if not row:
                        raise OrderError(
                            f"Asset {asset_name} not found in listing {listing_id}"
                        )
                        
                    if row['confirmed_balance'] < amount:
                        raise InsufficientBalanceError(
                            asset_name,
                            row['confirmed_balance'],
                            amount
                        )
                    
                    logger.debug(f"Balance check passed for {asset_name}")
                        
                    price = row['price_evr'] * amount
                    total_price += price
                    
                    order_items.append({
                        'asset_name': asset_name,
                        'amount': amount,
                        'price_evr': price
                    })
            
            # Calculate fee
            fee = total_price * DEFAULT_FEE_PERCENT
            logger.debug(f"Calculated total price: {total_price} EVR, fee: {fee} EVR")
            
            # Create order in its own transaction
            async with self.pool.acquire() as conn:
                order = await conn.fetchrow(
                    '''
                    INSERT INTO orders (
                        listing_id,
                        buyer_address,
                        total_price_evr,
                        fee_evr,
                        payment_address
                    ) VALUES ($1, $2, $3, $4, $5)
                    RETURNING *
                    ''',
                    listing_id,
                    buyer_address,
                    total_price,
                    fee,
                    payment_address
                )
                logger.debug(f"Created order: {order['id']}")
            
            # Create order items in separate transaction
            async with self.pool.acquire() as conn:
                for item in order_items:
                    await conn.execute(
                        '''
                        INSERT INTO order_items (
                            order_id,
                            asset_name,
                            amount,
                            price_evr
                        ) VALUES ($1, $2, $3, $4)
                        ''',
                        order['id'],
                        item['asset_name'],
                        item['amount'],
                        item['price_evr']
                    )
                logger.debug("Order items created")
            
            logger.info(f"Order {order['id']} created successfully")
            return dict(order)
                
        except PostgresError as e:
            logger.error(f"Database error creating order: {e}")
            raise DatabaseError(f"Failed to create order: {e}")
        except Exception as e:
            logger.error(f"Order creation failed: {e}")
            raise

    async def get_order(self, order_id: UUID) -> Optional[Dict]:
        """Get order details by ID.
        
        Args:
            order_id: UUID of order to retrieve
            
        Returns:
            Dict containing order details or None if not found
        """
        async with self.pool.acquire() as conn:
            order = await conn.fetchrow(
                'SELECT * FROM orders WHERE id = $1',
                order_id
            )
            
            if not order:
                return None
                
            # Get order items
            items = await conn.fetch(
                'SELECT * FROM order_items WHERE order_id = $1',
                order_id
            )
            
            result = dict(order)
            result['items'] = [dict(item) for item in items]
            return result
            
    async def process_paid_orders(self) -> None:
        """Process orders that are fully paid and ready for fulfillment.
        
        This method:
        1. Finds orders in 'paid' status
        2. Updates them to 'fulfilling'
        3. Sends assets to buyer
        4. Sends payment to seller
        5. Sends fee to marketplace
        6. Updates order status to 'completed'
        """
        async with self.pool.acquire() as conn:
            # Find paid orders
            orders = await conn.fetch(
                "SELECT * FROM orders WHERE status = 'paid'"
            )
            
            for order in orders:
                try:
                    async with conn.transaction():
                        # Update to fulfilling
                        await conn.execute(
                            '''
                            UPDATE orders 
                            SET status = 'fulfilling', updated_at = now()
                            WHERE id = $1
                            ''',
                            order['id']
                        )
                        
                        # Get order items and listing info
                        items = await conn.fetch(
                            '''
                            SELECT oi.*, l.seller_address
                            FROM order_items oi
                            JOIN orders o ON o.id = oi.order_id
                            JOIN listings l ON l.id = o.listing_id
                            WHERE oi.order_id = $1
                            ''',
                            order['id']
                        )
                        
                        # Send assets to buyer
                        for item in items:
                            tx_hash = await rpc_client.sendasset(
                                item['seller_address'],
                                order['buyer_address'],
                                item['asset_name'],
                                float(item['amount'])
                            )
                            
                            # Record fulfillment
                            await conn.execute(
                                '''
                                UPDATE order_items
                                SET 
                                    fulfillment_tx_hash = $1,
                                    fulfillment_time = now(),
                                    updated_at = now()
                                WHERE order_id = $2 AND asset_name = $3
                                ''',
                                tx_hash,
                                order['id'],
                                item['asset_name']
                            )
                            
                        # Send EVR payment to seller
                        seller_amount = order['total_price_evr'] - order['fee_evr']
                        await rpc_client.sendtoaddress(
                            items[0]['seller_address'],
                            float(seller_amount)
                        )
                        
                        # Send fee to marketplace
                        await rpc_client.sendtoaddress(
                            DEFAULT_FEE_ADDRESS,
                            float(order['fee_evr'])
                        )
                        
                        # Update order status
                        await conn.execute(
                            '''
                            UPDATE orders
                            SET status = 'completed', updated_at = now()
                            WHERE id = $1
                            ''',
                            order['id']
                        )
                        
                except Exception as e:
                    logger.error(f"Failed to process order {order['id']}: {e}")
                    # Update status to error
                    await conn.execute(
                        '''
                        UPDATE orders
                        SET status = 'error', updated_at = now()
                        WHERE id = $1
                        ''',
                        order['id']
                    ) 