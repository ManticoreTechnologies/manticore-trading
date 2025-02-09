"""Order management endpoints for cancellation, history, and disputes."""

from fastapi import APIRouter, HTTPException, status
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from database import get_pool
from orders import OrderManager, OrderError

router = APIRouter()

class OrderHistoryEntry(BaseModel):
    """Model for order history entries."""
    timestamp: datetime
    status: str
    description: str
    details: Optional[Dict[str, Any]] = None

class DisputeRequest(BaseModel):
    """Model for opening a dispute."""
    reason: str
    description: str
    evidence: Optional[List[str]] = None  # List of evidence URLs/hashes

@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str):
    """Cancel an unfulfilled order.
    
    Args:
        order_id: The order's UUID
        
    Returns:
        Dict containing updated order status
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify order exists and can be cancelled
            order = await conn.fetchrow(
                '''
                SELECT id, status
                FROM orders
                WHERE id = $1 AND status IN ('pending', 'partially_paid')
                ''',
                order_id
            )
            
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found or cannot be cancelled"
                )
            
            # Update order status
            await conn.execute(
                '''
                UPDATE orders
                SET status = 'cancelled',
                    updated_at = now()
                WHERE id = $1
                ''',
                order_id
            )
            
            # Record in history
            await conn.execute(
                '''
                INSERT INTO order_history (
                    order_id,
                    status,
                    description,
                    details
                ) VALUES ($1, $2, $3, $4)
                ''',
                order_id,
                'cancelled',
                'Order cancelled by user',
                {'cancelled_at': datetime.utcnow().isoformat()}
            )
            
            return {
                "order_id": order_id,
                "status": "cancelled",
                "cancelled_at": datetime.utcnow().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/orders/{order_id}/history")
async def get_order_history(order_id: str) -> List[OrderHistoryEntry]:
    """Get detailed order history including status changes.
    
    Args:
        order_id: The order's UUID
        
    Returns:
        List of order history entries
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify order exists
            exists = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM orders WHERE id = $1)',
                order_id
            )
            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found"
                )
            
            # Get history entries
            entries = await conn.fetch(
                '''
                SELECT 
                    created_at as timestamp,
                    status,
                    description,
                    details
                FROM order_history
                WHERE order_id = $1
                ORDER BY created_at DESC
                ''',
                order_id
            )
            
            return [
                OrderHistoryEntry(
                    timestamp=entry['timestamp'],
                    status=entry['status'],
                    description=entry['description'],
                    details=entry['details']
                )
                for entry in entries
            ]
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/orders/{order_id}/dispute")
async def open_dispute(order_id: str, dispute: DisputeRequest):
    """Open a dispute for an order.
    
    Args:
        order_id: The order's UUID
        dispute: The dispute details
        
    Returns:
        Dict containing dispute details
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify order exists and can be disputed
            order = await conn.fetchrow(
                '''
                SELECT id, status
                FROM orders
                WHERE id = $1 AND status NOT IN ('pending', 'cancelled')
                ''',
                order_id
            )
            
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found or cannot be disputed"
                )
            
            # Check if dispute already exists
            existing_dispute = await conn.fetchval(
                '''
                SELECT id
                FROM order_disputes
                WHERE order_id = $1 AND status != 'closed'
                ''',
                order_id
            )
            
            if existing_dispute:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Active dispute already exists for order {order_id}"
                )
            
            # Create dispute
            dispute_id = await conn.fetchval(
                '''
                INSERT INTO order_disputes (
                    order_id,
                    reason,
                    description,
                    evidence,
                    status
                ) VALUES ($1, $2, $3, $4, 'opened')
                RETURNING id
                ''',
                order_id,
                dispute.reason,
                dispute.description,
                dispute.evidence
            )
            
            # Record in order history
            await conn.execute(
                '''
                INSERT INTO order_history (
                    order_id,
                    status,
                    description,
                    details
                ) VALUES ($1, $2, $3, $4)
                ''',
                order_id,
                'disputed',
                'Dispute opened by user',
                {
                    'dispute_id': str(dispute_id),
                    'reason': dispute.reason
                }
            )
            
            return {
                "dispute_id": str(dispute_id),
                "order_id": order_id,
                "status": "opened",
                "created_at": datetime.utcnow().isoformat(),
                "reason": dispute.reason,
                "description": dispute.description,
                "evidence": dispute.evidence
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Export the router
__all__ = ['router'] 