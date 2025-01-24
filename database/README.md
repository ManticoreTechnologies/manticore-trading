# Database Module

This module manages connections to CockroachDB and handles database initialization and connection lifecycle.

## Features

- Asynchronous connection pooling with asyncpg
- Automatic database creation if not exists
- Schema management through versioning system
- Conservative connection pool settings
- Graceful connection handling

## Usage

```python
from database import init_db, get_pool, close

# Initialize database with URL
await init_db("postgresql://user:pass@host:26257/dbname")

# Or initialize using settings from config
await init_db()  # Uses settings_conf.get('db_url')

# Get connection pool
pool = await get_pool()

# Use pool for queries
async with pool.acquire() as conn:
    result = await conn.fetch('SELECT * FROM my_table')

# Close pool when done
await close()
```

## Connection Pool Configuration

The module uses conservative pool settings for CockroachDB:

```python
pool = await asyncpg.create_pool(
    url,
    min_size=2,          # Minimum connections
    max_size=10,         # Maximum connections
    max_queries=50000,   # Max queries per connection
    max_inactive_connection_lifetime=300.0,  # 5 minutes
)
```

## API Reference

### init_db(db_url: Optional[str] = None)
Initialize the database connection pool and schema.

```python
# With explicit URL
await init_db("postgresql://user:pass@host:26257/dbname")

# Using config settings
await init_db()
```

### get_pool() -> asyncpg.Pool
Get the database connection pool. Initializes the pool if not already done.

```python
pool = await get_pool()
```

### close()
Close the database connection pool gracefully.

```python
await close()
```

## Database Creation

The module automatically creates the database if it doesn't exist:

1. Parses the database URL
2. Connects to 'defaultdb'
3. Checks if target database exists
4. Creates database if needed

```python
await create_database_if_not_exists(db_url)
```

## Schema Management

Schema management is handled through the SchemaManager class:

```python
schema_manager = SchemaManager(pool)
await schema_manager.initialize()
```

The schema manager is automatically initialized during `init_db()`.

## Error Handling

The module provides detailed error logging for:
- Database initialization failures
- Connection pool errors
- Schema management errors
- Database creation issues

Example error handling:

```python
try:
    await init_db()
except Exception as e:
    logger.error(f"Database initialization failed: {e}")
    raise
```

## Integration with Config

The module integrates with the config module for database settings:

```python
from config import settings_conf

db_url = settings_conf.get('db_url')
```

## Module Dependencies

The database module depends on:
- `asyncpg`: For async PostgreSQL/CockroachDB connections
- `config`: For configuration settings
- `.lib.schema_manager`: For schema management

## Connection Lifecycle

1. **Initialization**
   - Create database if needed
   - Initialize connection pool
   - Set up schema manager

2. **Usage**
   - Get pool via get_pool()
   - Acquire connections from pool
   - Execute queries

3. **Cleanup**
   - Close pool via close()
   - Clear global references

## Best Practices

1. Always initialize the database before use
2. Use the connection pool for all database operations
3. Close the pool during application shutdown
4. Handle database errors appropriately
5. Use transactions for multi-statement operations
6. Let the schema manager handle schema changes

## Schema Management

The schema is managed through version files in the `schema/` directory. Each version file defines:

- Tables with columns, constraints, and indexes
- Triggers for automatic data updates
- Foreign key relationships
- Conditional indexes

The schema manager handles:
1. Creating the schema_version table to track migrations
2. Loading and validating schema files
3. Creating tables, indexes, and constraints
4. Setting up triggers for automatic updates
5. Applying migrations in version order

### Core Tables

#### Blocks Table
```sql
CREATE TABLE blocks (
    hash TEXT PRIMARY KEY,
    height INT8 NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

#### Transaction Entries Table
```sql
CREATE TABLE transaction_entries (
    tx_hash TEXT,
    address TEXT,
    entry_type TEXT,
    asset_name TEXT,
    amount DECIMAL NOT NULL,
    fee DECIMAL,
    confirmations INT8 DEFAULT 0,
    time TIMESTAMP,
    asset_type TEXT,
    asset_message TEXT,
    vout INT8,
    trusted BOOLEAN DEFAULT false,
    bip125_replaceable BOOLEAN DEFAULT false,
    abandoned BOOLEAN DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (tx_hash, address, entry_type, asset_name)
);
```

#### Listings Tables
```sql
CREATE TABLE listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_address TEXT NOT NULL,
    listing_address TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    image_ipfs_hash TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE listing_prices (
    listing_id UUID,
    asset_name TEXT,
    price_evr DECIMAL,
    price_asset_name TEXT,
    price_asset_amount DECIMAL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (listing_id, asset_name),
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);

CREATE TABLE listing_addresses (
    listing_id UUID,
    asset_name TEXT,
    deposit_address TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (listing_id, asset_name),
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);

CREATE TABLE listing_balances (
    listing_id UUID,
    asset_name TEXT,
    deposit_address TEXT NOT NULL,
    confirmed_balance DECIMAL NOT NULL DEFAULT 0,
    pending_balance DECIMAL NOT NULL DEFAULT 0,
    last_confirmed_tx_hash TEXT,
    last_confirmed_tx_time TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (listing_id, asset_name),
    FOREIGN KEY (listing_id) REFERENCES listings(id),
    FOREIGN KEY (deposit_address) REFERENCES listing_addresses(deposit_address)
);
```

### Automatic Balance Updates

The system uses a trigger to automatically update listing balances when transactions reach the required number of confirmations (6 by default):

```sql
CREATE OR REPLACE FUNCTION update_listing_balance()
RETURNS TRIGGER AS $$
BEGIN
    -- Only handle receive transactions that reach min_confirmations
    IF NEW.entry_type = 'receive' AND NEW.confirmations >= 6 AND 
       (OLD.confirmations IS NULL OR OLD.confirmations < 6) THEN
        
        -- Update listing balances for this transaction
        UPDATE listing_balances lb
        SET 
            confirmed_balance = confirmed_balance + NEW.amount,
            pending_balance = pending_balance - NEW.amount,
            last_confirmed_tx_hash = NEW.tx_hash,
            last_confirmed_tx_time = NEW.time,
            updated_at = now()
        FROM listing_addresses la
        WHERE la.deposit_address = NEW.address
        AND la.asset_name = NEW.asset_name
        AND lb.listing_id = la.listing_id
        AND lb.deposit_address = la.deposit_address;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_listing_balance_trigger
AFTER UPDATE OF confirmations ON transaction_entries
FOR EACH ROW
EXECUTE FUNCTION update_listing_balance();
```

## CockroachDB Compatibility

The schema is designed to work with CockroachDB Cloud:

- Uses compatible data types (INT8, TEXT, TIMESTAMP, etc.)
- Properly handles foreign key constraints
- Uses triggers for automatic updates
- Includes appropriate indexes for performance

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
6. Never modify the `schema_version` table directly - let the schema manager handle it 