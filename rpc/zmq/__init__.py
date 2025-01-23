"""ZMQ module for subscribing to Evrmore node notifications

This module provides a high-level interface for subscribing to ZeroMQ notifications from an Evrmore node.
It handles the complexity of ZMQ socket management, async operations, and thread safety.

Example usage:
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

Available ZMQ topics:
    - hashtx: New transaction hashes
    - rawtx: New transactions in raw format
    - hashblock: New block hashes
    - rawblock: New blocks in raw format
    - sequence: Sequence notifications for chain reorganizations

Configuration:
    The module reads ZMQ endpoints from evrmore.conf using the following settings:
    - zmqpubhashtx: Endpoint for transaction hash notifications
    - zmqpubrawtx: Endpoint for raw transaction notifications
    - zmqpubhashblock: Endpoint for block hash notifications
    - zmqpubrawblock: Endpoint for raw block notifications
    - zmqpubsequence: Endpoint for sequence notifications

Thread Safety:
    This module is designed to be thread-safe and can handle both synchronous and
    asynchronous callbacks. It uses a queue-based system to safely pass notifications
    from ZMQ threads to the async event loop.
"""
import zmq
import asyncio
from typing import Dict, Callable, Any, Optional, List, Union, Awaitable
from config import evrmore_conf

class ZMQNotification:
    """Base class for ZMQ notifications from the Evrmore node.
    
    This class represents a notification received from the Evrmore node via ZMQ.
    Different notification types (transactions, blocks, etc.) inherit from this base class.
    
    Attributes:
        topic (bytes): The ZMQ topic this notification was received on
        body (bytes): The notification payload (e.g., transaction or block hash)
        sequence (int): Monotonically increasing sequence number for this notification type
    """
    def __init__(self, topic: bytes, body: bytes, sequence: int):
        self.topic = topic
        self.body = body
        self.sequence = sequence

class HashTxNotification(ZMQNotification):
    """Transaction hash notification.
    
    Received when a new transaction enters the mempool.
    The body contains the transaction hash in raw bytes (32 bytes).
    """
    pass

class RawTxNotification(ZMQNotification):
    """Raw transaction notification.
    
    Received when a new transaction enters the mempool.
    The body contains the complete raw transaction data.
    """
    pass

class HashBlockNotification(ZMQNotification):
    """Block hash notification.
    
    Received when a new block is added to the chain.
    The body contains the block hash in raw bytes (32 bytes).
    """
    pass

class RawBlockNotification(ZMQNotification):
    """Raw block notification.
    
    Received when a new block is added to the chain.
    The body contains the complete raw block data.
    """
    pass

class SequenceNotification(ZMQNotification):
    """Sequence notification.
    
    Received during chain reorganizations.
    Used to maintain consistency in the notification sequence.
    """
    pass

