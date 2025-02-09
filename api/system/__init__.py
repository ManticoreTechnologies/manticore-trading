"""System health and rate limiting endpoints."""

from fastapi import APIRouter, HTTPException, status, Request
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import psutil
import os
from database import get_pool
from rpc import client as rpc_client
from decimal import Decimal

# Create router
router = APIRouter(
    prefix="/system",
    tags=["System"]
)

class SystemHealth(BaseModel):
    """Model for system health data."""
    status: str
    uptime: float
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_connections: int
    websocket_connections: int
    database_status: str
    blockchain_status: str
    last_block_time: Optional[datetime] = None

class RateLimits(BaseModel):
    """Model for rate limit data."""
    endpoint: str
    limit: int
    remaining: int
    reset_time: datetime
    current_usage: int

async def record_metric(metric_type: str, metric_name: str, metric_value: float):
    """Record a system metric in the database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            '''
            INSERT INTO system_metrics (
                metric_type,
                metric_name,
                metric_value
            ) VALUES ($1, $2, $3)
            ''',
            metric_type,
            metric_name,
            Decimal(str(metric_value))
        )

async def check_rate_limit(endpoint: str, client_id: str) -> bool:
    """Check if a request is within rate limits.
    
    Args:
        endpoint: The endpoint being accessed
        client_id: The client's identifier
        
    Returns:
        bool: True if request is allowed, False if rate limited
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Get existing rate limit entry
            rate_limit = await conn.fetchrow(
                '''
                SELECT 
                    request_count,
                    reset_time
                FROM rate_limits
                WHERE endpoint = $1 AND client_id = $2
                FOR UPDATE
                ''',
                endpoint,
                client_id
            )
            
            now = datetime.utcnow()
            
            if rate_limit:
                # Check if reset time has passed
                if rate_limit['reset_time'] < now:
                    # Reset counter
                    await conn.execute(
                        '''
                        UPDATE rate_limits
                        SET 
                            request_count = 1,
                            reset_time = $3,
                            updated_at = now()
                        WHERE endpoint = $1 AND client_id = $2
                        ''',
                        endpoint,
                        client_id,
                        now + timedelta(hours=1)
                    )
                    return True
                else:
                    # Increment counter
                    await conn.execute(
                        '''
                        UPDATE rate_limits
                        SET 
                            request_count = request_count + 1,
                            updated_at = now()
                        WHERE endpoint = $1 AND client_id = $2
                        ''',
                        endpoint,
                        client_id
                    )
                    
                    # Get endpoint limits
                    endpoint_limits = {
                        'listings': 1000,
                        'orders': 500,
                        'websocket': 100,
                        'default': 1000
                    }
                    
                    # Get limit for this endpoint
                    limit = endpoint_limits.get(
                        next((k for k in endpoint_limits if k in endpoint),
                        'default')
                    )
                    
                    return rate_limit['request_count'] < limit
            else:
                # Create new rate limit entry
                await conn.execute(
                    '''
                    INSERT INTO rate_limits (
                        endpoint,
                        client_id,
                        request_count,
                        reset_time
                    ) VALUES ($1, $2, 1, $3)
                    ''',
                    endpoint,
                    client_id,
                    now + timedelta(hours=1)
                )
                return True

@router.get("/health")
async def get_system_health() -> SystemHealth:
    """Get system health status.
    
    Returns:
        SystemHealth object containing system metrics
    """
    try:
        # Gather system metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get blockchain status
        try:
            blockchain_info = rpc_client.getblockchaininfo()
            blockchain_synced = blockchain_info['initialblockdownload'] == False
            
            # Get latest block time
            latest_block_hash = rpc_client.getbestblockhash()
            latest_block = rpc_client.getblock(latest_block_hash)
            last_block_time = datetime.fromtimestamp(latest_block['time'])
        except:
            blockchain_synced = False
            last_block_time = None
        
        # Get database status
        pool = await get_pool()
        async with pool.acquire() as conn:
            db_status = "connected"
            
            # Get connection counts
            active_connections = await conn.fetchval(
                '''
                SELECT COUNT(*)
                FROM pg_stat_activity
                WHERE state = 'active'
                '''
            )
            
            # Get WebSocket connections
            websocket_connections = await conn.fetchval(
                '''
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT client_id
                    FROM rate_limits
                    WHERE endpoint LIKE '%/ws/%'
                    AND reset_time > now()
                ) as active_ws
                '''
            )
        
        # Record metrics
        await record_metric('system', 'cpu_usage', cpu_percent)
        await record_metric('system', 'memory_usage', memory.percent)
        await record_metric('system', 'disk_usage', disk.percent)
        await record_metric('system', 'active_connections', active_connections)
        await record_metric('system', 'websocket_connections', websocket_connections)
        
        return SystemHealth(
            status="healthy" if cpu_percent < 80 else "degraded",
            uptime=psutil.boot_time(),
            cpu_usage=cpu_percent,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            active_connections=active_connections,
            websocket_connections=websocket_connections,
            database_status=db_status,
            blockchain_status="synced" if blockchain_synced else "syncing",
            last_block_time=last_block_time
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/limits")
async def get_rate_limits(request: Request) -> Dict[str, RateLimits]:
    """Get current rate limits and usage.
    
    Args:
        request: The FastAPI request object
        
    Returns:
        Dict mapping endpoints to their rate limits
    """
    try:
        pool = await get_pool()
        client_id = request.client.host
        
        async with pool.acquire() as conn:
            # Get rate limits for all endpoints
            rate_limits = await conn.fetch(
                '''
                SELECT 
                    endpoint,
                    request_count,
                    reset_time
                FROM rate_limits
                WHERE client_id = $1
                AND reset_time > now()
                ''',
                client_id
            )
            
            # Define endpoint limits
            endpoint_limits = {
                'listings': 1000,
                'orders': 500,
                'websocket': 100,
                'default': 1000
            }
            
            # Format results
            results = {}
            for rl in rate_limits:
                limit = endpoint_limits.get(
                    next((k for k in endpoint_limits if k in rl['endpoint']),
                    'default')
                )
                
                results[rl['endpoint']] = RateLimits(
                    endpoint=rl['endpoint'],
                    limit=limit,
                    remaining=max(0, limit - rl['request_count']),
                    reset_time=rl['reset_time'],
                    current_usage=rl['request_count']
                )
            
            return results
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Export the router and rate limit checker
__all__ = ['router', 'check_rate_limit'] 