"""Database module tests."""
import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from asyncpg.pool import Pool
from asyncpg.exceptions import UniqueViolationError

from database import init_db, get_pool, close
from database.exceptions import DatabaseError

pytestmark = pytest.mark.asyncio  # Mark all tests as async

@pytest_asyncio.fixture
async def db_pool() -> Pool:
    """Fixture that provides a database connection pool."""
    await init_db()
    pool = await get_pool()
    yield pool
    await close()

async def test_connection(db_pool: Pool) -> None:
    """Test basic database connectivity."""
    async with db_pool.acquire() as conn:
        # Simple query to verify connection
        result = await conn.fetchval('SELECT 1')
        assert result == 1

async def test_schema_version(db_pool: Pool) -> None:
    """Test that schema version table exists and has a version."""
    async with db_pool.acquire() as conn:
        version = await conn.fetchval(
            'SELECT version FROM schema_version ORDER BY version DESC LIMIT 1'
        )
        assert version is not None
        assert version > 0

async def test_create_user(db_pool: Pool) -> None:
    """Test user creation and retrieval."""
    test_username = f"test_user_{uuid.uuid4()}"
    
    async with db_pool.acquire() as conn:
        # Create user
        user_id = await conn.fetchval(
            '''
            INSERT INTO users (id, username)
            VALUES (gen_random_uuid(), $1)
            RETURNING id
            ''',
            test_username
        )
        
        # Verify user exists
        row = await conn.fetchrow(
            'SELECT * FROM users WHERE id = $1',
            user_id
        )
        
        assert row is not None
        assert row['username'] == test_username
        assert row['created_at'] is not None

async def test_create_asset(db_pool: Pool) -> None:
    """Test asset creation and retrieval."""
    test_asset = {
        'name': f"Test Asset {uuid.uuid4()}",
        'symbol': f"TEST_{uuid.uuid4().hex[:6]}"
    }
    
    async with db_pool.acquire() as conn:
        # Create asset
        asset_id = await conn.fetchval(
            '''
            INSERT INTO assets (id, name, symbol)
            VALUES (gen_random_uuid(), $1, $2)
            RETURNING id
            ''',
            test_asset['name'],
            test_asset['symbol']
        )
        
        # Verify asset exists
        row = await conn.fetchrow(
            'SELECT * FROM assets WHERE id = $1',
            asset_id
        )
        
        assert row is not None
        assert row['name'] == test_asset['name']
        assert row['symbol'] == test_asset['symbol']
        assert row['created_at'] is not None

async def test_unique_constraints(db_pool: Pool) -> None:
    """Test that unique constraints are enforced."""
    test_username = f"test_user_{uuid.uuid4()}"
    
    async with db_pool.acquire() as conn:
        # Create first user
        await conn.execute(
            '''
            INSERT INTO users (id, username)
            VALUES (gen_random_uuid(), $1)
            ''',
            test_username
        )
        
        # Attempt to create second user with same username
        with pytest.raises(UniqueViolationError):
            await conn.execute(
                '''
                INSERT INTO users (id, username)
                VALUES (gen_random_uuid(), $1)
                ''',
                test_username
            ) 