import asyncio
import signal
import logging
from typing import Optional, Tuple, Literal

from rpc import getblockcount, getblock, getblockhash, getrawtransaction
from rpc.zmq import subscribe, start, close, ZMQNotification
from database import init_db, get_pool, close as db_close

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
running = True

# Create a queue for processing ZMQ notifications
notification_queue = asyncio.Queue()

async def process_new_block(block_hash: str, pool) -> None:
    """Process a new block when received via ZMQ."""
    try:
        # Get full block data (RPC calls are not async)
        block_data = getblock(block_hash)
        
        # Store in database
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    'INSERT INTO blocks (hash, height, timestamp) VALUES ($1, $2, $3)',
                    block_hash,
                    block_data['height'],
                    block_data['time']
                )
        
        logger.info(f"Processed block {block_data['height']} ({block_hash})")
    except Exception as e:
        logger.error(f"Error processing block {block_hash}: {e}")

async def process_new_transaction(tx_hash: str, pool) -> None:
    """Process a new transaction when received via ZMQ."""
    try:
        # Try to get transaction details - if it fails, it might be in mempool
        try:
            # Get full transaction details with confirmations
            tx_data = getrawtransaction(tx_hash, True)
            confirmations = tx_data.get('confirmations', 0)
            logger.debug(f"Transaction {tx_hash} found with {confirmations} confirmations")
        except Exception as e:
            if "No such mempool or blockchain transaction" in str(e):
                logger.warning(f"Transaction {tx_hash} not found in blockchain or mempool, skipping")
                return
            raise  # Re-raise other errors
        
        # Store in database with UPSERT to handle confirmations
        async with pool.acquire() as conn:
            async with conn.transaction():
                # If confirmations is present in tx_data, use it directly
                # Otherwise, it's a new mempool transaction (0 confirmations)
                await conn.execute(
                    '''
                    INSERT INTO transactions (hash, version, size, time, confirmations, updated_at)
                    VALUES ($1, $2, $3, $4, $5, now())
                    ON CONFLICT (hash) DO UPDATE
                    SET 
                        confirmations = $5,  -- Use the actual confirmations from RPC
                        updated_at = now()
                    ''',
                    tx_hash,
                    tx_data['version'],
                    tx_data['size'],
                    tx_data.get('time'),
                    confirmations
                )
        
        logger.info(f"Processed transaction {tx_hash} (size: {tx_data['size']} bytes, confirmations: {confirmations})")
    except Exception as e:
        logger.error(f"Error processing transaction {tx_hash}: {e}")

def handle_block(notification: ZMQNotification):
    """Handle new block notifications from ZMQ."""
    block_hash = notification.body.hex()
    # Add to queue instead of processing directly
    asyncio.get_event_loop().call_soon_threadsafe(
        notification_queue.put_nowait,
        ('block', block_hash)
    )

def handle_transaction(notification: ZMQNotification):
    """Handle new transaction notifications from ZMQ."""
    tx_hash = notification.body.hex()
    # Add to queue instead of processing directly
    asyncio.get_event_loop().call_soon_threadsafe(
        notification_queue.put_nowait,
        ('tx', tx_hash)
    )

async def process_notifications(pool):
    """Process notifications from the queue"""
    while running:
        try:
            # Get notification from queue
            notification_type, hash_value = await notification_queue.get()
            
            # Process based on type
            if notification_type == 'tx':
                await process_new_transaction(hash_value, pool)
            elif notification_type == 'block':
                await process_new_block(hash_value, pool)
                
            # Mark task as done
            notification_queue.task_done()
        except Exception as e:
            logger.error(f"Error processing notification: {e}")
            await asyncio.sleep(1)

async def sync_historical_blocks(start_height: Optional[int] = None) -> None:
    """Sync historical blocks from a given height."""
    try:
        pool = await get_pool()
        # RPC calls are not async
        current_height = getblockcount()
        
        # If no start height provided, start from genesis
        sync_height = start_height if start_height is not None else 0
        
        while sync_height <= current_height and running:
            block_hash = getblockhash(sync_height)
            await process_new_block(block_hash, pool)
            sync_height += 1
            
    except Exception as e:
        logger.error(f"Error during historical sync: {e}")

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    logger.info("Shutdown signal received. Cleaning up...")
    running = False
    close()  # Close ZMQ connections
    asyncio.create_task(db_close())  # Close database connections

async def main():
    """Main application entry point."""
    try:
        # Initialize database
        logger.info("Initializing database...")
        await init_db()
        pool = await get_pool()
        
        # Set up ZMQ subscriptions
        logger.info("Setting up ZMQ subscriptions...")
        subscribe([b"hashblock"], handle_block)
        subscribe([b"hashtx"], handle_transaction)
        
        # Register shutdown handlers
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
        
        # Create tasks for ZMQ monitoring and notification processing
        logger.info("Starting ZMQ listener and notification processor...")
        zmq_task = asyncio.create_task(start())
        notification_task = asyncio.create_task(process_notifications(pool))
        
        # Wait for both tasks
        await asyncio.gather(zmq_task, notification_task)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        close()  # Close ZMQ connections
        await db_close()  # Close database connections
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
