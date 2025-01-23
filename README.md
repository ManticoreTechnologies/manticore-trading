# Manticore Trading Backend Service

A high-performance backend service for real-time blockchain monitoring and trading operations on the Evrmore network. This service provides a robust foundation for building trading applications with real-time transaction and block monitoring, supporting both EVR and asset transactions.

## Features

- Real-time blockchain monitoring using ZMQ notifications
- Wallet transaction tracking with confirmation status
- Asset transaction support (transfers, new assets, etc.)
- Per-address transaction entry tracking
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
- Balance tracking per address
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

### Blocks Table
```sql
CREATE TABLE blocks (
    hash STRING PRIMARY KEY,
    height INT8 UNIQUE,
    timestamp INT8,
    created_at TIMESTAMP DEFAULT now()
);
```

### Transaction Entries Table
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

## Monitoring

The service provides detailed logging:
```
2025-01-22 19:58:14,022 - __main__ - INFO - Starting ZMQ listener and notification processor...
2025-01-22 19:58:45,210 - __main__ - INFO - Processed block 1166021 (0000000...)
2025-01-22 19:58:45,721 - __main__ - INFO - Processed receive entry for CREDITS: tx=9dbe85..., address=EbY5su2..., amount=1.00000000, confirmations=0
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
The service tracks balances per address and asset:
- Individual transaction entries for precise history
- Separate send/receive records
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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
