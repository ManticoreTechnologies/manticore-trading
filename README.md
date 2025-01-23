# Manticore Trading Backend Service

A high-performance backend service for real-time blockchain monitoring and trading operations on the Evrmore network. This service provides a robust foundation for building trading applications with real-time transaction and block monitoring, supporting both EVR and asset transactions.

## Features

- Real-time blockchain monitoring using ZMQ notifications
- Wallet transaction tracking with confirmation status
- Asset transaction support (transfers, new assets, etc.)
- Per-address transaction entry tracking
- Trading platform with listings and deposits
- Multi-asset pricing support
- Balance tracking per listing and address
- High-performance CockroachDB storage
- Clean architecture with modular design
- Robust error handling and graceful shutdown
- Type-safe RPC interface to Evrmore node

## Architecture

The service is built with three main components:

### 1. RPC Module (`rpc/`)
- Complete Evrmore RPC client implementation
- Type-safe method interfaces
- Automatic configuration from `evrmore.conf`
- Built-in retry and error handling
- Wallet transaction monitoring
- Asset operation support
- See [RPC Documentation](rpc/README.md)

### 2. ZMQ Module (`rpc/zmq/`)
- Real-time blockchain notifications
- Asynchronous event handling
- Automatic reconnection
- Clean shutdown handling
- Transaction and block monitoring
- See [ZMQ Documentation](rpc/zmq/README.md)

### 3. Database Module (`database/`)
- CockroachDB integration
- Schema versioning and migrations
- Connection pooling
- Transaction management
- Balance tracking per listing
- Asset holdings tracking
- See [Database Documentation](database/README.md)

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Evrmore Node**
   ```bash
   # Copy example config
   cp examples/evrmore.conf.example ~/.evrmore/evrmore.conf
   
   # Edit required settings
   nano ~/.evrmore/evrmore.conf
   ```
   Required settings:
   ```ini
   server=1
   rpcuser=your_username
   rpcpassword=your_password
   rpcport=8819
   txindex=1
   addressindex=1
   
   # ZMQ settings
   zmqpubhashtx=tcp://127.0.0.1:2936
   zmqpubrawblock=tcp://127.0.0.1:2935
   zmqpubsequence=tcp://127.0.0.1:2934
   zmqpubrawtx=tcp://127.0.0.1:29332
   zmqpubhashblock=tcp://127.0.0.1:29333
   ```

3. **Configure Service**
   ```bash
   # Copy example settings
   cp examples/settings.conf.example settings.conf
   
   # Edit settings
   nano settings.conf
   ```
   Required settings:
   ```ini
   [DEFAULT]
   evrmore_root = /home/your_user/.evrmore/
   db_url = postgresql://user:pass@host:port/db?sslmode=verify-full
   ```

4. **Run the Service**
   ```bash
   python main.py
   ```

## Data Model

### Core Tables

#### Blocks Table
```sql
CREATE TABLE blocks (
    hash STRING PRIMARY KEY,
    height INT8 UNIQUE,
    timestamp INT8,
    created_at TIMESTAMP DEFAULT now()
);
```

#### Transaction Entries Table
```sql
CREATE TABLE transaction_entries (
    tx_hash STRING,
    address STRING,
    entry_type STRING,  -- 'send' or 'receive'
    asset_name STRING DEFAULT 'EVR',  -- EVR or asset name
    amount DECIMAL(20,8) DEFAULT 0,
    fee DECIMAL(20,8) DEFAULT 0,
    confirmations INT8 DEFAULT 0,
    time INT8,
    asset_type STRING,  -- transfer_asset, new_asset, etc
    asset_message STRING,
    vout INT8,
    trusted BOOLEAN DEFAULT false,
    bip125_replaceable BOOLEAN DEFAULT false,
    abandoned BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (tx_hash, address, entry_type, asset_name)
);
```

### Trading Platform Tables

#### Listings Table
```sql
CREATE TABLE listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_address STRING NOT NULL,
    name STRING NOT NULL,
    description STRING,
    image_ipfs_hash STRING,
    status STRING NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);
```

#### Listing Prices Table
```sql
CREATE TABLE listing_prices (
    listing_id UUID NOT NULL REFERENCES listings(id),
    asset_name STRING NOT NULL,
    price_evr DECIMAL(24,8),  -- Price in EVR
    price_asset_name STRING,   -- Or price in another asset
    price_asset_amount DECIMAL(24,8),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (listing_id, asset_name)
);
```

#### Listing Addresses Table
```sql
CREATE TABLE listing_addresses (
    listing_id UUID NOT NULL REFERENCES listings(id),
    deposit_address STRING NOT NULL,
    asset_name STRING NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (listing_id, asset_name),
    UNIQUE INDEX listing_addresses_by_address (deposit_address)
);
```

