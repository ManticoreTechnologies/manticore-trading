"""Test script to demonstrate WebSocket chat functionality."""

import asyncio
import json
import logging
import websockets
from test_profile_flow import ProfileClientTest  # Reuse auth flow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ChatClientTest:
    """Test harness for WebSocket chat functionality."""
    
    def __init__(self):
        self.api_url = "ws://localhost:8000/chat/ws"
        self.auth_token = None
        self.websocket = None
        
    async def connect(self):
        """Connect to WebSocket and authenticate."""
        logger.info("Connecting to WebSocket...")
        
        # First get auth token using profile test flow
        profile_test = ProfileClientTest()
        await profile_test.setup()
        self.auth_token = await profile_test.authenticate()
        
        # Connect to WebSocket
        self.websocket = await websockets.connect(self.api_url)
        
        # Send authentication message
        await self.websocket.send(json.dumps({
            "token": self.auth_token
        }))
        
        # Wait for connection confirmation
        response = await self.websocket.recv()
        data = json.loads(response)
        
        if data.get("type") == "connection_status" and data.get("data", {}).get("status") == "connected":
            logger.info("Successfully connected and authenticated")
        else:
            raise ValueError(f"Failed to authenticate: {data}")
            
    async def send_message(self, text: str, channel: str = "global"):
        """Send a chat message."""
        await self.websocket.send(json.dumps({
            "type": "chat_message",
            "data": {
                "text": text,
                "type": "global",
                "channel": channel
            }
        }))
        
        # Wait for confirmation
        response = await self.websocket.recv()
        data = json.loads(response)
        logger.info(f"Message response: {data}")
        
    async def subscribe_to_channel(self, channel: str):
        """Subscribe to a chat channel."""
        await self.websocket.send(json.dumps({
            "type": "subscribe",
            "data": {
                "channel": channel
            }
        }))
        
        # Wait for subscription confirmation
        response = await self.websocket.recv()
        data = json.loads(response)
        logger.info(f"Subscription response: {data}")
        
    async def update_presence(self, status: str):
        """Update presence status."""
        await self.websocket.send(json.dumps({
            "type": "presence",
            "data": {
                "status": status
            }
        }))
        
    async def listen_for_messages(self, timeout: int = 30):
        """Listen for incoming messages for a specified duration."""
        try:
            while True:
                response = await asyncio.wait_for(self.websocket.recv(), timeout)
                data = json.loads(response)
                logger.info(f"Received message: {data}")
        except asyncio.TimeoutError:
            logger.info("Finished listening for messages")
        
    async def run_test(self):
        """Run a comprehensive chat test."""
        try:
            # Connect and authenticate
            await self.connect()
            
            # Subscribe to a test channel
            await self.subscribe_to_channel("test_channel")
            
            # Update presence
            await self.update_presence("online")
            
            # Send a test message
            await self.send_message("Hello from test client!")
            
            # Listen for any responses
            await self.listen_for_messages(timeout=10)
            
            # Update presence before disconnecting
            await self.update_presence("offline")
            
            # Clean up
            if self.websocket:
                await self.websocket.close()
            
            logger.info("Chat test completed successfully!")
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            raise
        finally:
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()

if __name__ == "__main__":
    # Run the test
    test = ChatClientTest()
    try:
        asyncio.run(test.run_test())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 