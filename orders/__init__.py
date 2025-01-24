"""Orders module for managing marketplace orders.

This module handles order creation, validation, and fulfillment.
It ensures orders have sufficient listing balances and tracks payment status.
"""
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID

from asyncpg.pool import Pool
from asyncpg.exceptions import PostgresError

from database.exceptions import DatabaseError
from database import get_pool
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

class ListingNotFoundError(OrderError):
    """Raised when the requested listing is not found or inactive."""
    pass

class AssetNotFoundError(OrderError):
    """Raised when the requested asset is not found in the listing."""
    pass

class OrderManager:
    """Manages order operations and state transitions."""
    
    def __init__(self, pool: Optional[Pool] = None) -> None:
        """Initialize order manager.
        
        Args:
            pool: Optional database connection pool. If not provided, will get from database module.
        """
        self.pool = pool
        
    async def ensure_pool(self):
        """Ensure we have a database pool."""
        if not self.pool:
            self.pool = await get_pool()
        
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
            ListingNotFoundError: If listing not found or inactive
            AssetNotFoundError: If asset not found in listing
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
            await self.ensure_pool()

            # Verify listing exists in its own transaction
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
                    raise ListingNotFoundError(f"Listing {listing_id} not found or inactive")
                
                logger.debug(f"Found active listing: {listing['id']}")

            # Check balances and get prices for all items
            total_price = Decimal(0)
            order_items = []
            
            for item in items:
                asset_name = item['asset_name']
                amount = item['amount']
                
                logger.debug(f"Checking balance for {asset_name}")
                
                # Get current balance and price in its own transaction
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        '''
                        SELECT 
                            lb.confirmed_balance,
                            lb.pending_balance,
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
                        raise AssetNotFoundError(
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
                        payment_address
                    ) VALUES ($1, $2, $3)
                    RETURNING *
                    ''',
                    listing_id,
                    buyer_address,
                    payment_address
                )
                logger.debug(f"Created order: {order['id']}")
            
            # Create order items and balances in separate transactions
            for item in order_items:
                # Calculate fee for this item
                item_fee = item['price_evr'] * DEFAULT_FEE_PERCENT
                
                async with self.pool.acquire() as conn:
                    # Create order item
                    await conn.execute(
                        '''
                        INSERT INTO order_items (
                            order_id,
                            asset_name,
                            amount,
                            price_evr,
                            fee_evr
                        ) VALUES ($1, $2, $3, $4, $5)
                        ''',
                        order['id'],
                        item['asset_name'],
                        item['amount'],
                        item['price_evr'],
                        item_fee
                    )
                    
                    # Initialize order balance entry
                    await conn.execute(
                        '''
                        INSERT INTO order_balances (
                            order_id,
                            asset_name,
                            confirmed_balance,
                            pending_balance
                        ) VALUES ($1, $2, 0, 0)
                        ''',
                        order['id'],
                        item['asset_name']
                    )
            
            # Get full order details in its own transaction
            order_details = await self.get_order(order['id'])
            
            logger.info(f"Order {order['id']} created successfully")
            return order_details
                
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
        await self.ensure_pool()
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
            
            # Get order balances
            balances = await conn.fetch(
                'SELECT * FROM order_balances WHERE order_id = $1',
                order_id
            )
            
            # Calculate totals
            total_price_evr = Decimal('0')
            total_fee_evr = Decimal('0')
            for item in items:
                total_price_evr += item['price_evr']
                total_fee_evr += item['fee_evr']
            
            result = dict(order)
            result['items'] = [dict(item) for item in items]
            result['balances'] = [dict(balance) for balance in balances]
            result['total_price_evr'] = total_price_evr
            result['total_fee_evr'] = total_fee_evr
            result['total_payment_evr'] = total_price_evr + total_fee_evr
            return result

    async def get_order_balances(self, order_id: UUID) -> Dict[str, Dict[str, Decimal]]:
        """Get balance of an order's payment address.
        
        Args:
            order_id: UUID of order to check
            
        Returns:
            Dict mapping asset names to balance info
            
        Raises:
            OrderError: If order not found
        """
        await self.ensure_pool()
        async with self.pool.acquire() as conn:
            # Get balances from database
            rows = await conn.fetch(
                '''
                SELECT 
                    asset_name,
                    confirmed_balance,
                    pending_balance
                FROM order_balances 
                WHERE order_id = $1
                ''',
                order_id
            )
            
            if not rows:
                raise OrderError(f"Order {order_id} not found")
                
            return {
                row['asset_name']: {
                    'confirmed_balance': row['confirmed_balance'] or Decimal('0'),
                    'pending_balance': row['pending_balance'] or Decimal('0')
                }
                for row in rows
            }

# Export public interface
__all__ = [
    'OrderManager',
    'OrderError',
    'InsufficientBalanceError',
    'ListingNotFoundError',
    'AssetNotFoundError'
] 