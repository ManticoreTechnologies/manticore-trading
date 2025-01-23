"""Database module for CockroachDB connection management.

This module provides a connection pool and database management interface
specifically designed for CockroachDB cloud clusters.
"""
import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse, parse_qs

import asyncpg
from asyncpg.pool import Pool

from config import settings_conf
from .lib.schema_manager import SchemaManager
from .exceptions import DatabaseConnectionError, DatabasePoolError

logger = logging.getLogger(__name__)

# Global connection pool
_pool: Optional[Pool] = None
_schema_manager: Optional[SchemaManager] = None

async def create_database_if_not_exists(db_url: str) -> None:
    """Create the database if it doesn't exist.
    
    Args:
        db_url: Database connection URL
    """
    try:
        # Parse the URL to get database name and create a URL without the database
        url = urlparse(db_url)
        
        # Handle CockroachDB cloud URLs which have the database in query params
        params = parse_qs(url.query)
        database = params.get('database', ['demo_db'])[0]
            
        # Create base URL with defaultdb
        base_url = f"{url.scheme}://{url.netloc}/defaultdb"
        if url.query:
            # Remove database from query params if present
            params = parse_qs(url.query)
            params.pop('database', None)
            if params:
                query_string = '&'.join(f"{k}={v[0]}" for k, v in params.items())
                base_url = f"{base_url}?{query_string}"
        
        logger.info(f"Connecting to defaultdb to create {database} if needed")
        # Connect to defaultdb to create our database
        conn = await asyncpg.connect(base_url)
        try:
            # Check if database exists
            exists = await conn.fetchval(
                "SELECT 1 FROM [SHOW DATABASES] WHERE database_name = $1",
                database
            )
            
            if not exists:
                logger.info(f"Creating database {database}")
                # Escape database name for SQL
                escaped_db = database.replace('"', '""')
                await conn.execute(f'CREATE DATABASE "{escaped_db}"')
                logger.info(f"Created database {database}")
                
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Failed to create database: {e}")
        raise DatabaseConnectionError(f"Database creation failed: {e}")

async def init_db() -> None:
    """Initialize the database connection pool and schema.
    
    This should be called once at application startup.
    """
    global _pool, _schema_manager
    
    if _pool is not None:
        logger.warning("Database already initialized")
        return
        
    try:
        # Create database if it doesn't exist
        db_url = settings_conf['db_url']
        await create_database_if_not_exists(db_url)
        
        # Create the connection pool
        _pool = await asyncpg.create_pool(
            db_url,
            min_size=int(settings_conf.get('db_min_connections', 5)),
            max_size=int(settings_conf.get('db_max_connections', 20)),
            command_timeout=int(settings_conf.get('db_statement_timeout', 30)),
            timeout=int(settings_conf.get('db_connection_timeout', 10))
        )
        
        # Initialize schema manager
        _schema_manager = SchemaManager(_pool)
        await _schema_manager.initialize()
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        if _pool:
            await _pool.close()
            _pool = None
        raise DatabaseConnectionError(f"Database initialization failed: {e}")

async def get_pool() -> Pool:
    """Get the database connection pool.
    
    Returns:
        asyncpg.Pool: The connection pool
        
    Raises:
        DatabasePoolError: If the pool hasn't been initialized
    """
    if _pool is None:
        raise DatabasePoolError("Database not initialized. Call init_db() first")
    return _pool

async def close() -> None:
    """Close the database connection pool.
    
    This should be called when shutting down the application.
    """
    global _pool
    if _pool:
        await _pool.close()
        _pool = None 