class ZMQHandler:
    """Handles ZMQ subscriptions to Evrmore node notifications.
    
    This class manages ZMQ socket connections, subscriptions, and notification processing.
    It provides thread-safe handling of notifications and supports both sync and async callbacks.
    
    The handler uses a queue-based system to safely pass notifications from ZMQ threads
    to the async event loop, where callbacks are executed.
    
    Attributes:
        context (zmq.Context): ZMQ context for creating sockets
        sockets (Dict[str, zmq.Socket]): Map of endpoint URLs to socket subscriptions
        callbacks (Dict[bytes, List[Callable]]): Map of topics to callback functions
        queue (asyncio.Queue): Queue for passing notifications between threads
        loop (asyncio.AbstractEventLoop): Main event loop for async operations
        running (bool): Flag to control socket threads
        processor_task (asyncio.Task): Task for processing notifications from the queue
    """
    
    def __init__(self):
        """Initialize ZMQ handler with endpoints from evrmore.conf.
        
        Reads ZMQ endpoint configuration from evrmore.conf and sets up the basic
        infrastructure for handling notifications. No connections are made until
        subscribe() is called.
        """
        self.context = zmq.Context()
        
        # Map of endpoint URLs to socket subscriptions
        self.sockets: Dict[str, zmq.Socket] = {}
        
        # Map of topics to callback functions (can be sync or async)
        self.callbacks: Dict[bytes, List[Callable[[ZMQNotification], Union[None, Awaitable[None]]]]] = {}
        
        # Queue for processing notifications
        self.queue: asyncio.Queue = asyncio.Queue()
        
        # Store main event loop
        self.loop = None
        
        # Get endpoints from config
        self.endpoints = {
            b"hashtx": evrmore_conf['zmqpubhashtx'],
            b"rawtx": evrmore_conf['zmqpubrawtx'],
            b"hashblock": evrmore_conf['zmqpubhashblock'],
            b"rawblock": evrmore_conf['zmqpubrawblock'],
            b"sequence": evrmore_conf['zmqpubsequence']
        }
        
        # Map topics to notification types
        self.notification_types = {
            b"hashtx": HashTxNotification,
            b"rawtx": RawTxNotification,
            b"hashblock": HashBlockNotification,
            b"rawblock": RawBlockNotification,
            b"sequence": SequenceNotification
        }
        
        # Task for processing notifications
        self.processor_task = None
        
        # Flag to control socket threads
        self.running = True
    
    def subscribe(self, topics: List[bytes], callback: Callable[[ZMQNotification], Union[None, Awaitable[None]]]) -> None:
        """Subscribe to ZMQ notifications for specified topics.
        
        This method sets up ZMQ socket subscriptions and registers callbacks for the
        specified topics. Multiple callbacks can be registered for the same topic.
        Both synchronous and asynchronous callbacks are supported.
        
        Args:
            topics: List of topics to subscribe to (e.g. [b"hashtx", b"hashblock"])
            callback: Function to call when notification is received.
                     Can be either a regular function or an async coroutine.
        
        Raises:
            ValueError: If an invalid topic is specified
        """
        for topic in topics:
            if topic not in self.endpoints:
                raise ValueError(f"Invalid topic: {topic}")
            
            # Add callback to list for this topic
            if topic not in self.callbacks:
                self.callbacks[topic] = []
            self.callbacks[topic].append(callback)
            
            # Create socket if endpoint not already subscribed
            endpoint = self.endpoints[topic]
            if endpoint not in self.sockets:
                socket = self.context.socket(zmq.SUB)
                socket.connect(endpoint)
                socket.setsockopt(zmq.SUBSCRIBE, topic)
                self.sockets[endpoint] = socket
    
    async def _process_notifications(self):
        """Process notifications from the queue.
        
        This internal coroutine runs continuously, pulling notifications from the queue
        and executing the appropriate callbacks. It handles both sync and async callbacks
        and ensures proper error handling.
        """
        while True:
            try:
                notification = await self.queue.get()
                callbacks = self.callbacks.get(notification.topic, [])
                
                for callback in callbacks:
                    try:
                        # Check if callback is async
                        if asyncio.iscoroutinefunction(callback):
                            await callback(notification)
                        else:
                            callback(notification)
                    except Exception as e:
                        print(f"Error in callback: {e}")
                
                self.queue.task_done()
            except Exception as e:
                print(f"Error processing notification: {e}")
                await asyncio.sleep(1)
    
    def _handle_socket(self, socket: zmq.Socket, loop: asyncio.AbstractEventLoop) -> None:
        """Handle messages from a ZMQ socket.
        
        This method runs in a separate thread for each socket. It receives messages
        from the socket and safely passes them to the async event loop via a queue.
        
        Args:
            socket: ZMQ socket to receive messages from
            loop: Event loop to use for scheduling callbacks
        """
        while self.running:
            try:
                # Use poll to allow checking running flag
                if socket.poll(timeout=1000):  # 1 second timeout
                    # Receive multipart message [topic, body, sequence]
                    topic, body, sequence = socket.recv_multipart()
                    
                    # Create appropriate notification type
                    notification_type = self.notification_types.get(topic, ZMQNotification)
                    notification = notification_type(topic, body, int.from_bytes(sequence, 'little'))
                    
                    # Add notification to queue using call_soon_threadsafe
                    loop.call_soon_threadsafe(
                        self.queue.put_nowait,
                        notification
                    )
    
            except Exception as e:
                if self.running:  # Only print error if we're still supposed to be running
                    print(f"Error receiving ZMQ message: {e}")
                    # Sleep using time.sleep since we're in a thread
                    import time
                    time.sleep(1)  # Wait before retrying
    
    async def start(self) -> None:
        """Start listening for ZMQ notifications.
        
        This method starts the notification processor and socket handlers.
        It will run indefinitely until close() is called or an error occurs.
        
        This is a coroutine and must be run in an event loop:
        ```python
        asyncio.run(handler.start())
        ```
        """
        self.loop = asyncio.get_running_loop()
        self.running = True
        tasks = []
        
        # Start notification processor
        self.processor_task = asyncio.create_task(self._process_notifications())
        tasks.append(self.processor_task)
        
        # Start socket handlers
        for endpoint, socket in self.sockets.items():
            tasks.append(self.loop.run_in_executor(
                None, 
                self._handle_socket,
                socket,
                self.loop
            ))
            
        await asyncio.gather(*tasks)
    
    def close(self) -> None:
        """Close all ZMQ sockets and stop processing.
        
        This method performs a clean shutdown of the ZMQ handler:
        1. Stops all socket threads
        2. Closes all sockets
        3. Terminates the ZMQ context
        4. Cancels the notification processor task
        """
        self.running = False
        
        for socket in self.sockets.values():
            socket.close()
        self.context.term()
        
        # Cancel processor task if running
        if self.processor_task and not self.processor_task.done():
            self.processor_task.cancel()

# Create global instance
handler = ZMQHandler()

# Export main interface
subscribe = handler.subscribe
start = handler.start
close = handler.close

__all__ = [
    'subscribe',
    'start',
    'close',
    'ZMQNotification',
    'HashTxNotification',
    'RawTxNotification',
    'HashBlockNotification',
    'RawBlockNotification',
    'SequenceNotification'
] 