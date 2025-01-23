"""Monitor module for tracking blockchain transactions and blocks.

This module provides real-time monitoring of blockchain activity including:
- Transaction tracking (EVR and assets)
- Block monitoring
- Confirmation updates
- Balance tracking per address
"""

import asyncio
import logging
from typing import Optional, Tuple, Literal

from rpc import getblockcount, getblock, getblockhash, getrawtransaction, gettransaction
from rpc.zmq import subscribe, start, close, ZMQNotification
from database import get_pool

# Configure logging
logger = logging.getLogger(__name__)

class TransactionMonitor:
    """Monitor blockchain transactions and blocks."""
    
    def __init__(self, pool):
        """Initialize the transaction monitor.
        
        Args:
            pool: Database connection pool
        """
        self.pool = pool
        self.running = True
        self.notification_queue = asyncio.Queue()
    
    async def process_new_block(self, block_hash: str) -> None:
        """Process a new block when received via ZMQ."""
        try:
            # Get full block data (RPC calls are not async)
            block_data = getblock(block_hash)
            
            # Store in database
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Insert new block
                    await conn.execute(
                        'INSERT INTO blocks (hash, height, timestamp) VALUES ($1, $2, $3)',
                        block_hash,
                        block_data['height'],
                        block_data['time']
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
                time = tx_data.get('time')
                trusted = wallet_tx.get('trusted', False)
                bip125_replaceable = wallet_tx.get('bip125-replaceable', 'no') == 'yes'
                fee = abs(wallet_tx.get('fee', 0)) if wallet_tx.get('fee') else 0
                
                # Store entries for regular EVR transactions
                entries = []
                for detail in wallet_tx.get('details', []):
                    if detail.get('address'):  # Only process if we have an address
                        entries.append({
                            'tx_hash': tx_hash,
                            'address': detail['address'],
                            'entry_type': detail['category'],  # 'send' or 'receive' relative to our wallet
                            'asset_name': 'EVR',  # Regular EVR transaction
                            'amount': abs(detail.get('amount', 0)),
                            'fee': fee if detail['category'] == 'send' else 0,  # Fee only on send entries
                            'confirmations': confirmations,
                            'time': time,
                            'vout': detail.get('vout'),
                            'trusted': trusted,
                            'bip125_replaceable': bip125_replaceable,
                            'abandoned': detail.get('abandoned', False)
                        })
                
                # Store entries for asset transactions
                for asset_detail in wallet_tx.get('asset_details', []):
                    if asset_detail.get('destination'):  # Only process if we have a destination
                        entries.append({
                            'tx_hash': tx_hash,
                            'address': asset_detail['destination'],
                            'entry_type': asset_detail['category'],  # 'send' or 'receive' relative to our wallet
                            'asset_name': asset_detail['asset_name'],
                            'amount': abs(asset_detail.get('amount', 0)),
                            'fee': fee if asset_detail['category'] == 'send' else 0,  # Fee only on send entries
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
                    logger.warning(f"No valid entries found for transaction {tx_hash}")
                    return
                
                # Store all entries in database
                async with self.pool.acquire() as conn:
                    async with conn.transaction():
                        for entry in entries:
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