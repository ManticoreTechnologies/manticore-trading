"""WebSocket endpoints for real-time updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from typing import Dict, Set, Optional, List
from datetime import datetime, timedelta
import logging
import json
import asyncio
from asyncio import Task, Queue
from statistics import mean

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

# Heartbeat settings
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 10   # seconds
LATENCY_WINDOW = 10      # number of samples to keep for latency calculation
SIGNAL_UPDATE_INTERVAL = 5  # seconds between signal strength updates

class ConnectionQuality:
    """Track connection quality metrics."""
    def __init__(self):
        self.latencies: List[float] = []  # in milliseconds
        self.missed_pongs = 0
        self.total_pongs = 0
        self.last_signal_update = datetime.utcnow()

    def add_latency(self, latency_ms: float):
        """Add a latency measurement."""
        self.latencies.append(latency_ms)
        if len(self.latencies) > LATENCY_WINDOW:
            self.latencies.pop(0)
        self.total_pongs += 1

    def get_signal_strength(self) -> dict:
        """Calculate signal strength metrics."""
        if not self.latencies:
            return {
                "strength": 0,
                "latency": None,
                "reliability": 100 if self.total_pongs > 0 else 0
            }

        avg_latency = mean(self.latencies)
        reliability = (self.total_pongs - self.missed_pongs) / max(self.total_pongs, 1) * 100

        # Calculate strength (0-4) based on latency and reliability
        if avg_latency < 100:  # < 100ms
            strength = 4
        elif avg_latency < 300:  # < 300ms
            strength = 3
        elif avg_latency < 1000:  # < 1s
            strength = 2
        elif avg_latency < 3000:  # < 3s
            strength = 1
        else:
            strength = 0

        # Reduce strength if reliability is poor
        if reliability < 50:
            strength = max(0, strength - 2)
        elif reliability < 80:
            strength = max(0, strength - 1)

        return {
            "strength": strength,  # 0-4 (like signal bars)
            "latency": round(avg_latency, 2),  # in ms
            "reliability": round(reliability, 2)  # percentage
        }

class ConnectionManager:
    def __init__(self):
        self.active_connections = active_connections
        self.heartbeat_tasks: Dict[WebSocket, Task] = {}
        self.last_pong: Dict[WebSocket, datetime] = {}
        self.message_queues: Dict[WebSocket, Queue] = {}
        self.connection_quality: Dict[WebSocket, ConnectionQuality] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        """Accept connection and add to active connections."""
        await websocket.accept()
        self.active_connections[channel].add(websocket)
        self.last_pong[websocket] = datetime.utcnow()
        self.message_queues[websocket] = Queue()
        self.connection_quality[websocket] = ConnectionQuality()
        
        # Start heartbeat for this connection
        self.heartbeat_tasks[websocket] = asyncio.create_task(
            self.heartbeat_loop(websocket, channel)
        )
        logger.info(f"New connection established for channel: {channel}")

    def disconnect(self, websocket: WebSocket, channel: str):
        """Remove connection from active connections."""
        try:
            self.active_connections[channel].remove(websocket)
            # Clean up heartbeat task
            if websocket in self.heartbeat_tasks:
                self.heartbeat_tasks[websocket].cancel()
                del self.heartbeat_tasks[websocket]
            if websocket in self.last_pong:
                del self.last_pong[websocket]
            if websocket in self.message_queues:
                del self.message_queues[websocket]
            if websocket in self.connection_quality:
                del self.connection_quality[websocket]
            logger.info(f"Connection closed for channel: {channel}")
        except KeyError:
            pass

    async def heartbeat_loop(self, websocket: WebSocket, channel: str):
        """Maintain heartbeat for a connection."""
        try:
            while True:
                try:
                    # Send ping with timestamp
                    ping_time = datetime.utcnow()
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": ping_time.isoformat()
                    })
                    
                    # Wait for pong with timeout
                    try:
                        # Wait for message to be put in queue
                        message = await asyncio.wait_for(
                            self.message_queues[websocket].get(),
                            timeout=HEARTBEAT_TIMEOUT
                        )
                        
                        if message.get("type") == "pong":
                            pong_time = datetime.utcnow()
                            latency = (pong_time - ping_time).total_seconds() * 1000  # convert to ms
                            self.connection_quality[websocket].add_latency(latency)
                            self.last_pong[websocket] = pong_time

                            # Send signal strength update if needed
                            if (pong_time - self.connection_quality[websocket].last_signal_update).total_seconds() >= SIGNAL_UPDATE_INTERVAL:
                                await self.send_signal_strength(websocket)
                                self.connection_quality[websocket].last_signal_update = pong_time
                        else:
                            # Put non-pong messages back in queue
                            await self.message_queues[websocket].put(message)
                        
                    except asyncio.TimeoutError:
                        # No pong received in time
                        if websocket in self.connection_quality:
                            self.connection_quality[websocket].missed_pongs += 1
                        logger.warning(f"Heartbeat timeout in channel {channel}")
                        await self.handle_timeout(websocket, channel)
                        return
                        
                    # Wait for next heartbeat interval
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
                    
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected during heartbeat in channel {channel}")
                    break
                    
        except asyncio.CancelledError:
            # Heartbeat task was cancelled
            pass
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")
        finally:
            await self.handle_timeout(websocket, channel)

    async def send_signal_strength(self, websocket: WebSocket):
        """Send signal strength update to client."""
        try:
            if websocket in self.connection_quality:
                signal_data = self.connection_quality[websocket].get_signal_strength()
                await websocket.send_json({
                    "type": "signal",
                    "data": signal_data,
                    "timestamp": datetime.utcnow().isoformat()
                })
        except Exception as e:
            logger.error(f"Error sending signal strength: {e}")

    async def handle_timeout(self, websocket: WebSocket, channel: str):
        """Handle heartbeat timeout or connection error."""
        self.disconnect(websocket, channel)
        try:
            await websocket.close(code=1001, reason="Heartbeat timeout")
        except:
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
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to connection: {e}")
                dead_connections.add(connection)
                
        # Clean up dead connections
        for dead in dead_connections:
            self.disconnect(dead, channel)

# Create connection manager instance
manager = ConnectionManager()

@router.websocket("/ping")
async def ping_endpoint(websocket: WebSocket):
    """Simple ping endpoint to test WebSocket connectivity."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
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
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                message = json.loads(data) if isinstance(data, str) else data
                
                # Put message in queue for processing
                await manager.message_queues[websocket].put(message)
                
                # If it's not a pong message, process it here
                if message.get("type") != "pong":
                    # Handle other message types if needed
                    pass
                    
        except WebSocketDisconnect:
            pass
            
        finally:
            manager.disconnect(websocket, channel)
            
    except Exception as e:
        logger.error(f"WebSocket error in {channel} channel: {e}")
        manager.disconnect(websocket, channel)

async def broadcast_update(channel: str, data: dict):
    """Broadcast an update to all clients subscribed to a channel."""
    await manager.broadcast(channel, data)

# Export the router and broadcast function
__all__ = ['router', 'broadcast_update', 'active_connections'] 