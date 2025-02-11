"""Orders module for managing marketplace orders.

This module handles order creation, validation, and fulfillment.
It ensures orders have sufficient listing balances and tracks payment status.
"""
import logging
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta

from asyncpg.pool import Pool
from asyncpg.exceptions import PostgresError

from database.exceptions import DatabaseError
from database import get_pool
from rpc import client as rpc_client
from config import settings_conf, evrmore_conf

logger = logging.getLogger(__name__)

# Default marketplace settings
DEFAULT_FEE_PERCENT = Decimal('0.01')  # 1% fee
DEFAULT_FEE_ADDRESS = settings_conf['fee_address']  # Get fee address from settings

# Load settings from config and convert to proper types
MAX_PAYOUT_ATTEMPTS = int(settings_conf['max_payout_attempts'])
PAYOUT_RETRY_DELAY = int(settings_conf['payout_retry_delay'])
PAYOUT_BATCH_SIZE = int(settings_conf['payout_batch_size'])
ORDER_EXPIRATION_MINUTES = int(settings_conf['order_expiration_minutes'])

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

class PayoutError(Exception):
    """Base exception for payout-related errors."""
    pass

class InsufficientFundsError(PayoutError):
    """Raised when there are insufficient funds for payout."""
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
        """Create a new order for a listing."""
        await self.ensure_pool()
        
        try:
            # First verify the listing exists and get its details
            async with self.pool.acquire() as conn:
                listing = await conn.fetchrow(
                    'SELECT * FROM listings WHERE id = $1',
                    listing_id
                )
                if not listing:
                    raise ListingNotFoundError(f"Listing {listing_id} not found")
                
                # Get prices and units for all requested assets
                prices = {}
                for item in items:
                    price_row = await conn.fetchrow(
                        '''
                        SELECT price_evr, price_asset_name, price_asset_amount, units
                        FROM listing_prices 
                        WHERE listing_id = $1 AND asset_name = $2
                        ''',
                        listing_id,
                        item['asset_name']
                    )
                    if not price_row:
                        raise AssetNotFoundError(
                            f"Asset {item['asset_name']} not available in listing {listing_id}"
                        )
                    prices[item['asset_name']] = price_row
                    
                    # Validate amount has correct number of decimal places
                    amount_str = str(item['amount'])
                    decimal_places = len(amount_str.split('.')[-1]) if '.' in amount_str else 0
                    if decimal_places > price_row['units']:
                        raise OrderError(
                            f"Invalid amount for {item['asset_name']}: "
                            f"maximum {price_row['units']} decimal places allowed"
                        )
                
                # Get current balances
                balances = await conn.fetch(
                    '''
                    SELECT asset_name, confirmed_balance, units
                    FROM listing_balances 
                    WHERE listing_id = $1
                    ''',
                    listing_id
                )
                balance_map = {
                    b['asset_name']: {
                        'confirmed': b['confirmed_balance'],
                        'units': b['units']
                    }
                    for b in balances
                }
                
                # Verify sufficient balance for each item
                for item in items:
                    asset_name = item['asset_name']
                    if asset_name not in balance_map:
                        raise InsufficientBalanceError(
                            asset_name, Decimal('0'), item['amount']
                        )
                    
                    balance = balance_map[asset_name]['confirmed']
                    if balance < item['amount']:
                        raise InsufficientBalanceError(
                            asset_name, balance, item['amount']
                        )
                
                # Get payment address before starting transaction
                try:
                    logger.debug("Getting new payment address from RPC")
                    payment_address = rpc_client.getnewaddress()
                    logger.debug(f"Got payment address: {payment_address}")
                except Exception as e:
                    logger.error(f"RPC error getting payment address: {e}")
                    raise OrderError(f"Failed to get payment address: {e}")

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

    async def search_orders(
        self,
        buyer_address: Optional[str] = None,
        listing_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search orders with various filters.
        
        Args:
            buyer_address: Optional buyer address to filter by
            listing_id: Optional listing ID to filter by
            status: Optional order status to filter by
            limit: Maximum number of results to return
            offset: Number of results to skip
            
        Returns:
            List of matching orders with their details
        """
        await self.ensure_pool()
        
        try:
            # Build the base query
            query = """
                SELECT DISTINCT o.*
                FROM orders o
                WHERE 1=1
            """
            params = []
            param_idx = 1
            
            # Add search conditions
            if buyer_address:
                query += f" AND o.buyer_address = ${param_idx}"
                params.append(buyer_address)
                param_idx += 1
                
            if listing_id:
                query += f" AND o.listing_id = ${param_idx}"
                params.append(listing_id)
                param_idx += 1
                
            if status:
                query += f" AND o.status = ${param_idx}"
                params.append(status)
                param_idx += 1
                
            # Add ordering and pagination
            query += " ORDER BY o.created_at DESC LIMIT $" + str(param_idx) + " OFFSET $" + str(param_idx + 1)
            params.extend([limit, offset])
            
            logger.debug("Executing order search query: %s with params: %r", query, params)
            
            async with self.pool.acquire() as conn:
                # Execute search query
                rows = await conn.fetch(query, *params)
                logger.debug("Search query returned %d orders", len(rows))
                
                # Get full order details for each result
                results = []
                for row in rows:
                    try:
                        order = await self.get_order(row['id'])
                        if order:
                            results.append(order)
                    except Exception as e:
                        logger.error("Error getting details for order %s: %s", row.get('id'), str(e))
                        continue
                
                logger.debug("Returning %d orders with full details", len(results))
                return results
                
        except Exception as e:
            logger.exception("Error in search_orders: %s", str(e))
            raise OrderError(f"Failed to search orders: {str(e)}")

    async def expire_pending_orders(self) -> int:
        """Expire pending orders that are older than 15 minutes.
        
        Returns:
            Number of orders expired
        """
        await self.ensure_pool()
        
        try:
            # Use timestamptz in the query instead of passing datetime
            async with self.pool.acquire() as conn:
                # Update orders that are pending and older than 15 minutes
                result = await conn.execute(
                    '''
                    UPDATE orders 
                    SET 
                        status = 'expired',
                        updated_at = now()
                    WHERE 
                        status = 'pending' 
                        AND created_at < (now() - interval '15 minutes')
                    '''
                )
                
                # Get number of orders expired
                expired_count = int(result.split()[-1])
                if expired_count > 0:
                    logger.info(f"Expired {expired_count} pending orders older than {ORDER_EXPIRATION_MINUTES} minutes")
                return expired_count
                
        except PostgresError as e:
            logger.error(f"Database error expiring orders: {e}")
            raise DatabaseError(f"Failed to expire orders: {e}")
        except Exception as e:
            logger.error(f"Error expiring orders: {e}")
            raise OrderError(f"Failed to expire orders: {e}")

    async def create_cart_order(
        self,
        buyer_address: str,
        items: List[Dict[str, Any]]
    ) -> Dict:
        """Create a new cart order for items from multiple listings.
        
        Args:
            buyer_address: Buyer's payment address
            items: List of items to order with listing_id, asset_name and amount
            
        Returns:
            Dict containing the created cart order details
            
        Raises:
            ListingNotFoundError: If any listing not found or inactive
            AssetNotFoundError: If asset not found in listing
            InsufficientBalanceError: If listing has insufficient balance
            DatabaseError: If database operation fails
        """
        logger.info("Starting cart order creation")
        
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

            # Verify all listings exist and get their details
            listings = {}
            async with self.pool.acquire() as conn:
                for item in items:
                    listing = await conn.fetchrow(
                        '''
                        SELECT id, seller_address, name 
                        FROM listings 
                        WHERE id = $1 AND status = 'active'
                        ''',
                        item['listing_id']
                    )
                    
                    if not listing:
                        raise ListingNotFoundError(f"Listing {item['listing_id']} not found or inactive")
                    
                    listings[item['listing_id']] = dict(listing)
                    logger.debug(f"Found active listing: {listing['id']}")

            # Check balances and get prices for all items
            total_price = Decimal(0)
            cart_items = []
            
            for item in items:
                listing_id = item['listing_id']
                asset_name = item['asset_name']
                amount = Decimal(str(item['amount']))

                async with self.pool.acquire() as conn:
                    # Get price for this asset
                    price = await conn.fetchrow(
                        '''
                        SELECT price_evr
                        FROM listing_prices 
                        WHERE listing_id = $1 AND asset_name = $2
                        ''',
                        listing_id,
                        asset_name
                    )
                    
                    if not price:
                        raise AssetNotFoundError(f"Asset {asset_name} not found in listing {listing_id}")

                    # Check listing balance
                    balance = await conn.fetchrow(
                        '''
                        SELECT confirmed_balance
                        FROM listing_balances
                        WHERE listing_id = $1 AND asset_name = $2
                        ''',
                        listing_id,
                        asset_name
                    )
                    
                    available = Decimal(str(balance['confirmed_balance'])) if balance else Decimal(0)
                    if available < amount:
                        raise InsufficientBalanceError(
                            asset_name=asset_name,
                            available=available,
                            requested=amount
                        )

                    # Calculate price for this item
                    item_price = (price['price_evr'] * amount) / Decimal('1.0')
                    total_price += item_price
                    
                    cart_items.append({
                        'listing_id': listing_id,
                        'listing_name': listings[listing_id]['name'],
                        'seller_address': listings[listing_id]['seller_address'],
                        'asset_name': asset_name,
                        'amount': amount,
                        'price_evr': item_price
                    })
                
            # Calculate fee
            fee_percent = Decimal(str(DEFAULT_FEE_PERCENT))
            total_fee = total_price * fee_percent
            total_required_payment = total_price + total_fee
            logger.debug(f"Calculated total price: {total_price} EVR, fee: {total_fee} EVR, required payment: {total_required_payment} EVR")
            
            # Create cart order in its own transaction
            async with self.pool.acquire() as conn:
                cart_order = await conn.fetchrow(
                    '''
                    INSERT INTO cart_orders (
                        buyer_address,
                        payment_address,
                        required_payment
                    ) VALUES ($1, $2, $3)
                    RETURNING *
                    ''',
                    buyer_address,
                    payment_address,
                    total_required_payment
                )
                logger.debug(f"Created cart order: {cart_order['id']}")
            
            # Create cart order items and balances in separate transactions
            for item in cart_items:
                # Calculate fee for this item
                item_fee = item['price_evr'] * fee_percent
                
                async with self.pool.acquire() as conn:
                    # Create cart order item
                    await conn.execute(
                        '''
                        INSERT INTO cart_order_items (
                            cart_order_id,
                            listing_id,
                            asset_name,
                            amount,
                            price_evr,
                            fee_evr
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        ''',
                        cart_order['id'],
                        item['listing_id'],
                        item['asset_name'],
                        item['amount'],
                        item['price_evr'],
                        item_fee
                    )
                    
                    # Initialize cart order balance entry for EVR
                    await conn.execute(
                        '''
                        INSERT INTO cart_order_balances (
                            cart_order_id,
                            asset_name,
                            confirmed_balance,
                            pending_balance
                        ) VALUES ($1, $2, 0, 0)
                        ON CONFLICT (cart_order_id, asset_name) DO NOTHING
                        ''',
                        cart_order['id'],
                        'EVR'
                    )
            
            # Get full cart order details
            cart_order_details = await self.get_cart_order(cart_order['id'])
            
            logger.info(f"Cart order {cart_order['id']} created successfully")
            return cart_order_details
                
        except PostgresError as e:
            logger.error(f"Database error creating cart order: {e}")
            raise DatabaseError(f"Failed to create cart order: {e}")
        except Exception as e:
            logger.error(f"Cart order creation failed: {e}")
            raise

    async def get_cart_order(self, cart_order_id: UUID) -> Optional[Dict]:
        """Get cart order details by ID.
        
        Args:
            cart_order_id: UUID of cart order to retrieve
            
        Returns:
            Dict containing cart order details or None if not found
        """
        await self.ensure_pool()
        async with self.pool.acquire() as conn:
            cart_order = await conn.fetchrow(
                'SELECT * FROM cart_orders WHERE id = $1',
                cart_order_id
            )
            
            if not cart_order:
                return None
                
            # Get cart order items with listing details
            items = await conn.fetch(
                '''
                SELECT 
                    coi.*,
                    l.seller_address,
                    l.deposit_address,
                    l.name as listing_name
                FROM cart_order_items coi
                JOIN listings l ON l.id = coi.listing_id
                WHERE coi.cart_order_id = $1
                ''',
                cart_order_id
            )
            
            # Get cart order balances
            balances = await conn.fetch(
                'SELECT * FROM cart_order_balances WHERE cart_order_id = $1',
                cart_order_id
            )
            
            # Calculate totals
            total_price_evr = Decimal('0')
            total_fee_evr = Decimal('0')
            for item in items:
                total_price_evr += item['price_evr']
                total_fee_evr += item['fee_evr']
            
            result = dict(cart_order)
            result['items'] = [dict(item) for item in items]
            result['balances'] = [dict(balance) for balance in balances]
            result['total_price_evr'] = total_price_evr
            result['total_fee_evr'] = total_fee_evr
            result['total_payment_evr'] = total_price_evr + total_fee_evr
            return result

    async def get_cart_order_balances(self, cart_order_id: UUID) -> Dict[str, Dict[str, Decimal]]:
        """Get balances for a cart order.
        
        Args:
            cart_order_id: UUID of cart order
            
        Returns:
            Dict mapping asset names to balance info
        """
        await self.ensure_pool()
        async with self.pool.acquire() as conn:
            balances = await conn.fetch(
                'SELECT * FROM cart_order_balances WHERE cart_order_id = $1',
                cart_order_id
            )
            
            return {
                balance['asset_name']: {
                    'confirmed_balance': balance['confirmed_balance'],
                    'pending_balance': balance['pending_balance']
                }
                for balance in balances
            }

class PayoutManager:
    """Manages order payouts and fee distribution."""
    
    def __init__(self, pool: Optional[Pool] = None):
        """Initialize payout manager.
        
        Args:
            pool: Optional database connection pool
        """
        self.pool = pool
        self._stop_requested = False
        
    async def ensure_pool(self):
        """Ensure we have a database pool."""
        if not self.pool:
            self.pool = await get_pool()
            
    def stop(self):
        """Signal the payout processor to stop."""
        self._stop_requested = True
            
    async def process_payouts(self):
        """Main payout processing loop.
        
        This method runs continuously, processing paid orders and handling payouts
        to buyers and sellers.
        """
        await self.ensure_pool()
        logger.info("Starting payout processor")
        
        while not self._stop_requested:
            try:
                # Get batch of paid orders that need processing
                orders = await self._get_orders_for_payout()
                
                if not orders:
                    # No orders to process, wait before checking again
                    await asyncio.sleep(60)
                    continue
                
                logger.info(f"Processing payouts for {len(orders)} orders")
                
                for order in orders:
                    try:
                        # Process each order in its own transaction
                        async with self.pool.acquire() as conn:
                            async with conn.transaction():
                                if order['order_type'] == 'cart':
                                    await self._process_cart_order_payout(conn, order)
                                else:
                                    await self._process_order_payout(conn, order)
                                
                    except Exception as e:
                        logger.error(f"Error processing payout for {order['order_type']} order {order['id']}: {e}")
                        # Update failure count and retry time
                        if order['order_type'] == 'cart':
                            await self._update_cart_order_payout_failure(order['id'])
                        else:
                            await self._update_payout_failure(order['id'])
                        
            except Exception as e:
                logger.error(f"Error in payout processor: {e}")
                await asyncio.sleep(60)  # Wait before retrying
                
    async def _get_orders_for_payout(self) -> List[Dict[str, Any]]:
        """Get orders that are ready for payout processing.
        
        Returns:
            List of orders ready for payout
        """
        await self.ensure_pool()
        
        try:
            async with self.pool.acquire() as conn:
                # Get paid regular orders without payouts
                regular_orders = await conn.fetch(
                    '''
                    SELECT o.*, op.attempts as failure_count, op.last_attempt as last_attempt_time
                    FROM orders o
                    LEFT JOIN order_payouts op ON o.id = op.order_id
                    WHERE o.status IN ('paid', 'sale_pending')
                    AND (
                        op.id IS NULL 
                        OR (
                            op.status = 'pending'
                            AND op.attempts < $1
                            AND (
                                op.last_attempt IS NULL 
                                OR op.last_attempt < now() - interval '1 hour'
                            )
                        )
                    )
                    ''',
                    MAX_PAYOUT_ATTEMPTS
                )

                # Get paid cart orders without payouts
                cart_orders = await conn.fetch(
                    '''
                    SELECT co.*, cop.attempts as failure_count, cop.last_attempt as last_attempt_time
                    FROM cart_orders co
                    LEFT JOIN order_payouts cop ON co.id = cop.cart_order_id
                    WHERE co.status IN ('paid', 'sale_pending')
                    AND (
                        cop.id IS NULL 
                        OR (
                            cop.status = 'pending'
                            AND cop.attempts < $1
                            AND (
                                cop.last_attempt IS NULL 
                                OR cop.last_attempt < now() - interval '1 hour'
                            )
                        )
                    )
                    ''',
                    MAX_PAYOUT_ATTEMPTS
                )

                logger.info(f"Found {len(regular_orders)} total paid regular orders and {len(cart_orders)} paid cart orders")

                # Filter orders that are eligible for payout
                eligible_orders = []
                
                # Process regular orders
                for record in regular_orders:
                    order = dict(record)  # Convert Record to dict
                    failure_count = order['failure_count'] or 0
                    last_attempt = order['last_attempt_time']
                    
                    if failure_count < MAX_PAYOUT_ATTEMPTS and (
                        not last_attempt or 
                        (datetime.now(timezone.utc) - last_attempt.replace(tzinfo=timezone.utc)).total_seconds() > 3600
                    ):
                        order['order_type'] = 'regular'
                        eligible_orders.append(order)
                        logger.info(
                            f"regular order {order['id']} is eligible for payout "
                            f"(failures: {failure_count}, last_attempt: {last_attempt})"
                        )

                # Process cart orders
                for record in cart_orders:
                    order = dict(record)  # Convert Record to dict
                    failure_count = order['failure_count'] or 0
                    last_attempt = order['last_attempt_time']
                    
                    if failure_count < MAX_PAYOUT_ATTEMPTS and (
                        not last_attempt or 
                        (datetime.now(timezone.utc) - last_attempt.replace(tzinfo=timezone.utc)).total_seconds() > 3600
                    ):
                        order['order_type'] = 'cart'
                        eligible_orders.append(order)
                        logger.info(
                            f"cart order {order['id']} is eligible for payout "
                            f"(failures: {failure_count}, last_attempt: {last_attempt})"
                        )

                logger.info(f"Found {len(eligible_orders)} total orders eligible for payout processing")
                return eligible_orders

        except Exception as e:
            logger.error(f"Error getting orders for payout: {e}")
            return []

    async def _process_order_payout(self, conn, order: Dict[str, Any]):
        """Process payout for a single order.
        
        Args:
            conn: Database connection
            order: Order details
            
        Raises:
            PayoutError: If payout fails
        """
        order_id = order['id']
        logger.info(f"Starting payout process for order {order_id}")
        
        # Get order items with listing details
        items = await conn.fetch(
            '''
            SELECT 
                oi.*,
                l.seller_address,
                l.deposit_address,
                l.id as listing_id
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN listings l ON l.id = o.listing_id
            WHERE oi.order_id = $1
            ''',
            order_id
        )
        
        if not items:
            raise PayoutError(f"No items found for order {order_id}")
            
        logger.info(f"Processing {len(items)} items for order {order_id}")
        
        # Group payments by seller
        seller_payments = {}
        for item in items:
            seller_address = item['seller_address']
            price_evr = item['price_evr']
            
            if seller_address not in seller_payments:
                seller_payments[seller_address] = Decimal('0')
            seller_payments[seller_address] += price_evr
            logger.info(f"Added {price_evr} EVR payment for seller {seller_address}")
            
        # Calculate total fees
        total_fees = sum(item['fee_evr'] for item in items)
        logger.info(f"Total fees for order {order_id}: {total_fees} EVR")
        
        try:
            # First send assets to buyer
            for item in items:
                try:
                    logger.info(
                        f"Transferring {item['amount']} {item['asset_name']} "
                        f"to {order['buyer_address']}"
                    )
                    
                    # Validate asset exists
                    try:
                        asset_info = rpc_client.getassetdata(item['asset_name'])
                        logger.info(f"Asset info: {asset_info}")
                    except Exception as e:
                        logger.error(f"Failed to get asset data for {item['asset_name']}: {e}")
                        raise PayoutError(f"Asset {item['asset_name']} not found or invalid")

                    # Validate amount is valid
                    amount = float(item['amount'])  # Convert to float for RPC
                    logger.info(f"Attempting transfer with amount: {amount}")
                    
                    # Transfer asset using transferfromaddress instead of transfer
                    result = rpc_client.transferfromaddress(
                        item['asset_name'],      # Asset name
                        item['deposit_address'], # From address (listing's deposit address)
                        amount,                  # Amount
                        order['buyer_address'],  # To address
                        "",                      # Message
                        0,                       # Expire time
                        item['deposit_address'], # EVR change address (back to listing)
                        item['deposit_address']  # Asset change address (back to listing)
                    )
                    tx_hash = result[0] if isinstance(result, list) else result
                    logger.info(f"Transfer successful: {tx_hash}")
                    
                    # Record outgoing transaction
                    await conn.execute(
                        '''
                        INSERT INTO transaction_entries (
                            tx_hash, address, entry_type, asset_name,
                            amount, fee, confirmations, time,
                            asset_type, asset_message, trusted,
                            created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, now(), now())
                        ''',
                        tx_hash,                    # tx_hash
                        item['deposit_address'],    # address
                        'send',                     # entry_type
                        item['asset_name'],         # asset_name
                        item['amount'],             # amount
                        Decimal('0'),               # fee
                        0,                          # confirmations
                        datetime.now(timezone.utc), # time
                        'transfer_asset',           # asset_type
                        '',                         # asset_message
                        True                        # trusted
                    )
                    
                    # Update fulfillment info
                    await conn.execute(
                        '''
                        UPDATE order_items 
                        SET 
                            fulfillment_time = now(),
                            fulfillment_tx_hash = $3,
                            updated_at = now()
                        WHERE order_id = $1 AND asset_name = $2
                        ''',
                        order_id,
                        item['asset_name'],
                        tx_hash
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to transfer {item['asset_name']}: {e}")
                    raise PayoutError(f"Failed to transfer {item['asset_name']}: {str(e)}")
            
            # Then send EVR to sellers and fee address using sendmany
            # Convert all amounts to float for RPC
            payments = {
                addr: float(amount)  # Convert Decimal to float
                for addr, amount in seller_payments.items()
            }
            if total_fees > 0:
                payments[DEFAULT_FEE_ADDRESS] = float(total_fees)
            
            # Send all EVR payments in one transaction
            try:
                logger.info(f"Sending EVR payments for order {order_id}: {payments}")
                tx_hash = rpc_client.sendmany(
                    "",  # fromaccount
                    payments,  # amounts
                    1,  # minconf
                    f"Order {order_id} payout"  # comment
                )
                logger.info(f"EVR payments successful: {tx_hash}")
                
                # Record outgoing EVR transactions
                for address, amount in payments.items():
                    await conn.execute(
                        '''
                        INSERT INTO transaction_entries (
                            tx_hash, address, entry_type, asset_name,
                            amount, fee, confirmations, time,
                            trusted, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now(), now())
                        ''',
                        tx_hash,                    # tx_hash
                        address,                    # address
                        'send',                     # entry_type
                        'EVR',                      # asset_name
                        Decimal(str(amount)),       # amount
                        Decimal('0'),               # fee
                        0,                          # confirmations
                        datetime.now(timezone.utc), # time
                        True                        # trusted
                    )
                    
            except Exception as e:
                logger.error(f"Failed to send EVR payments: {e}")
                raise PayoutError(f"Failed to send EVR payments: {str(e)}")
            
            # Record successful payout
            await conn.execute(
                '''
                INSERT INTO order_payouts (
                    order_id, 
                    status,
                    amount,
                    asset_name,
                    to_address,
                    tx_hash,
                    completed_at
                ) VALUES ($1, 'completed', $2, 'EVR', $3, $4, now())
                ON CONFLICT (order_id) DO UPDATE
                SET 
                    status = 'completed',
                    amount = EXCLUDED.amount,
                    tx_hash = EXCLUDED.tx_hash,
                    completed_at = EXCLUDED.completed_at,
                    updated_at = now()
                ''',
                order_id,
                total_fees,
                DEFAULT_FEE_ADDRESS,
                tx_hash
            )
            
            # Update order status
            await conn.execute(
                '''
                UPDATE orders 
                SET 
                    status = 'completed',
                    updated_at = now()
                WHERE id = $1
                ''',
                order_id
            )
            
            # Let the blockchain monitor handle balance updates
            # Wait a moment for the transaction to be seen
            await asyncio.sleep(2)
            
            logger.info(f"Successfully processed payout for order {order_id}")
            
        except Exception as e:
            logger.error(f"Error processing payout for order {order_id}: {e}")
            raise PayoutError(f"Payout failed: {str(e)}")
            
    async def _update_payout_failure(self, order_id: UUID):
        """Update failure count for an order payout.
        
        Args:
            order_id: The order UUID
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO order_payouts (
                    order_id,
                    status,
                    attempts,
                    last_attempt
                ) VALUES ($1, 'pending', 1, now())
                ON CONFLICT (order_id) DO UPDATE
                SET 
                    attempts = order_payouts.attempts + 1,
                    last_attempt = now(),
                    updated_at = now()
                ''',
                order_id
            )

    async def _process_cart_order_payout(self, conn, cart_order: Dict[str, Any]):
        """Process payout for a cart order.
        
        Args:
            conn: Database connection
            cart_order: Cart order details
            
        Raises:
            PayoutError: If payout fails
        """
        cart_order_id = cart_order['id']
        logger.info(f"Starting payout process for cart order {cart_order_id}")
        
        # Get cart order items with listing details
        items = await conn.fetch(
            '''
            SELECT 
                coi.*,
                l.seller_address,
                l.deposit_address,
                l.name as listing_name
            FROM cart_order_items coi
            JOIN listings l ON l.id = coi.listing_id
            WHERE coi.cart_order_id = $1
            ''',
            cart_order_id
        )
        
        if not items:
            raise PayoutError(f"No items found for cart order {cart_order_id}")
            
        logger.info(f"Processing {len(items)} items for cart order {cart_order_id}")
        
        # Group payments by seller
        seller_payments = {}
        for item in items:
            seller_address = item['seller_address']
            price_evr = item['price_evr']
            
            if seller_address not in seller_payments:
                seller_payments[seller_address] = Decimal('0')
            seller_payments[seller_address] += price_evr
            logger.info(f"Added {price_evr} EVR payment for seller {seller_address}")
            
        # Calculate total fees
        total_fees = sum(item['fee_evr'] for item in items)
        logger.info(f"Total fees for cart order {cart_order_id}: {total_fees} EVR")
        
        try:
            # First send assets to buyer
            for item in items:
                try:
                    logger.info(
                        f"Transferring {item['amount']} {item['asset_name']} "
                        f"to {cart_order['buyer_address']}"
                    )
                    
                    # Validate asset exists
                    try:
                        asset_info = rpc_client.getassetdata(item['asset_name'])
                        logger.info(f"Asset info: {asset_info}")
                    except Exception as e:
                        logger.error(f"Failed to get asset data for {item['asset_name']}: {e}")
                        raise PayoutError(f"Asset {item['asset_name']} not found or invalid")

                    # Validate amount is valid
                    amount = float(item['amount'])  # Convert to float for RPC
                    logger.info(f"Attempting transfer with amount: {amount}")
                    
                    # Transfer asset using transferfromaddress instead of transfer
                    result = rpc_client.transferfromaddress(
                        item['asset_name'],      # Asset name
                        item['deposit_address'], # From address (listing's deposit address)
                        amount,                  # Amount
                        cart_order['buyer_address'],  # To address
                        "",                      # Message
                        0,                       # Expire time
                        item['deposit_address'], # EVR change address (back to listing)
                        item['deposit_address']  # Asset change address (back to listing)
                    )
                    tx_hash = result[0] if isinstance(result, list) else result
                    logger.info(f"Transfer successful: {tx_hash}")
                    
                    # Record outgoing transaction
                    await conn.execute(
                        '''
                        INSERT INTO transaction_entries (
                            tx_hash, address, entry_type, asset_name,
                            amount, fee, confirmations, time,
                            asset_type, asset_message, trusted,
                            created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, now(), now())
                        ''',
                        tx_hash,                    # tx_hash
                        item['deposit_address'],    # address
                        'send',                     # entry_type
                        item['asset_name'],         # asset_name
                        item['amount'],             # amount
                        Decimal('0'),               # fee
                        0,                          # confirmations
                        datetime.now(timezone.utc), # time
                        'transfer_asset',           # asset_type
                        '',                         # asset_message
                        True                        # trusted
                    )
                    
                    # Record sale
                    await conn.execute(
                        '''
                        INSERT INTO sale_history (
                            cart_order_id,
                            listing_id,
                            asset_name,
                            amount,
                            price_evr,
                            seller_address,
                            buyer_address,
                            sale_time
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, now())
                        ''',
                        cart_order_id,
                        item['listing_id'],
                        item['asset_name'],
                        item['amount'],
                        item['price_evr'],
                        item['seller_address'],
                        cart_order['buyer_address']
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to transfer {item['asset_name']}: {e}")
                    raise PayoutError(f"Failed to transfer {item['asset_name']}: {str(e)}")
            
            # Then send EVR to sellers and fee address using sendmany
            # Convert all amounts to float for RPC
            payments = {
                addr: float(amount)  # Convert Decimal to float
                for addr, amount in seller_payments.items()
            }
            if total_fees > 0:
                payments[DEFAULT_FEE_ADDRESS] = float(total_fees)
            
            # Send all EVR payments in one transaction
            try:
                logger.info(f"Sending EVR payments for cart order {cart_order_id}: {payments}")
                tx_hash = rpc_client.sendmany(
                    "",  # fromaccount
                    payments,  # amounts
                    1,  # minconf
                    f"Cart order {cart_order_id} payout"  # comment
                )
                logger.info(f"EVR payments successful: {tx_hash}")
                
                # Record outgoing EVR transactions
                for address, amount in payments.items():
                    await conn.execute(
                        '''
                        INSERT INTO transaction_entries (
                            tx_hash, address, entry_type, asset_name,
                            amount, fee, confirmations, time,
                            trusted, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now(), now())
                        ''',
                        tx_hash,                    # tx_hash
                        address,                    # address
                        'send',                     # entry_type
                        'EVR',                      # asset_name
                        Decimal(str(amount)),       # amount
                        Decimal('0'),               # fee
                        0,                          # confirmations
                        datetime.now(timezone.utc), # time
                        True                        # trusted
                    )
                    
            except Exception as e:
                logger.error(f"Failed to send EVR payments: {e}")
                raise PayoutError(f"Failed to send EVR payments: {str(e)}")
            
            # Record successful payout
            await conn.execute(
                '''
                INSERT INTO order_payouts (
                    cart_order_id, 
                    status,
                    amount,
                    asset_name,
                    to_address,
                    tx_hash,
                    completed_at
                ) VALUES ($1, 'completed', $2, 'EVR', $3, $4, now())
                ON CONFLICT (cart_order_id) DO UPDATE
                SET 
                    status = 'completed',
                    amount = EXCLUDED.amount,
                    tx_hash = EXCLUDED.tx_hash,
                    completed_at = EXCLUDED.completed_at,
                    updated_at = now()
                ''',
                cart_order_id,
                total_fees,
                DEFAULT_FEE_ADDRESS,
                tx_hash
            )
            
            # Update cart order status
            await conn.execute(
                '''
                UPDATE cart_orders 
                SET 
                    status = 'completed',
                    updated_at = now()
                WHERE id = $1
                ''',
                cart_order_id
            )
            
            # Let the blockchain monitor handle balance updates
            # Wait a moment for the transaction to be seen
            await asyncio.sleep(2)
            
            logger.info(f"Successfully processed payout for cart order {cart_order_id}")
            
        except Exception as e:
            logger.error(f"Error processing payout for cart order {cart_order_id}: {e}")
            raise PayoutError(f"Payout failed: {str(e)}")
            
    async def _update_cart_order_payout_failure(self, cart_order_id: UUID):
        """Update failure count for a cart order payout.
        
        Args:
            cart_order_id: The cart order UUID
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO order_payouts (
                    cart_order_id,
                    status,
                    attempts,
                    last_attempt
                ) VALUES ($1, 'pending', 1, now())
                ON CONFLICT (cart_order_id) DO UPDATE
                SET 
                    attempts = order_payouts.attempts + 1,
                    last_attempt = now(),
                    updated_at = now()
                ''',
                cart_order_id
            )

# Export public interface
__all__ = [
    'OrderManager',
    'OrderError',
    'InsufficientBalanceError',
    'ListingNotFoundError',
    'AssetNotFoundError',
    'PayoutManager',
    'PayoutError',
    'InsufficientFundsError'
] 