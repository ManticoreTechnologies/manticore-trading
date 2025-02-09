"""WebSocket endpoints for real-time updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from typing import Dict, Set, Optional
from datetime import datetime
import logging
import json
import asyncio

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/ws",
    tags=["WebSocket"]
)

# Track active connections
active_connections: Dict[str, Set[WebSocket]] = {
    'listings': set(),
    'orders': set(),
    'market': set(),
    'notifications': set()
}

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 30

async def heartbeat(websocket: WebSocket):
    """Send periodic heartbeat to keep connection alive."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except Exception:
        pass

class ConnectionManager:
    def __init__(self):
        self.active_connections = active_connections

    async def connect(self, websocket: WebSocket, channel: str):
        """Accept connection and add to active connections."""
        await websocket.accept()
        self.active_connections[channel].add(websocket)
        logger.info(f"New connection established for channel: {channel}")

    def disconnect(self, websocket: WebSocket, channel: str):
        """Remove connection from active connections."""
        try:
            self.active_connections[channel].remove(websocket)
            logger.info(f"Connection closed for channel: {channel}")
        except KeyError:
            pass

    async def broadcast(self, channel: str, data: dict):
        """Broadcast message to all connections in a channel."""
        if channel not in self.active_connections:
            raise ValueError(f"Invalid channel: {channel}")
            
        dead_connections = set()
        message = {
            "type": "update",
            "channel": channel,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for connection in self.active_connections[channel]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send to connection: {e}")
                dead_connections.add(connection)
                
        # Clean up dead connections
        for dead in dead_connections:
            self.active_connections[channel].remove(dead)

# Create connection manager instance
manager = ConnectionManager()

@router.websocket("/ping")
async def ping_endpoint(websocket: WebSocket):
    """Simple ping endpoint to test WebSocket connectivity."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass

@router.websocket("/listings")
async def listings_endpoint(websocket: WebSocket):
    """WebSocket endpoint for listings updates."""
    await handle_connection(websocket, "listings")

@router.websocket("/orders")
async def orders_endpoint(websocket: WebSocket):
    """WebSocket endpoint for orders updates."""
    await handle_connection(websocket, "orders")

@router.websocket("/market")
async def market_endpoint(websocket: WebSocket):
    """WebSocket endpoint for market data updates."""
    await handle_connection(websocket, "market")

async def handle_connection(websocket: WebSocket, channel: str):
    """Handle WebSocket connection for a specific channel."""
    try:
        await manager.connect(websocket, channel)
        heartbeat_task = asyncio.create_task(heartbeat(websocket))
        
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    if message.get("type") == "pong":
                        continue
                    # Handle other message types if needed
                except json.JSONDecodeError:
                    continue
                    
        except WebSocketDisconnect:
            pass
            
        finally:
            manager.disconnect(websocket, channel)
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            
    except Exception as e:
        logger.error(f"WebSocket error in {channel} channel: {e}")
        manager.disconnect(websocket, channel)

async def broadcast_update(channel: str, data: dict):
    """Broadcast an update to all clients subscribed to a channel."""
    await manager.broadcast(channel, data)

# Export the router and broadcast function
__all__ = ['router', 'broadcast_update', 'active_connections'] 