"""Notifications API endpoints."""

from fastapi import APIRouter, HTTPException, WebSocket, status
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from database import get_pool

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)

class NotificationSettings(BaseModel):
    """Model for notification settings."""
    email_enabled: bool = False
    email_address: Optional[str] = None
    order_updates: bool = True
    listing_updates: bool = True
    price_alerts: bool = True

@router.post("/settings")
async def update_notification_settings(
    user_address: str,
    settings: NotificationSettings
):
    """Update notification settings for a user."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO notification_settings (
                    user_address,
                    email_enabled,
                    email_address,
                    order_updates,
                    listing_updates,
                    price_alerts
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_address) DO UPDATE
                SET
                    email_enabled = EXCLUDED.email_enabled,
                    email_address = EXCLUDED.email_address,
                    order_updates = EXCLUDED.order_updates,
                    listing_updates = EXCLUDED.listing_updates,
                    price_alerts = EXCLUDED.price_alerts,
                    updated_at = now()
                ''',
                user_address,
                settings.email_enabled,
                settings.email_address,
                settings.order_updates,
                settings.listing_updates,
                settings.price_alerts
            )
            
            return {
                "user_address": user_address,
                "settings": settings.dict(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/settings/{user_address}")
async def get_notification_settings(user_address: str):
    """Get notification settings for a user."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            settings = await conn.fetchrow(
                '''
                SELECT 
                    email_enabled,
                    email_address,
                    order_updates,
                    listing_updates,
                    price_alerts,
                    created_at,
                    updated_at
                FROM notification_settings
                WHERE user_address = $1
                ''',
                user_address
            )
            
            if not settings:
                # Return default settings
                return NotificationSettings().dict()
                
            return {
                "user_address": user_address,
                "settings": dict(settings),
                "created_at": settings['created_at'].isoformat(),
                "updated_at": settings['updated_at'].isoformat()
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/unread/{user_address}")
async def get_unread_notifications(
    user_address: str,
    limit: int = 50,
    offset: int = 0
):
    """Get unread notifications for a user."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            notifications = await conn.fetch(
                '''
                SELECT 
                    id,
                    type,
                    title,
                    message,
                    data,
                    created_at
                FROM notifications
                WHERE user_address = $1
                AND read = false
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                ''',
                user_address,
                limit,
                offset
            )
            
            total_count = await conn.fetchval(
                '''
                SELECT COUNT(*)
                FROM notifications
                WHERE user_address = $1
                AND read = false
                ''',
                user_address
            )
            
            return {
                "notifications": [dict(n) for n in notifications],
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/mark-read")
async def mark_notifications_read(
    user_address: str,
    notification_ids: List[UUID]
):
    """Mark notifications as read."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                '''
                UPDATE notifications
                SET read = true
                WHERE user_address = $1
                AND id = ANY($2)
                ''',
                user_address,
                notification_ids
            )
            
            return {
                "marked_read": len(notification_ids),
                "updated_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.websocket("/stream")
async def notification_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications."""
    await websocket.accept()
    
    try:
        # Get user address from query params
        user_address = websocket.query_params.get("user_address")
        if not user_address:
            await websocket.close(code=4000, reason="Missing user_address parameter")
            return
            
        # Add to active connections
        from api.websockets import active_connections
        active_connections['notifications'].add(websocket)
        
        try:
            while True:
                # Keep connection alive with ping/pong
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
                    
        except Exception:
            pass
            
        finally:
            active_connections['notifications'].remove(websocket)
            
    except Exception as e:
        logger.error(f"Notification stream error: {e}")
        await websocket.close(code=4000)

async def send_notification(
    user_address: str,
    type: str,
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None
):
    """Send a notification to a user.
    
    This is an internal function used by other modules to send notifications.
    It will:
    1. Save the notification to the database
    2. Send it via WebSocket if user is connected
    3. Send email if enabled in user's settings
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Check user's notification settings
            settings = await conn.fetchrow(
                '''
                SELECT 
                    email_enabled,
                    email_address,
                    order_updates,
                    listing_updates,
                    price_alerts
                FROM notification_settings
                WHERE user_address = $1
                ''',
                user_address
            )
            
            # Default to enabled if no settings
            should_notify = True
            if settings:
                if type.startswith('order') and not settings['order_updates']:
                    should_notify = False
                elif type.startswith('listing') and not settings['listing_updates']:
                    should_notify = False
                elif type.startswith('price') and not settings['price_alerts']:
                    should_notify = False
            
            if should_notify:
                # Save notification
                notification_id = await conn.fetchval(
                    '''
                    INSERT INTO notifications (
                        user_address,
                        type,
                        title,
                        message,
                        data
                    ) VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    ''',
                    user_address,
                    type,
                    title,
                    message,
                    data
                )
                
                # Send via WebSocket if connected
                notification = {
                    "id": str(notification_id),
                    "type": type,
                    "title": title,
                    "message": message,
                    "data": data,
                    "created_at": datetime.utcnow().isoformat()
                }
                
                from api.websockets import broadcast_update
                await broadcast_update('notifications', {
                    "user_address": user_address,
                    "notification": notification
                })
                
                # Send email if enabled
                if settings and settings['email_enabled'] and settings['email_address']:
                    # TODO: Implement email sending
                    pass
                    
    except Exception as e:
        logger.error(f"Error sending notification: {e}")

# Export the router and notification function
__all__ = ['router', 'send_notification'] 