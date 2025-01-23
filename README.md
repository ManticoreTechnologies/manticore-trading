# Manticore Trading Backend Service

A high-performance backend service for real-time blockchain monitoring and trading operations on the Evrmore network. This service provides a robust foundation for building trading applications with real-time transaction and block monitoring.

## Features

- Real-time blockchain monitoring using ZMQ notifications
- Transaction and block tracking with confirmation status
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
- See [RPC Documentation](rpc/README.md)

### 2. ZMQ Module (`rpc/zmq/`)
- Real-time blockchain notifications
- Asynchronous event handling
- Automatic reconnection
- Clean shutdown handling
- See [ZMQ Documentation](rpc/zmq/README.md)

### 3. Database Module (`database/`)
- CockroachDB integration
- Schema versioning and migrations
- Connection pooling
- Transaction management
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

### Transactions Table
```sql
CREATE TABLE transactions (
    hash STRING PRIMARY KEY,
    version INT8,
    size INT8,
    time INT8,
    confirmations INT8 DEFAULT 0,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
```

## Monitoring

The service provides detailed logging:
```
2025-01-22 19:58:14,022 - __main__ - INFO - Starting ZMQ listener and notification processor...
2025-01-22 19:58:45,210 - __main__ - INFO - Processed block 1166021 (0000000...)
2025-01-22 19:58:45,721 - __main__ - INFO - Processed transaction 6de28d... (size: 224 bytes, confirmations: 0)
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

## Error Handling

The service handles various error conditions:
- Node connection issues
- Database connectivity
- Invalid transactions
- Duplicate notifications
- Schema migration failures

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
