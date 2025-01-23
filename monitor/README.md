# Transaction Monitor

A module for real-time monitoring of blockchain transactions and blocks. This module provides comprehensive tracking of both EVR and asset transactions, with support for confirmation updates and balance tracking.

## Features

- Real-time transaction monitoring via ZMQ
- Block tracking and confirmation updates
- Support for both EVR and asset transactions
- Per-address transaction tracking
- Automatic abandoned transaction handling
- Detailed logging and error reporting

## Quick Start

```python
from database import init_db, get_pool
from monitor import start_monitoring, stop_monitoring

async def main():
    # Initialize database
    await init_db()
    pool = await get_pool()
    
    try:
        # Start monitoring
        await start_monitoring(pool)
    except KeyboardInterrupt:
        # Stop monitoring gracefully
        stop_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
```

## Transaction Tracking

The module tracks transactions with detailed information:

### EVR Transactions
```json
{
    "tx_hash": "3703abc074ab825c...",
    "address": "EZekLb2Epp...",
    "entry_type": "send",  // Relative to our wallet
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
    "entry_type": "receive",  // Relative to our wallet
    "asset_name": "CREDITS",
    "amount": 1.00000000,
    "asset_type": "transfer_asset",
    "confirmations": 0
}
```

## Block Tracking

The module tracks blocks and updates transaction confirmations:

```python
# Example block data
{
    "hash": "000000000022d5c9...",
    "height": 1166094,
    "timestamp": 1737597110
}
```

## API Reference

### start_monitoring(pool)
Start the blockchain monitoring system.
- `pool`: Database connection pool

### stop_monitoring()
Stop the monitoring system gracefully.

### sync_historical_blocks(start_height=None)
Sync historical blocks from a given height.
- `start_height`: Optional starting block height (default: 0)

## Error Handling

The module handles various error conditions:
- Node connection issues
- Invalid transactions
- Duplicate notifications
- Database errors
- ZMQ connection issues

## Logging

The module provides detailed logging:
```
2025-01-22 19:58:14,022 - monitor - INFO - Starting ZMQ listener and notification processor...
2025-01-22 19:58:45,210 - monitor - INFO - Processed block 1166021 (0000000...)
2025-01-22 19:58:45,721 - monitor - INFO - Processed receive entry for CREDITS: tx=9dbe85..., address=EbY5su2..., amount=1.00000000, confirmations=0
```

## Best Practices

1. **Error Handling**
   - Always wrap monitoring in try/except
   - Handle shutdown gracefully
   - Monitor error logs

2. **Database Management**
   - Use connection pooling
   - Handle transactions properly
   - Keep indexes updated

3. **Performance**
   - Process notifications asynchronously
   - Use batch updates when possible
   - Monitor memory usage

## Common Issues

1. **Missing Transactions**
   - Check ZMQ connection
   - Verify wallet transaction visibility
   - Check node synchronization

2. **Confirmation Issues**
   - Verify block processing
   - Check database updates
   - Monitor block notifications

3. **Performance Problems**
   - Monitor queue size
   - Check database performance
   - Verify system resources 