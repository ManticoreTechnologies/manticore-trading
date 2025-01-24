# Transaction Monitor

A module for real-time monitoring of blockchain transactions and blocks. This module provides comprehensive tracking of both EVR and asset transactions, with support for confirmation updates and balance tracking.

## Features

- Real-time transaction monitoring via ZMQ
- Block tracking and confirmation updates
- Support for both EVR and asset transactions
- Listing and order balance tracking
- Configurable minimum confirmations
- Detailed logging and error reporting

## Usage

```python
from monitor import monitor_transactions
from database import get_pool

async def main():
    # Get database pool
    pool = await get_pool()
    
    # Create monitor instance
    monitor = monitor_transactions(pool)
    
    try:
        # Start monitoring
        await monitor.start()
    except KeyboardInterrupt:
        # Stop monitoring gracefully
        monitor.stop()
```

## Transaction Tracking

The module tracks transactions with detailed information:

### EVR Transactions
```json
{
    "tx_hash": "3703abc074ab825c...",
    "address": "EZekLb2Epp...",
    "entry_type": "send",
    "asset_name": "EVR",
    "amount": "0.10000000",
    "fee": "0.02260000",
    "confirmations": 1,
    "time": "2024-01-23T00:00:00Z",
    "vout": 0,
    "trusted": true,
    "bip125_replaceable": false,
    "abandoned": false
}
```

### Asset Transactions
```json
{
    "tx_hash": "9dbe857e8846a84a...",
    "address": "EbY5su2eyc...",
    "entry_type": "receive",
    "asset_name": "CREDITS",
    "amount": "1.00000000",
    "fee": "0.00000000",
    "confirmations": 0,
    "time": "2024-01-23T00:00:00Z",
    "asset_type": "transfer_asset",
    "asset_message": "",
    "vout": 1,
    "trusted": true,
    "bip125_replaceable": false,
    "abandoned": false
}
```

## Block Tracking

The monitor processes new blocks and updates transaction confirmations:

- Stores block data (hash, height, timestamp)
- Updates confirmation counts for existing transactions
- Processes newly confirmed transactions for listings and orders
- Triggers balance updates when minimum confirmations are reached

## Configuration

The monitor can be configured through the settings file:

```python
# Default configuration
min_confirmations = 6  # Minimum confirmations for transaction finality
```

## API Reference

### TransactionMonitor

#### Constructor
```python
monitor = TransactionMonitor(pool=None, min_confirmations=6)
```
- `pool`: Optional database pool (will get from database module if not provided)
- `min_confirmations`: Number of confirmations required for transaction finality

#### Methods

##### start()
Start the blockchain monitoring system. Sets up ZMQ subscriptions and starts processing notifications.

##### stop()
Stop the monitoring system gracefully. Closes ZMQ connections.

##### sync_historical_blocks(start_height=None)
Sync historical blocks from a given height.
- `start_height`: Optional starting block height (default: 0)

## Database Integration

The monitor integrates with several database tables:

- `blocks`: Stores block data
- `transaction_entries`: Stores transaction details
- `listing_balances`: Tracks listing asset balances
- `order_balances`: Tracks order payment balances

Each transaction entry includes:
- Transaction details (hash, address, amount, etc.)
- Asset information for asset transactions
- Confirmation status
- BIP125 replaceability status
- Trust and abandonment status

## Error Handling

The module handles various error conditions:
- Wallet transaction validation
- Transaction processing errors
- Block processing errors
- Database connection issues
- ZMQ notification handling

## Logging

The module provides detailed logging for:
- Block processing
- Transaction processing
- Balance updates
- Error conditions
- System status

Example log messages:
```
INFO: Processed block 1166094 (000000000022d5c9...)
INFO: Updated listing abc-123 balances: Asset=NFT1, Pending=1.0, Confirmed=0.5
INFO: Processed receive entry for CREDITS: tx=9dbe85..., address=EbY5su2..., amount=1.00000000
ERROR: Error processing transaction abc123: Transaction not found in wallet
```

## Integration with Other Modules

The monitor integrates with:
- `listings`: For tracking listing deposits and balances
- `orders`: For tracking order payments and balances
- `database`: For persistent storage
- `rpc`: For blockchain interaction
- `config`: For configuration management

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