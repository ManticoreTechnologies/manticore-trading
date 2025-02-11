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

                # Create balance entries for new assets
                await conn.execute(
                    '''
                    INSERT INTO listing_balances (listing_id, asset_name, confirmed_balance, pending_balance)
                    SELECT DISTINCT 
                        l.id,
                        te.asset_name,
                        0,
                        0
                    FROM transaction_entries te
                    JOIN listings l ON l.deposit_address = te.address
                    WHERE te.entry_type = 'receive'
                    AND NOT EXISTS (
                        SELECT 1 
                        FROM listing_balances lb 
                        WHERE lb.listing_id = l.id 
                        AND lb.asset_name = te.asset_name
                    )
                    ON CONFLICT (listing_id, asset_name) DO NOTHING
                    '''
                )

                # Update confirmed balances for listings
                await conn.execute(
                    '''
                    WITH confirmed_txs AS (
                        SELECT 
                            l.id as listing_id,
                            te.asset_name,
                            SUM(te.amount) as total_amount,
                            MAX(te.tx_hash) as last_tx_hash,
                            MAX(te.time) as last_tx_time
                        FROM transaction_entries te
                        JOIN listings l ON l.deposit_address = te.address
                        WHERE te.entry_type = 'receive' 
                        AND te.abandoned = false
                        AND te.confirmations >= $1
                        GROUP BY l.id, te.asset_name
                    )
                    UPDATE listing_balances lb
                    SET 
                        confirmed_balance = ct.total_amount,
                        last_confirmed_tx_hash = ct.last_tx_hash,
                        last_confirmed_tx_time = ct.last_tx_time,
                        updated_at = now()
                    FROM confirmed_txs ct
                    WHERE lb.listing_id = ct.listing_id
                    AND lb.asset_name = ct.asset_name
                    ''', 
                    self.min_confirmations
                )

                # Update pending balances for listings
                await conn.execute(
                    '''
                    WITH pending_txs AS (
                        SELECT 
                            l.id as listing_id,
                            te.asset_name,
                            SUM(te.amount) as total_amount
                        FROM transaction_entries te
                        JOIN listings l ON l.deposit_address = te.address
                        WHERE te.entry_type = 'receive'
                        AND te.abandoned = false
                        AND te.confirmations < $1
                        GROUP BY l.id, te.asset_name
                    )
                    UPDATE listing_balances lb
                    SET 
                        pending_balance = COALESCE(pt.total_amount, 0),
                        updated_at = now()
                    FROM pending_txs pt
                    WHERE lb.listing_id = pt.listing_id
                    AND lb.asset_name = pt.asset_name
                    ''',
                    self.min_confirmations
                )

                # Record balance changes in history
                await conn.execute(
                    '''
                    INSERT INTO inventory_history (
                        listing_id,
                        asset_name,
                        change_amount,
                        change_type,
                        tx_hash
                    )
                    SELECT 
                        l.id as listing_id,
                        te.asset_name,
                        te.amount,
                        CASE 
                            WHEN te.confirmations >= $1 THEN 'confirmed_deposit'
                            ELSE 'pending_deposit'
                        END as change_type,
                        te.tx_hash
                    FROM transaction_entries te
                    JOIN listings l ON l.deposit_address = te.address
                    WHERE te.entry_type = 'receive'
                    AND te.abandoned = false
                    AND te.confirmations = $1  -- Only record changes for newly confirmed txs
                    ''',
                    self.min_confirmations
                )

                # Log balance updates
                updated_balances = await conn.fetch(
                    '''
                    SELECT 
                        l.id as listing_id,
                        lb.asset_name,
                        lb.confirmed_balance,
                        lb.pending_balance
                    FROM listing_balances lb
                    JOIN listings l ON l.id = lb.listing_id
                    WHERE lb.updated_at >= now() - interval '1 minute'
                    '''
                )

                for balance in updated_balances:
                    logger.info(
                        f"Updated listing {balance['listing_id']} balances: "
                        f"Asset={balance['asset_name']}, "
                        f"Confirmed={balance['confirmed_balance']}, "
                        f"Pending={balance['pending_balance']}"
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

                # Extract input addresses
                input_addresses = set()
                for vin in tx_data.get('vin', []):
                    if 'txid' in vin:
                        try:
                            prev_tx = getrawtransaction(vin['txid'], True)
                            if 'vout' in vin and vin['vout'] < len(prev_tx.get('vout', [])):
                                prev_vout = prev_tx['vout'][vin['vout']]
                                if 'addresses' in prev_vout.get('scriptPubKey', {}):
                                    input_addresses.update(prev_vout['scriptPubKey']['addresses'])
                        except Exception as e:
                            logger.warning(f"Failed to get input address for {vin.get('txid')}: {e}")

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
                    # Only process receive entries for tracked addresses
                    if (detail.get('address') and 
                        detail['address'] in tracked_addresses and
                        detail['category'] == 'receive'):
                        
                        # Skip if this is a change output (address is both input and output)
                        if detail['address'] in input_addresses:
                            logger.debug(f"Skipping change output for {detail['address']}")
                            continue
                            
                        # Use Decimal for precise arithmetic
                        amount = quantize_amount(Decimal(str(abs(detail.get('amount', 0)))))
                        fee = quantize_amount(Decimal(str(abs(fee)))) if fee else Decimal('0')
                        
                        # Check if transaction was abandoned
                        abandoned = detail.get('abandoned', False)
                        if abandoned:
                            await self.handle_abandoned_transaction(
                                tx_hash,
                                detail['address'],
                                'EVR'
                            )
                            continue
                            
                        entries.append({
                            'tx_hash': tx_hash,
                            'address': detail['address'],
                            'entry_type': detail['category'],
                            'asset_name': 'EVR',
                            'amount': amount,
                            'fee': Decimal('0'),
                            'confirmations': confirmations,
                            'time': time,
                            'vout': detail.get('vout'),
                            'trusted': trusted,
                            'bip125_replaceable': bip125_replaceable,
                            'abandoned': abandoned
                        })
                
                # Store entries for asset transactions
                for asset_detail in wallet_tx.get('asset_details', []):
                    # Only process receive entries for tracked addresses
                    if (asset_detail.get('destination') and 
                        asset_detail['destination'] in tracked_addresses and
                        asset_detail['category'] == 'receive'):
                        
                        # Skip if this is a change output (address is both input and output)
                        if asset_detail['destination'] in input_addresses:
                            logger.debug(f"Skipping change output for {asset_detail['destination']}")
                            continue
                            
                        # Use Decimal for precise arithmetic
                        amount = quantize_amount(Decimal(str(abs(asset_detail.get('amount', 0)))))
                        fee = quantize_amount(Decimal(str(abs(fee)))) if fee else Decimal('0')
                        
                        # Check if transaction was abandoned
                        abandoned = asset_detail.get('abandoned', False)
                        if abandoned:
                            await self.handle_abandoned_transaction(
                                tx_hash,
                                asset_detail['destination'],
                                asset_detail.get('asset_name', 'EVR')
                            )
                            continue
                            
                        entries.append({
                            'tx_hash': tx_hash,
                            'address': asset_detail['destination'],
                            'entry_type': asset_detail['category'],
                            'asset_name': asset_detail.get('asset_name', 'EVR'),
                            'amount': amount,
                            'fee': Decimal('0'),
                            'confirmations': confirmations,
                            'time': time,
                            'asset_type': asset_detail.get('asset_type'),
                            'asset_message': asset_detail.get('message', ''),
                            'vout': asset_detail.get('vout'),
                            'trusted': trusted,
                            'bip125_replaceable': bip125_replaceable,
                            'abandoned': abandoned
                        })
                
                if not entries:
                    logger.debug(f"No relevant entries found for transaction {tx_hash}")
                    return
                
                # Store all entries in database and update balances
                async with self.pool.acquire() as conn:
                    async with conn.transaction():
                        for entry in entries:
                            # Store transaction entry
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

                            # Immediately update listing balances for this transaction
                            if entry['entry_type'] == 'receive' and not entry['abandoned']:
                                # Update or create balance entry
                                await conn.execute(
                                    '''
                                    INSERT INTO listing_balances (
                                        listing_id, asset_name, confirmed_balance, pending_balance
                                    )
                                    SELECT 
                                        l.id,
                                        $1,
                                        CASE WHEN $3::int >= $4::int THEN $2 ELSE 0 END,
                                        CASE WHEN $3::int < $4::int THEN $2 ELSE 0 END
                                    FROM listings l
                                    WHERE l.deposit_address = $5
                                    ON CONFLICT (listing_id, asset_name) DO UPDATE
                                    SET 
                                        confirmed_balance = CASE 
                                            WHEN $3::int >= $4::int THEN listing_balances.confirmed_balance + $2
                                            ELSE listing_balances.confirmed_balance
                                        END,
                                        pending_balance = CASE 
                                            WHEN $3::int < $4::int THEN listing_balances.pending_balance + $2
                                            ELSE listing_balances.pending_balance
                                        END,
                                        updated_at = now()
                                    ''',
                                    entry['asset_name'],
                                    entry['amount'],
                                    entry['confirmations'],
                                    self.min_confirmations,
                                    entry['address']
                                )

                            # Log transaction processing
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
    
    async def handle_abandoned_transaction(self, tx_hash: str, address: str, asset_name: str) -> None:
        """Handle an abandoned transaction by updating balances appropriately.
        
        Args:
            tx_hash: The transaction hash
            address: The deposit address
            asset_name: The asset name
        """
        try:
            async with self.pool.acquire() as conn:
                # Get transaction details
                tx = await conn.fetchrow(
                    '''
                    SELECT 
                        amount,
                        confirmations
                    FROM transaction_entries
                    WHERE tx_hash = $1
                    AND address = $2
                    AND asset_name = $3
                    AND entry_type = 'receive'
                    ''',
                    tx_hash,
                    address,
                    asset_name
                )
                
                if not tx:
                    return
                
                # Update listing balances
                await conn.execute(
                    '''
                    UPDATE listing_balances lb
                    SET 
                        confirmed_balance = CASE 
                            WHEN $3 >= $4 THEN confirmed_balance - $2
                            ELSE confirmed_balance
                        END,
                        pending_balance = CASE 
                            WHEN $3 < $4 THEN pending_balance - $2
                            ELSE pending_balance
                        END,
                        updated_at = now()
                    FROM listings l
                    WHERE l.id = lb.listing_id
                    AND l.deposit_address = $1
                    AND lb.asset_name = $5
                    ''',
                    address,
                    tx['amount'],
                    tx['confirmations'],
                    self.min_confirmations,
                    asset_name
                )
                
                # Record in history
                await conn.execute(
                    '''
                    INSERT INTO inventory_history (
                        listing_id,
                        asset_name,
                        change_amount,
                        change_type,
                        tx_hash
                    )
                    SELECT 
                        l.id,
                        $3,
                        -$2,
                        'abandoned',
                        $1
                    FROM listings l
                    WHERE l.deposit_address = $4
                    ''',
                    tx_hash,
                    tx['amount'],
                    asset_name,
                    address
                )
                
                logger.info(
                    f"Handled abandoned transaction {tx_hash} for {address}: "
                    f"{tx['amount']} {asset_name}"
                )
                
        except Exception as e:
            logger.error(f"Error handling abandoned transaction {tx_hash}: {e}")
    
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