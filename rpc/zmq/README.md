# ZMQ Notification System

This module provides a high-level interface for subscribing to ZeroMQ notifications from an Evrmore node. It handles the complexity of ZMQ socket management, async operations, and thread safety.

## Features

- Real-time notifications for blockchain events
- Support for both synchronous and asynchronous callbacks
- Thread-safe notification handling
- Automatic reconnection on connection loss
- Clean shutdown handling

## Quick Start

```python
import asyncio
from rpc.zmq import subscribe, start, close, ZMQNotification

# Define handlers for different notification types
async def handle_tx(notification: ZMQNotification):
    tx_hash = notification.body.hex()
    print(f"New transaction: {tx_hash}")

async def handle_block(notification: ZMQNotification):
    block_hash = notification.body.hex()
    print(f"New block: {block_hash}")

# Subscribe to notifications
subscribe([b"hashtx"], handle_tx)
subscribe([b"hashblock"], handle_block)

# Start listening (this will block until interrupted)
try:
    asyncio.run(start())
except KeyboardInterrupt:
    close()
```

## Available Topics

| Topic | Description | Payload |
|-------|-------------|---------|
| `hashtx` | New transaction notifications | 32-byte transaction hash |
| `rawtx` | New transaction notifications | Complete raw transaction data |
| `hashblock` | New block notifications | 32-byte block hash |
| `rawblock` | New block notifications | Complete raw block data |
| `sequence` | Chain reorganization notifications | Sequence number |

## Configuration

The module reads ZMQ endpoints from your `evrmore.conf` file. The following settings are required:

```conf
# ZMQ notification endpoints
zmqpubhashtx=tcp://127.0.0.1:28332
zmqpubrawtx=tcp://127.0.0.1:28332
zmqpubhashblock=tcp://127.0.0.1:28332
zmqpubrawblock=tcp://127.0.0.1:28332
zmqpubsequence=tcp://127.0.0.1:28332
```

## Detailed Usage

### Subscribing to Notifications

You can subscribe to multiple topics with different callbacks:

```python
from rpc.zmq import subscribe, ZMQNotification

# Synchronous callback
def sync_handler(notification: ZMQNotification):
    print(f"Got notification on topic: {notification.topic}")

# Asynchronous callback
async def async_handler(notification: ZMQNotification):
    print(f"Processing notification: {notification.body.hex()}")

# Subscribe to multiple topics with different handlers
subscribe([b"hashtx", b"hashblock"], sync_handler)
subscribe([b"rawtx"], async_handler)
```

### Notification Types

Each notification type provides specific attributes:

```python
class ZMQNotification:
    topic: bytes    # The ZMQ topic (e.g., b"hashtx")
    body: bytes     # The notification payload
    sequence: int   # Monotonically increasing sequence number

# Specialized notification types
HashTxNotification      # Transaction hash notifications
RawTxNotification      # Raw transaction notifications
HashBlockNotification   # Block hash notifications
RawBlockNotification   # Raw block notifications
SequenceNotification   # Sequence notifications
```

### Error Handling

The module includes built-in error handling and recovery:

- Socket errors are caught and retried
- Callback errors are isolated and logged
- Clean shutdown on interrupt
- Automatic reconnection on connection loss

### Thread Safety

The module uses a queue-based system to safely pass notifications from ZMQ threads to the async event loop:

1. ZMQ sockets run in separate threads
2. Notifications are queued using thread-safe methods
3. Callbacks are executed in the main event loop
4. Both sync and async callbacks are supported

## Advanced Usage

### Custom Error Handling

```python
async def handle_tx_with_errors(notification: ZMQNotification):
    try:
        # Process transaction
        tx_hash = notification.body.hex()
        # ... do something with tx_hash ...
    except Exception as e:
        # Handle error
        print(f"Error processing transaction: {e}")
        # Optionally re-raise or handle differently
```

### Combining with RPC Calls

```python
from rpc import getrawtransaction
from rpc.zmq import subscribe

async def process_new_tx(notification: ZMQNotification):
    tx_hash = notification.body.hex()
    try:
        # Get full transaction details using RPC
        tx_details = getrawtransaction(tx_hash, True)
        print(f"New transaction with {len(tx_details['vin'])} inputs")
    except Exception as e:
        print(f"Error fetching transaction details: {e}")

# Subscribe to new transactions
subscribe([b"hashtx"], process_new_tx)
```

### Clean Shutdown

```python
import asyncio
import signal
from rpc.zmq import start, close

async def main():
    # Set up signal handlers
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, close)
    loop.add_signal_handler(signal.SIGTERM, close)
    
    try:
        await start()
    except Exception as e:
        print(f"Error: {e}")
        close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Best Practices

1. **Error Handling**: Always wrap callback logic in try-except blocks
2. **Resource Management**: Use the `close()` function for clean shutdown
3. **Async Usage**: Prefer async callbacks for better performance
4. **Topic Selection**: Subscribe only to needed topics to reduce overhead
5. **Configuration**: Verify ZMQ endpoints in `evrmore.conf` are correct

## Common Issues

1. **No Notifications**
   - Check if ZMQ is enabled in `evrmore.conf`
   - Verify endpoint addresses and ports
   - Check firewall settings

2. **Performance Issues**
   - Reduce number of subscriptions
   - Use async callbacks for heavy processing
   - Handle errors efficiently in callbacks

3. **Memory Leaks**
   - Always call `close()` on shutdown
   - Don't create new subscriptions in callbacks
   - Clean up resources in error handlers
