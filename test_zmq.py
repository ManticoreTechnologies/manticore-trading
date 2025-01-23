"""Test script for ZMQ subscriptions and RPC functionality"""
import asyncio
from rpc.zmq import ZMQNotification, subscribe, start, close
from rpc import getblockcount, getblockhash, getblock, getmempoolinfo, getrawtransaction
import binascii

# Create a queue for processing ZMQ notifications
notification_queue = asyncio.Queue()

def handle_hashtx(notification: ZMQNotification):
    """Handle transaction hash notifications"""
    tx_hash = binascii.hexlify(notification.body).decode('ascii')
    print(f"New transaction: {tx_hash}")
    # Add to queue instead of creating task directly
    asyncio.get_event_loop().call_soon_threadsafe(
        notification_queue.put_nowait, 
        ('tx', tx_hash)
    )

def handle_hashblock(notification: ZMQNotification):
    """Handle block hash notifications"""
    block_hash = binascii.hexlify(notification.body).decode('ascii')
    print(f"New block: {block_hash}")
    # Add to queue instead of creating task directly
    asyncio.get_event_loop().call_soon_threadsafe(
        notification_queue.put_nowait,
        ('block', block_hash)
    )

def handle_sequence(notification: ZMQNotification):
    """Handle sequence notifications"""
    print(f"Sequence notification: {notification.sequence}")

async def process_new_transaction(tx_hash: str):
    """Process a new transaction using RPC calls"""
    try:
        # Get transaction details (verbose=True for decoded format)
        tx = getrawtransaction(tx_hash, True)
        print(f"\nTransaction details:")
        print(f"Version: {tx.get('version')}")
        print(f"Size: {tx.get('size')} bytes")
        print(f"Inputs: {len(tx.get('vin', []))}") 
        print(f"Outputs: {len(tx.get('vout', []))}")
        if 'time' in tx:
            print(f"Time: {tx.get('time')}")
    except Exception as e:
        print(f"Error processing transaction: {e}")

async def process_new_block(block_hash_hex: str):
    """Process a new block using RPC calls"""
    try:
        # Get block details
        block = getblock(block_hash_hex)
        print(f"\nBlock details:")
        print(f"Height: {block.get('height')}")
        print(f"Time: {block.get('time')}")
        print(f"Transactions: {len(block.get('tx', []))}")
    except Exception as e:
        print(f"Error processing block: {e}")

async def process_notifications():
    """Process notifications from the queue"""
    while True:
        try:
            # Get notification from queue
            notification_type, hash_value = await notification_queue.get()
            
            # Process based on type
            if notification_type == 'tx':
                await process_new_transaction(hash_value)
            elif notification_type == 'block':
                await process_new_block(hash_value)
                
            # Mark task as done
            notification_queue.task_done()
        except Exception as e:
            print(f"Error processing notification: {e}")
            await asyncio.sleep(1)

async def periodic_blockchain_check():
    """Periodically check blockchain status using RPC"""
    while True:
        try:
            # Get current block count
            block_count = getblockcount()
            print(f"\nCurrent block height: {block_count}")
            
            # Get latest block info
            block_hash = getblockhash(block_count)
            block = getblock(block_hash)
            print(f"Latest block time: {block.get('time')}")
            
            # Wait before next check
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            print(f"Error in blockchain check: {e}")
            await asyncio.sleep(5)  # Wait shorter time on error

async def check_mempool():
    """Periodically check mempool status using RPC"""
    while True:
        try:
            # Get mempool info
            mempool = getmempoolinfo()
            print(f"\nMempool status (10s check):")
            print(f"Size: {mempool.get('size')} transactions")
            print(f"Bytes: {mempool.get('bytes')} bytes")
            
            await asyncio.sleep(10)  # Check every 10 seconds
            
        except Exception as e:
            print(f"Error checking mempool: {e}")
            await asyncio.sleep(5)  # Wait shorter time on error

async def main():
    """Run ZMQ subscriptions and RPC checks concurrently"""
    try:
        # Subscribe to ZMQ notifications
        subscribe([b"hashtx", b"hashblock", b"sequence"], handle_hashtx)
        subscribe([b"hashblock"], handle_hashblock)
        subscribe([b"sequence"], handle_sequence)
        
        print("Starting monitoring. Press Ctrl+C to stop...")
        
        # Create tasks for ZMQ monitoring and periodic RPC checks
        zmq_task = asyncio.create_task(start())
        blockchain_task = asyncio.create_task(periodic_blockchain_check())
        mempool_task = asyncio.create_task(check_mempool())
        notification_task = asyncio.create_task(process_notifications())
        
        # Wait for all tasks indefinitely
        await asyncio.gather(zmq_task, blockchain_task, mempool_task, notification_task)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
        close()
    except Exception as e:
        print(f"Error: {e}")
        close()

if __name__ == "__main__":
    asyncio.run(main()) 