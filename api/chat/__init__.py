"""
Chat module for Manticore Trading API.
Provides real-time chat functionality with WebSocket support.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import json

from auth import get_current_user, manager as auth_manager
from database import get_pool
from . import db
from .manager import manager
from .models import (
    ChatMessage, ChatMessageType, ChatMessageCreate, ChatMessageEdit,
    ChatChannelInfo, ChatChannelSubscription, ChatAttachment,
    ChatReport, ChatPresenceUpdate, WebSocketMessage
)

# Create router
router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    # Accept the connection first
    await websocket.accept()
    
    user_address = None
    try:
        # Wait for authentication message
        auth_message = await websocket.receive_json()
        if not isinstance(auth_message, dict) or "token" not in auth_message:
            await websocket.close(code=4001, reason="Authentication required")
            return
            
        # Verify the token
        token = auth_message["token"]
        try:
            user_address = await auth_manager.verify_session(token)
            if not user_address:
                await websocket.close(code=4001, reason="Invalid token")
                return
        except Exception as e:
            await websocket.close(code=4001, reason="Invalid token")
            return
            
        # Connect to manager
        await manager.connect(websocket, user_address)
        
        try:
            while True:
                # Receive and validate message
                data = await websocket.receive_json()
                try:
                    message = WebSocketMessage(**data)
                    await manager.handle_message(user_address, message)
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "data": {
                            "message": f"Invalid message format: {str(e)}"
                        }
                    })
        except WebSocketDisconnect:
            if user_address:
                manager.disconnect(user_address)
    except Exception as e:
        if user_address:
            manager.disconnect(user_address)
        if not websocket.client_state.DISCONNECTED:
            await websocket.close(code=1011, reason=f"Internal error: {str(e)}")

@router.get("/global", response_model=List[ChatMessage])
async def get_global_messages(
    pool = Depends(get_pool),
    current_user: str = Depends(get_current_user),
    limit: int = 50,
    before: Optional[datetime] = None
):
    """Get global chat messages."""
    async with pool.acquire() as conn:
        messages = await db.get_messages(
            conn,
            msg_type=ChatMessageType.GLOBAL,
            limit=limit,
            before=before
        )
        return messages

@router.post("/global", response_model=ChatMessage)
async def send_global_message(
    message: ChatMessageCreate,
    pool = Depends(get_pool),
    current_user: str = Depends(get_current_user)
):
    """Send a message to global chat."""
    async with pool.acquire() as conn:
        chat_msg = await db.create_message(
            conn,
            text=message.text,
            sender=current_user,
            msg_type=ChatMessageType.GLOBAL,
            ipfs_hash=message.ipfs_hash
        )
        
        # Broadcast to WebSocket clients
        await manager.broadcast_to_channel("global", {
            "type": "chat_message",
            "data": chat_msg.dict()
        })
        
        return chat_msg

@router.get("/assets/channels")
async def get_asset_channels(
    pool = Depends(get_pool),
    current_user: str = Depends(get_current_user)
):
    """Get all available asset channels."""
    async with pool.acquire() as conn:
        # Get all distinct asset channels and their info
        channels = await conn.fetch(
            """
            SELECT DISTINCT 
                channel,
                'asset' as type,
                COUNT(DISTINCT sender) as participants,
                (
                    SELECT text 
                    FROM chat_messages m2 
                    WHERE m2.channel = m1.channel 
                    AND m2.type = 'asset'
                    ORDER BY created_at DESC 
                    LIMIT 1
                ) as last_message
            FROM chat_messages m1
            WHERE type = 'asset'
            AND channel IS NOT NULL
            GROUP BY channel
            ORDER BY channel
            """
        )
        
        return {
            "channels": [
                {
                    "name": row['channel'],
                    "type": "asset",
                    "participants": row['participants'],
                    "lastMessage": row['last_message']
                }
                for row in channels
            ]
        }

# Export the router
__all__ = ['router'] 