#### Listing Balances Table
```sql
CREATE TABLE listing_balances (
    listing_id UUID NOT NULL REFERENCES listings(id),
    asset_name STRING NOT NULL,
    confirmed_balance DECIMAL(24,8) NOT NULL DEFAULT 0,
    pending_balance DECIMAL(24,8) NOT NULL DEFAULT 0,
    last_confirmed_tx_hash STRING,
    last_confirmed_tx_time TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (listing_id, asset_name)
);
```

#### Listing Transactions Table
```sql
CREATE TABLE listing_transactions (
    tx_hash STRING NOT NULL,
    listing_id UUID NOT NULL REFERENCES listings(id),
    asset_name STRING NOT NULL,
    amount DECIMAL(24,8) NOT NULL,
    tx_type STRING NOT NULL,
    confirmations INT8 NOT NULL DEFAULT 0,
    status STRING NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (tx_hash, listing_id, asset_name)
);
```

## Transaction Tracking

The service tracks both EVR and asset transactions with detailed information:

### EVR Transactions
```json
{
    "tx_hash": "3703abc074ab825c...",
    "address": "EZekLb2Epp...",
    "entry_type": "send",
    "asset_name": "EVR",
    "amount": 0.10000000,
    "fee": 0.02260000,
    "confirmations": 1
}
```

### Asset Transactions
```json
{
    "tx_hash": "9dbe857e8846a84a...",
    "address": "EbY5su2eyc...",
    "entry_type": "receive",
    "asset_name": "CREDITS",
    "amount": 1.00000000,
    "asset_type": "transfer_asset",
    "confirmations": 0
}
```

## Trading Platform

The service supports creating and managing listings with multiple assets:

### Creating a Listing
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "seller_address": "EZekLb2Epp...",
    "name": "My NFT Collection",
    "description": "A collection of unique NFTs",
    "image_ipfs_hash": "Qm...",
    "prices": [
        {
            "asset_name": "NFT1",
            "price_evr": 100.0
        },
        {
            "asset_name": "NFT2",
            "price_asset_name": "USDT",
            "price_asset_amount": 50.0
        }
    ]
}
```

### Listing Deposits
Each listing gets unique deposit addresses per asset:
```json
{
    "listing_id": "550e8400-e29b-41d4-a716-446655440000",
    "deposits": [
        {
            "asset_name": "NFT1",
            "deposit_address": "EbY5su2eyc..."
        },
        {
            "asset_name": "NFT2",
            "deposit_address": "EZekLb2Epp..."
        }
    ]
}
```

### Balance Tracking
The service tracks both confirmed and pending balances:
```json
{
    "listing_id": "550e8400-e29b-41d4-a716-446655440000",
    "balances": [
        {
            "asset_name": "NFT1",
            "confirmed_balance": 1.0,
            "pending_balance": 0.5
        }
    ]
}
```

## Monitoring

The service provides detailed logging:
```
2025-01-22 19:58:14,022 - __main__ - INFO - Starting ZMQ listener and notification processor...
2025-01-22 19:58:45,210 - __main__ - INFO - Processed block 1166021 (0000000...)
2025-01-22 19:58:45,721 - __main__ - INFO - Processed receive entry for CREDITS: tx=9dbe85..., address=EbY5su2..., amount=1.00000000, confirmations=0
2025-01-22 19:58:46,123 - __main__ - INFO - Updated listing balance: listing=550e84..., asset=NFT1, confirmed=1.0
```

## Development

### Project Structure
```
manticore-trading/
├── config/           # Configuration management
├── database/         # Database operations
│   ├── schema/      # Database schema versions
│   └── lib/         # Database utilities
├── rpc/             # Evrmore RPC client
│   └── zmq/         # ZMQ notification system
├── examples/        # Example configuration files
├── main.py          # Service entry point
└── requirements.txt # Dependencies
```

### Adding Features
1. **New RPC Methods**
   - Add method to `rpc/__init__.py`
   - Add type hints and documentation
   - Add error handling

2. **Schema Changes**
   - Create new version in `database/schema/`
   - Increment version number
   - Add migration SQL
   - Test migration path

3. **New ZMQ Topics**
   - Add subscription in `main.py`
   - Create handler function
   - Add processing logic

### Balance Tracking
The service tracks balances at multiple levels:
- Per-address transaction entries
- Per-listing asset balances
- Confirmed vs pending states
- Asset-specific tracking
- Confirmation status updates
- Fee tracking on send operations

## Error Handling

The service handles various error conditions:
- Node connection issues
- Database connectivity
- Invalid transactions
- Duplicate notifications
- Schema migration failures
- Asset operation errors
- Wallet transaction validation
- Listing deposit validation
- Balance reconciliation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
