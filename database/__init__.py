"""Database module for managing connections to CockroachDB.

This module handles:
- Database connection pool initialization
- Schema management
- Connection lifecycle
"""

import asyncio
import logging
import ssl
from typing import Optional, Dict, Any
import backoff
import asyncpg
from urllib.parse import urlparse, parse_qs

from .lib.schema_manager import SchemaManager

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_schema_manager: Optional[SchemaManager] = None

def _get_ssl_context() -> ssl.SSLContext:
    """Create SSL context for CockroachDB Cloud connections."""
    ssl_context = ssl.create_default_context()
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True
    return ssl_context

def _get_connection_kwargs(db_url: str) -> Dict[str, Any]:
    """Get connection kwargs from database URL.
    
    Args:
        db_url: Database connection URL
        
    Returns:
        Dict of connection parameters
    """
    parsed = urlparse(db_url)
    params = parse_qs(parsed.query)
    
    # Start with base SSL-enabled kwargs
    kwargs = {
        'ssl': _get_ssl_context(),
        'server_settings': {
            'multiple_active_portals_enabled': 'true',
            'statement_timeout': '300000',  # 5 minutes
        }
    }
    
    # Add any additional params from URL
    for key, values in params.items():
        if key not in ('sslmode', 'ssl'):  # Skip SSL params as we handle those above
            kwargs[key] = values[0]
            
    return kwargs

@backoff.on_exception(
    backoff.expo,
    (asyncpg.exceptions.PostgresConnectionError, asyncpg.exceptions.CannotConnectNowError),
    max_tries=5
)
async def create_database_if_not_exists(db_url: str) -> None:
    """Create the database if it doesn't exist.
    
    Args:
        db_url: Database connection URL
        
    Raises:
        Exception: If database creation fails after retries
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
        
        conn_kwargs = _get_connection_kwargs(base_url)
        conn = await asyncpg.connect(base_url, **conn_kwargs)
        
        try:
            # Check if database exists
            exists = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM [SHOW DATABASES] WHERE database_name = $1)',
                db_name
            )
            
            if not exists:
                # Create database
                await conn.execute(f'CREATE DATABASE IF NOT EXISTS "{db_name}"')
                logger.info(f"Created database {db_name}")
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise

@backoff.on_exception(
    backoff.expo,
    (asyncpg.exceptions.PostgresConnectionError, asyncpg.exceptions.CannotConnectNowError),
    max_tries=5
)
async def init_db(db_url: Optional[str] = None, force_recreate: bool = False) -> None:
    """Initialize the database connection pool and schema.
    
    Args:
        db_url: Optional database URL. If not provided, will use settings.
        force_recreate: If True, drop and recreate all tables
        
    Raises:
        ValueError: If database URL is not provided
        Exception: If initialization fails after retries
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
        
        # Get connection kwargs
        conn_kwargs = _get_connection_kwargs(url)
        
        # Create connection pool with optimized settings for CockroachDB
        _pool = await asyncpg.create_pool(
            url,
            min_size=2,          # Minimum idle connections
            max_size=20,         # Maximum connections
            max_queries=10000,   # Reset connection after this many queries
            max_inactive_connection_lifetime=300.0,  # 5 minutes
            command_timeout=60.0,  # 1 minute command timeout
            init=lambda conn: conn.execute(
                'SET multiple_active_portals_enabled = true'
            ),
            **conn_kwargs
        )
        
        # Initialize schema manager
        _schema_manager = SchemaManager(_pool)
        
        # Check if schema exists
        async with _pool.acquire() as conn:
            schema_exists = await conn.fetchval(
                '''
                SELECT EXISTS (
                    SELECT 1 
                    FROM pg_tables 
                    WHERE schemaname = 'public' 
                    AND tablename = 'schema_version'
                )
                '''
            )
            
            if not schema_exists or force_recreate:
                logger.info("Schema not found or force recreate requested. Creating schema...")
                # Create schema_version table if it doesn't exist
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INT NOT NULL DEFAULT 0,
                        updated_at TIMESTAMP NOT NULL DEFAULT now()
                    )
                ''')
                
                # Get list of tables to drop
                tables = await conn.fetch(
                    '''
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE schemaname = 'public' 
                    AND tablename != 'schema_version'
                    '''
                )
                
                # Drop each table individually
                for table in tables:
                    await conn.execute(
                        f'DROP TABLE IF EXISTS "{table["tablename"]}" CASCADE'
                    )
                
                # Reset schema version
                await conn.execute('DELETE FROM schema_version')
                await conn.execute('INSERT INTO schema_version (version) VALUES (0)')
                
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
    if not _pool:
        raise RuntimeError("Failed to initialize database pool")
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