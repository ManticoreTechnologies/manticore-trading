from datetime import datetime
import json
from typing import Dict, List, Optional, Set
from uuid import UUID
from fastapi import WebSocket
from .models import ChatMessage, ChatMessageType, WebSocketMessage


class ConnectionManager:
    def __init__(self):
        # Map of user_address -> WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}
        # Map of channel -> set of user addresses
        self.channel_subscribers: Dict[str, Set[str]] = {
            "global": set()
        }
        # Map of user_address -> set of subscribed channels
        self.user_subscriptions: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, user_address: str):
        """Connect a new WebSocket client."""
        # Store the connection
        self.active_connections[user_address] = websocket
        
        # Subscribe to global channel by default
        if user_address not in self.user_subscriptions:
            self.user_subscriptions[user_address] = set()
        self.user_subscriptions[user_address].add("global")
        
        if "global" not in self.channel_subscribers:
            self.channel_subscribers["global"] = set()
        self.channel_subscribers["global"].add(user_address)
        
        # Send connection confirmation
        try:
            await websocket.send_json({
                "type": "connection_status",
                "data": {
                    "status": "connected",
                    "address": user_address
                }
            })
        except:
            self.disconnect(user_address)

    def disconnect(self, user_address: str):
        """Disconnect a WebSocket client."""
        if user_address in self.active_connections:
            del self.active_connections[user_address]
        
        # Remove from all channel subscriptions
        if user_address in self.user_subscriptions:
            channels = self.user_subscriptions[user_address]
            for channel in channels:
                if channel in self.channel_subscribers:
                    self.channel_subscribers[channel].discard(user_address)
            del self.user_subscriptions[user_address]

    async def broadcast_to_channel(self, channel: str, message: dict):
        """Broadcast a message to all subscribers of a channel."""
        if channel not in self.channel_subscribers:
            return
        
        disconnected = set()
        for user_address in self.channel_subscribers[channel]:
            if user_address in self.active_connections:
                try:
                    await self.active_connections[user_address].send_json(message)
                except:
                    disconnected.add(user_address)
        
        # Clean up disconnected users
        for user_address in disconnected:
            self.disconnect(user_address)

    async def broadcast_to_user(self, user_address: str, message: dict):
        """Send a message to a specific user."""
        if user_address in self.active_connections:
            try:
                await self.active_connections[user_address].send_json(message)
            except:
                self.disconnect(user_address)

    async def subscribe_to_channel(self, user_address: str, channel: str):
        """Subscribe a user to a channel."""
        if channel not in self.channel_subscribers:
            self.channel_subscribers[channel] = set()
        
        self.channel_subscribers[channel].add(user_address)
        if user_address not in self.user_subscriptions:
            self.user_subscriptions[user_address] = set()
        self.user_subscriptions[user_address].add(channel)
        
        # Notify user of successful subscription
        await self.broadcast_to_user(
            user_address,
            {
                "type": "channel_subscription",
                "data": {
                    "channel": channel,
                    "status": "subscribed"
                }
            }
        )

    async def unsubscribe_from_channel(self, user_address: str, channel: str):
        """Unsubscribe a user from a channel."""
        if channel in self.channel_subscribers:
            self.channel_subscribers[channel].discard(user_address)
        if user_address in self.user_subscriptions:
            self.user_subscriptions[user_address].discard(channel)
        
        # Notify user of successful unsubscription
        await self.broadcast_to_user(
            user_address,
            {
                "type": "channel_subscription",
                "data": {
                    "channel": channel,
                    "status": "unsubscribed"
                }
            }
        )

    def get_channel_subscribers(self, channel: str) -> Set[str]:
        """Get all subscribers of a channel."""
        return self.channel_subscribers.get(channel, set())

    def get_user_subscriptions(self, user_address: str) -> Set[str]:
        """Get all channels a user is subscribed to."""
        return self.user_subscriptions.get(user_address, set())

    async def handle_message(self, user_address: str, message: WebSocketMessage):
        """Handle an incoming WebSocket message."""
        try:
            if message.type == "subscribe":
                await self.subscribe_to_channel(user_address, message.data["channel"])
            elif message.type == "unsubscribe":
                await self.unsubscribe_from_channel(user_address, message.data["channel"])
            elif message.type == "presence":
                # Handle presence updates
                await self.broadcast_to_channel(
                    "global",
                    {
                        "type": "presence_update",
                        "data": {
                            "user_address": user_address,
                            "status": message.data["status"]
                        }
                    }
                )
            elif message.type == "chat_message":
                # Handle chat message
                await self.broadcast_to_channel(
                    message.data.get("channel", "global"),
                    {
                        "type": "chat_message",
                        "data": {
                            "text": message.data["text"],
                            "sender": user_address,
                            "type": message.data["type"],
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )
                # Send confirmation to sender
                await self.broadcast_to_user(
                    user_address,
                    {
                        "type": "message_confirmation",
                        "data": {
                            "status": "delivered",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )
        except Exception as e:
            # Send error message to user
            await self.broadcast_to_user(
                user_address,
                {
                    "type": "error",
                    "data": {
                        "message": str(e)
                    }
                }
            )


# Global instance
manager = ConnectionManager() 