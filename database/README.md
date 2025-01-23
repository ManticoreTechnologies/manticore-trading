# Database Module

This module manages connections to CockroachDB, schema management, and database operations.

## Features

- Connection pooling with asyncpg
- Robust schema versioning and migration system
- Automatic balance tracking for listings via triggers
- Support for multiple assets per listing
- Comprehensive transaction and block tracking

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

## Usage

### Initialization
```python
from database import init_db, get_pool, close

# Initialize database and schema
await init_db()

# Get connection pool
pool = get_pool()

# Use pool for queries
async with pool.acquire() as conn:
    result = await conn.fetch('SELECT * FROM listings')

# Close pool when shutting down
await close()
```

### Schema Updates

To add a new schema version:

1. Create a new file `vX.py` in the schema directory
2. Define the schema with:
   - `version`: Schema version number
   - `tables`: List of table definitions
   - `triggers`: List of trigger definitions

Example:
```python
schema = {
    'version': 1,
    'tables': [...],
    'triggers': [...]
}
```

## CockroachDB Compatibility

The schema is designed to work with CockroachDB Cloud:

- Uses compatible data types (INT8, TEXT, TIMESTAMP, etc.)
- Properly handles foreign key constraints
- Uses triggers for automatic updates
- Includes appropriate indexes for performance

## Error Handling

The module includes custom exceptions:
- `DatabaseError`: Base exception for database errors
- `DatabasePoolError`: Connection pool errors
- `DatabaseSchemaError`: Schema validation/migration errors

## Best Practices

1. Always use the connection pool
2. Handle database errors appropriately
3. Use transactions for multi-statement operations
4. Add appropriate indexes for queries
5. Test schema changes thoroughly
6. Document schema updates in version files

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