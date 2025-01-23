"""Database module for managing connections to CockroachDB.

This module handles:
- Database connection pool initialization
- Schema management
- Connection lifecycle
"""

import asyncio
import logging
from typing import Optional

import asyncpg
from urllib.parse import urlparse, parse_qs

from .lib.schema_manager import SchemaManager

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_schema_manager: Optional[SchemaManager] = None

async def create_database_if_not_exists(db_url: str) -> None:
    """Create the database if it doesn't exist.
    
    Args:
        db_url: Database connection URL
    """
    try:
        # Parse the URL
        parsed = urlparse(db_url)
        
        # Get database name from path or query params
        db_name = parsed.path.strip('/')
        if not db_name:
            params = parse_qs(parsed.query)
            db_name = params.get('database', ['defaultdb'])[0]
        
        # Connect to default database
        base_url = db_url.replace(db_name, 'defaultdb')
        logger.info(f"Connecting to defaultdb to create {db_name} if needed")
        
        conn = await asyncpg.connect(base_url)
        try:
            # Check if database exists
            exists = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM [SHOW DATABASES] WHERE database_name = $1)',
                db_name
            )
            
            if not exists:
                # Create database
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                logger.info(f"Created database {db_name}")
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise

async def init_db(db_url: Optional[str] = None) -> None:
    """Initialize the database connection pool and schema.
    
    Args:
        db_url: Optional database URL. If not provided, will use settings.
    """
    global _pool, _schema_manager
    
    try:
        # Import here to avoid circular imports
        from config import settings_conf
        
        # Use provided URL or get from settings
        url = db_url or settings_conf.get('db_url')
        if not url:
            raise ValueError("Database URL not provided")
        
        # Create database if needed
        await create_database_if_not_exists(url)
        
        # Create connection pool with more conservative settings
        _pool = await asyncpg.create_pool(
            url,
            min_size=2,
            max_size=10,
            max_queries=50000,
            max_inactive_connection_lifetime=300.0,  # 5 minutes
            init=lambda conn: conn.execute(
                'SET multiple_active_portals_enabled = true'
            )
        )
        
        # Initialize schema manager
        _schema_manager = SchemaManager(_pool)
        await _schema_manager.initialize()
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def get_pool() -> asyncpg.Pool:
    """Get the database connection pool.
    
    Returns:
        The connection pool
        
    Raises:
        RuntimeError: If pool hasn't been initialized
    """
    if not _pool:
        await init_db()
    return _pool

async def close() -> None:
    """Close the database connection pool."""
    global _pool, _schema_manager
    
    if _pool:
        await _pool.close()
        _pool = None
        _schema_manager = None

# Export public interface
__all__ = ['init_db', 'get_pool', 'close'] 