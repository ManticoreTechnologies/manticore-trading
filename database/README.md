# Database Module

This module provides a robust database connection and management system specifically designed for CockroachDB cloud clusters. It handles connection pooling, schema management, and provides a clean interface for database operations.

## Important Note

**This module is specifically designed for CockroachDB cloud clusters and may not work with other database systems.**

## Features

- Automatic connection pooling management
- Schema version tracking and migrations
- Asynchronous database operations
- Connection retry and error handling
- Type-safe query interface

## Quick Setup

1. Ensure your `settings.conf` has the correct CockroachDB connection URL:
   ```ini
   [DEFAULT]
   db_url = postgresql://user:pass@your-cluster-host:26257/your_db?sslmode=verify-full
   ```

2. Create your schema definition in `database/schema/`:
   ```python
   # database/schema/v1.py
   schema = {
       'version': 1,
       'tables': [
           {
               'name': 'users',
               'columns': [
                   {'name': 'id', 'type': 'UUID', 'primary_key': True},
                   {'name': 'username', 'type': 'STRING', 'unique': True},
                   {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()'}
               ]
           }
       ]
   }
   ```

3. Initialize the database in your application:
   ```python
   from database import init_db, get_pool
   
   # Initialize database (call once at app startup)
   await init_db()
   
   # Get connection pool for queries
   pool = await get_pool()
   ```

## Schema Management

### Creating Schema Files

Schema files should be placed in the `database/schema/` directory and follow the version naming convention:
- `v1.py`
- `v2.py`
- etc.

Each schema file must define a `schema` dictionary with:
- `version`: Schema version number (integer)
- `tables`: List of table definitions
- `migrations`: (optional) SQL statements for migrating from previous version

Example schema file with migrations:
```python
# database/schema/v2.py
schema = {
    'version': 2,
    'tables': [
        {
            'name': 'users',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True},
                {'name': 'username', 'type': 'STRING', 'unique': True},
                {'name': 'email', 'type': 'STRING', 'unique': True},  # New column
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()'}
            ]
        }
    ],
    'migrations': [
        'ALTER TABLE users ADD COLUMN email STRING UNIQUE;'
    ]
}
```

## Connection Pool Management

The module automatically handles connection pooling with the following features:

- Dynamic pool sizing based on load
- Connection health checks
- Automatic reconnection
- Connection timeouts
- Statement timeout limits
- Retry policies for transient errors

## Usage Examples

### Basic Queries
```python
from database import get_pool

async def get_user(username: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchrow(
            'SELECT * FROM users WHERE username = $1',
            username
        )
        return result

async def create_user(username: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                'INSERT INTO users (id, username) VALUES (gen_random_uuid(), $1)',
                username
            )
```

### Using Transactions
```python
async def transfer_funds(from_id: str, to_id: str, amount: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # CockroachDB specific retry logic is handled automatically
            await conn.execute(
                'UPDATE accounts SET balance = balance - $1 WHERE id = $2',
                amount, from_id
            )
            await conn.execute(
                'UPDATE accounts SET balance = balance + $1 WHERE id = $2',
                amount, to_id
            )
```

## Error Handling

The module provides custom exception classes for different types of database errors:

- `DatabaseConnectionError`: Connection-related issues
- `DatabaseSchemaError`: Schema validation or migration issues
- `DatabaseQueryError`: Query execution errors
- `DatabasePoolError`: Connection pool issues

Example error handling:
```python
from database.exceptions import DatabaseQueryError

async def safe_query():
    try:
        result = await get_user('username')
        return result
    except DatabaseQueryError as e:
        logger.error(f"Query failed: {e}")
        raise
```

## Best Practices

1. Always use connection pooling (don't create individual connections)
2. Use transactions for multi-statement operations
3. Handle retryable errors using the built-in retry mechanism
4. Keep schema versions in sequential order
5. Document schema changes in migration files
6. Use parameterized queries to prevent SQL injection
7. Set appropriate timeouts for your queries

## Configuration Options

The module reads additional configuration from `settings.conf`:

```ini
[DEFAULT]
db_url = postgresql://user:pass@host:26257/db?sslmode=verify-full
db_min_connections = 5      # Minimum connections in pool
db_max_connections = 20     # Maximum connections in pool
db_connection_timeout = 10  # Connection timeout in seconds
db_statement_timeout = 30   # Statement timeout in seconds
```

## Development Guidelines

1. Always create new schema versions (don't modify existing ones)
2. Test migrations thoroughly before deployment
3. Use type hints in your database interaction code
4. Follow the provided examples for connection management
5. Document any custom SQL functions or indexes in schema files 