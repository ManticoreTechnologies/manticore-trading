"""Monitor module for tracking blockchain transactions and blocks.

This module provides real-time monitoring of blockchain activity including:
- Transaction tracking (EVR and assets)
- Block monitoring
- Confirmation updates
- Balance tracking per address
- Listing deposit tracking
"""

import asyncio
import logging
from typing import Optional, Tuple, Literal
from datetime import datetime
from uuid import UUID
from decimal import Decimal, ROUND_DOWN

from rpc import getblockcount, getblock, getblockhash, getrawtransaction, gettransaction
from rpc.zmq import subscribe, start, close, ZMQNotification
from database import get_pool
from listings import ListingManager
from orders import OrderManager
from config import load_config

# Configure logging
logger = logging.getLogger(__name__)

def quantize_amount(amount: Decimal) -> Decimal:
    """Quantize amount to 8 decimal places, rounding down."""
    return Decimal(str(amount)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)

class TransactionMonitor:
    """Monitor blockchain transactions and blocks."""
    
    def __init__(self, pool=None, min_confirmations: int = 6):
        """Initialize the transaction monitor.
        
        Args:
            pool: Database connection pool
            min_confirmations: Minimum number of confirmations for a transaction to be considered confirmed
        """
        self.pool = pool  # Will be set in start() if not provided
        self.min_confirmations = min_confirmations
        self.running = True
        self.notification_queue = asyncio.Queue()
        self.listing_manager = ListingManager(pool)
        self.order_manager = OrderManager(pool)
        
        # Load config
        config = load_config()
        self.min_confirmations = int(config.get('DEFAULT', 'min_confirmations', fallback=6))
        logger.info(f"Using minimum confirmations: {self.min_confirmations}")
    
    async def process_new_block(self, block_hash: str) -> None:
        """Process a new block when received via ZMQ."""
        try:
            # Get full block data (RPC calls are not async)
            block_data = getblock(block_hash)
            
            # Convert Unix timestamp to datetime
            block_time = datetime.fromtimestamp(block_data['time'])
            
            # Store in database
            async with self.pool.acquire() as conn:
                # Insert new block
                await conn.execute(
                    'INSERT INTO blocks (hash, height, timestamp) VALUES ($1, $2, $3)',
                    block_hash,
                    block_data['height'],
                    block_time
                )
                
                # Increment confirmations for all previously confirmed transactions
                await conn.execute(
                    '''
                    UPDATE transaction_entries 
                    SET 
                        confirmations = confirmations + 1,
                        updated_at = now()
                    WHERE confirmations > 0
                    '''
                )

                # Find newly confirmed transactions for listing addresses
                newly_confirmed_listings = await conn.fetch(
                    '''
                    WITH tx_entries AS (
                        -- First get all receive entries that just reached min_confirmations
                        SELECT 
                            te.tx_hash,
                            te.address,
                            te.asset_name,
                            te.amount,
                            te.confirmations,
                            te.time,
                            l.id as listing_id,
                            l.deposit_address,
                            -- Count how many receive entries exist for this tx/asset
                            COUNT(*) OVER (PARTITION BY te.tx_hash, te.asset_name) as receive_count
                        FROM transaction_entries te
                        JOIN listings l ON te.address = l.deposit_address
                        WHERE te.confirmations = $1
                        AND te.entry_type = 'receive'
                    )
                    -- Just get the confirmed transactions, no need to update balances
                    SELECT DISTINCT ON (tx_hash, asset_name)
                        tx_hash,
                        address,
                        asset_name,
                        CASE 
                            WHEN receive_count > 1 THEN amount / receive_count  -- Split amount for self-sends
                            ELSE amount
                        END as amount,
                        confirmations,
                        time,
                        listing_id,
                        deposit_address
                    FROM tx_entries
                    ORDER BY tx_hash, asset_name, address
                    ''',
                    self.min_confirmations
                )

                # Find newly confirmed transactions for order addresses
                newly_confirmed_orders = await conn.fetch(
                    '''
                    WITH tx_entries AS (
                        -- First get all receive entries that just reached min_confirmations
                        SELECT 
                            te.tx_hash,
                            te.address,
                            te.asset_name,
                            te.amount,
                            te.confirmations,
                            te.time,
                            o.id as order_id,
                            o.payment_address,
                            -- Count how many receive entries exist for this tx/asset
                            COUNT(*) OVER (PARTITION BY te.tx_hash, te.asset_name) as receive_count
                        FROM transaction_entries te
                        JOIN orders o ON te.address = o.payment_address
                        WHERE te.confirmations = $1
                        AND te.entry_type = 'receive'
                    )
                    -- Just get the confirmed transactions, no need to update balances
                    SELECT DISTINCT ON (tx_hash, asset_name)
                        tx_hash,
                        address,
                        asset_name,
                        CASE 
                            WHEN receive_count > 1 THEN amount / receive_count  -- Split amount for self-sends
                            ELSE amount
                        END as amount,
                        confirmations,
                        time,
                        order_id,
                        payment_address
                    FROM tx_entries
                    ORDER BY tx_hash, asset_name, address
                    ''',
                    self.min_confirmations
                )

                # Log only the transaction confirmations
                for update in newly_confirmed_listings:
                    logger.info(
                        f"Confirmed transaction for listing {update['listing_id']}: "
                        f"{update['amount']} {update['asset_name']} "
                        f"(tx: {update['tx_hash']})"
                    )

                for update in newly_confirmed_orders:
                    logger.info(
                        f"Confirmed transaction for order {update['order_id']}: "
                        f"{update['amount']} {update['asset_name']} "
                        f"(tx: {update['tx_hash']})"
                    )
            
            logger.info(f"Processed block {block_data['height']} ({block_hash})")
        except Exception as e:
            logger.error(f"Error processing block {block_hash}: {e}")
    
    async def process_new_transaction(self, tx_hash: str) -> None:
        """Process a new transaction when received via ZMQ."""
        try:
            # First check if this transaction is related to our wallet
            try:
                # gettransaction only works for wallet transactions
                wallet_tx = gettransaction(tx_hash)
                logger.debug(f"Transaction {tx_hash} found in wallet")
            except Exception as e:
                if "Invalid or non-wallet transaction id" in str(e):
                    logger.debug(f"Transaction {tx_hash} not related to wallet, skipping")
                    return
                raise  # Re-raise other errors
            
            # If we get here, it's a wallet transaction - get full details
            try:
                tx_data = getrawtransaction(tx_hash, True)
                confirmations = tx_data.get('confirmations', 0)
                logger.debug(f"Wallet transaction {tx_hash} found with {confirmations} confirmations")
                
                # Get common transaction details
                time = datetime.fromtimestamp(tx_data.get('time', 0)) if tx_data.get('time') else None
                trusted = wallet_tx.get('trusted', False)
                bip125_replaceable = wallet_tx.get('bip125-replaceable', 'no') == 'yes'
                fee = abs(wallet_tx.get('fee', 0)) if wallet_tx.get('fee') else 0

                async with self.pool.acquire() as conn:
                    # Get all listing and order deposit addresses
                    listing_addresses = await conn.fetch(
                        '''
                        SELECT deposit_address, listing_address 
                        FROM listings
                        '''
                    )
                    order_addresses = await conn.fetch(
                        '''
                        SELECT payment_address 
                        FROM orders
                        '''
                    )
                    cart_order_addresses = await conn.fetch(
                        '''
                        SELECT payment_address 
                        FROM cart_orders
                        '''
                    )

                    # Create sets for faster lookup
                    tracked_addresses = set()
                    for row in listing_addresses:
                        tracked_addresses.add(row['deposit_address'])
                        tracked_addresses.add(row['listing_address'])
                    tracked_addresses.update(row['payment_address'] for row in order_addresses)
                    tracked_addresses.update(row['payment_address'] for row in cart_order_addresses)
                
                # Store entries for regular EVR transactions
                entries = []
                for detail in wallet_tx.get('details', []):
                    if (detail.get('address') and 
                        detail['address'] in tracked_addresses and
                        detail['category'] == 'receive'):  # Only process receive entries for tracked addresses
                        # Use Decimal for precise arithmetic
                        amount = quantize_amount(Decimal(str(abs(detail.get('amount', 0)))))
                        fee = quantize_amount(Decimal(str(abs(fee)))) if fee else Decimal('0')
                        entries.append({
                            'tx_hash': tx_hash,
                            'address': detail['address'],
                            'entry_type': detail['category'],  # Will always be 'receive'
                            'asset_name': 'EVR',  # Regular EVR transaction
                            'amount': amount,
                            'fee': Decimal('0'),  # No fee on receive entries
                            'confirmations': confirmations,
                            'time': time,
                            'vout': detail.get('vout'),
                            'trusted': trusted,
                            'bip125_replaceable': bip125_replaceable,
                            'abandoned': detail.get('abandoned', False)
                        })
                
                # Store entries for asset transactions
                for asset_detail in wallet_tx.get('asset_details', []):
                    if (asset_detail.get('destination') and 
                        asset_detail['destination'] in tracked_addresses and
                        asset_detail['category'] == 'receive'):  # Only process receive entries for tracked addresses
                        # Use Decimal for precise arithmetic
                        amount = quantize_amount(Decimal(str(abs(asset_detail.get('amount', 0)))))
                        fee = quantize_amount(Decimal(str(abs(fee)))) if fee else Decimal('0')
                        entries.append({
                            'tx_hash': tx_hash,
                            'address': asset_detail['destination'],
                            'entry_type': asset_detail['category'],  # Will always be 'receive'
                            'asset_name': asset_detail.get('asset_name', 'EVR'),  # Use EVR as default if no asset name
                            'amount': amount,
                            'fee': Decimal('0'),  # No fee on receive entries
                            'confirmations': confirmations,
                            'time': time,
                            'asset_type': asset_detail.get('asset_type'),
                            'asset_message': asset_detail.get('message', ''),
                            'vout': asset_detail.get('vout'),
                            'trusted': trusted,
                            'bip125_replaceable': bip125_replaceable,
                            'abandoned': asset_detail.get('abandoned', False)
                        })
                
                if not entries:
                    logger.debug(f"No relevant entries found for transaction {tx_hash}")
                    return
                
                # Store all entries in database
                async with self.pool.acquire() as conn:
                    for entry in entries:
                        # Check if we've already processed this transaction for this address
                        existing = await conn.fetchrow(
                            '''
                            SELECT tx_hash, address, entry_type, asset_name, amount
                            FROM transaction_entries
                            WHERE tx_hash = $1 AND address = $2 AND entry_type = $3 AND asset_name = $4
                            ''',
                            entry['tx_hash'],
                            entry['address'],
                            entry['entry_type'],
                            entry['asset_name']
                        )

                        # Store transaction entry - triggers will handle balance updates
                        await conn.execute(
                            '''
                            INSERT INTO transaction_entries (
                                tx_hash, address, entry_type, asset_name,
                                amount, fee, confirmations, time,
                                asset_type, asset_message, vout,
                                trusted, bip125_replaceable, abandoned,
                                updated_at
                            )
                            VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8,
                                $9, $10, $11, $12, $13, $14, now()
                            )
                            ON CONFLICT (tx_hash, address, entry_type, asset_name)
                            DO UPDATE SET
                                amount = $5,
                                fee = $6,
                                confirmations = $7,
                                time = $8,
                                asset_type = $9,
                                asset_message = $10,
                                vout = $11,
                                trusted = $12,
                                bip125_replaceable = $13,
                                abandoned = $14,
                                updated_at = now()
                            ''',
                            entry['tx_hash'],
                            entry['address'],
                            entry['entry_type'],
                            entry['asset_name'],
                            entry['amount'],
                            entry['fee'],
                            entry['confirmations'],
                            entry['time'],
                            entry.get('asset_type'),
                            entry.get('asset_message'),
                            entry['vout'],
                            entry['trusted'],
                            entry['bip125_replaceable'],
                            entry['abandoned']
                        )

                        # Log transaction processing
                        if entry['entry_type'] == 'receive':
                            # Get updated balances after trigger execution
                            listing_balance = await conn.fetchrow(
                                '''
                                SELECT l.id as listing_id, lb.pending_balance, lb.confirmed_balance
                                FROM listing_balances lb
                                JOIN listings l ON l.id = lb.listing_id
                                WHERE l.deposit_address = $1 AND lb.asset_name = $2
                                ''',
                                entry['address'],
                                entry['asset_name']
                            )
                            
                            order_balance = await conn.fetchrow(
                                '''
                                SELECT o.id as order_id, ob.pending_balance, ob.confirmed_balance
                                FROM order_balances ob
                                JOIN orders o ON o.id = ob.order_id
                                WHERE o.payment_address = $1 AND ob.asset_name = $2
                                ''',
                                entry['address'],
                                entry['asset_name']
                            )
                            
                            if listing_balance:
                                logger.info(
                                    f"Updated listing {listing_balance['listing_id']} balances: "
                                    f"Asset={entry['asset_name']}, "
                                    f"Pending={listing_balance['pending_balance']}, "
                                    f"Confirmed={listing_balance['confirmed_balance']}"
                                )
                            elif order_balance:
                                logger.info(
                                    f"Updated order {order_balance['order_id']} balances: "
                                    f"Asset={entry['asset_name']}, "
                                    f"Pending={order_balance['pending_balance']}, "
                                    f"Confirmed={order_balance['confirmed_balance']}"
                                )
                
                # Enhanced logging for all entries
                for entry in entries:
                    logger.info(
                        f"Processed {entry['entry_type']} entry for {entry['asset_name']}: "
                        f"tx={entry['tx_hash']}, address={entry['address']}, "
                        f"amount={entry['amount']}, confirmations={entry['confirmations']}"
                    )
                
            except Exception as e:
                if "No such mempool or blockchain transaction" in str(e):
                    logger.warning(f"Wallet transaction {tx_hash} not found in blockchain or mempool, skipping")
                    return
                raise  # Re-raise other errors
            
        except Exception as e:
            logger.error(f"Error processing transaction {tx_hash}: {e}")
    
    def handle_block(self, notification: ZMQNotification):
        """Handle new block notifications from ZMQ."""
        block_hash = notification.body.hex()
        # Add to queue instead of processing directly
        asyncio.get_event_loop().call_soon_threadsafe(
            self.notification_queue.put_nowait,
            ('block', block_hash)
        )
    
    def handle_transaction(self, notification: ZMQNotification):
        """Handle new transaction notifications from ZMQ."""
        tx_hash = notification.body.hex()
        # Add to queue instead of processing directly
        asyncio.get_event_loop().call_soon_threadsafe(
            self.notification_queue.put_nowait,
            ('tx', tx_hash)
        )
    
    async def process_notifications(self):
        """Process notifications from the queue"""
        while self.running:
            try:
                # Get notification from queue
                notification_type, hash_value = await self.notification_queue.get()
                
                # Process based on type
                if notification_type == 'tx':
                    await self.process_new_transaction(hash_value)
                elif notification_type == 'block':
                    await self.process_new_block(hash_value)
                    
                # Mark task as done
                self.notification_queue.task_done()
            except Exception as e:
                logger.error(f"Error processing notification: {e}")
                await asyncio.sleep(1)
    
    async def sync_historical_blocks(self, start_height: Optional[int] = None) -> None:
        """Sync historical blocks from a given height."""
        try:
            # RPC calls are not async
            current_height = getblockcount()
            
            # If no start height provided, start from genesis
            sync_height = start_height if start_height is not None else 0
            
            while sync_height <= current_height and self.running:
                block_hash = getblockhash(sync_height)
                await self.process_new_block(block_hash)
                sync_height += 1
                
        except Exception as e:
            logger.error(f"Error during historical sync: {e}")
    
    async def start(self) -> None:
        """Start the blockchain monitoring system."""
        try:
            # Initialize pool if not provided
            if self.pool is None:
                self.pool = await get_pool()
                self.listing_manager = ListingManager(self.pool)
                self.order_manager = OrderManager(self.pool)
            
            # Set up ZMQ subscriptions
            logger.info("Setting up ZMQ subscriptions...")
            subscribe([b"hashblock"], self.handle_block)
            subscribe([b"hashtx"], self.handle_transaction)
            
            # Create tasks for ZMQ monitoring and notification processing
            logger.info("Starting ZMQ listener and notification processor...")
            zmq_task = asyncio.create_task(start())
            notification_task = asyncio.create_task(self.process_notifications())
            
            # Wait for both tasks
            await asyncio.gather(zmq_task, notification_task)
            
        except Exception as e:
            logger.error(f"Fatal error in monitoring: {e}")
            close()  # Close ZMQ connections
            raise
    
    def stop(self):
        """Stop the blockchain monitoring system."""
        logger.info("Stopping blockchain monitoring...")
        self.running = False
        close()  # Close ZMQ connections

def monitor_transactions(pool) -> TransactionMonitor:
    """Create and return a new transaction monitor.
    
    Args:
        pool: Database connection pool
        
    Returns:
        TransactionMonitor: A new transaction monitor instance
    """
    return TransactionMonitor(pool)

# Export public interface
__all__ = [
    'monitor_transactions',
    'TransactionMonitor'
] 