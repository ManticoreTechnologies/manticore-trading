# Evrmore RPC Client

A Python client for interacting with the Evrmore node's RPC interface. This module provides a clean, type-safe interface to all Evrmore RPC methods with proper error handling and configuration management.

## Features

- Complete coverage of Evrmore RPC methods
- Automatic configuration from `evrmore.conf`
- Proper error handling with specific error types
- Thread-safe RPC calls
- Built-in retry mechanisms
- ZMQ notification support (see [ZMQ module](zmq/README.md))

## Quick Start

```python
from rpc import getblockcount, getblockhash, getblock

# Get current blockchain info
block_count = getblockcount()
block_hash = getblockhash(block_count)
latest_block = getblock(block_hash)

print(f"Latest block: {block_count}")
print(f"Block hash: {block_hash}")
print(f"Block time: {latest_block['time']}")
```

## Configuration

The module reads configuration from your `evrmore.conf` file. Required settings:

```conf
# RPC settings
rpcuser=your_username
rpcpassword=your_password
rpcport=8819  # Default Evrmore RPC port
```

## Available Methods

### Blockchain Methods
```python
from rpc import (
    getbestblockhash,    # Get hash of best block
    getblock,            # Get block data
    getblockchaininfo,   # Get blockchain info
    getblockcount,       # Get block height
    getblockhash,        # Get block hash at height
    getblockheader,      # Get block header
    getchaintips,        # Get chain tips
    getdifficulty,       # Get network difficulty
    getmempoolinfo,      # Get mempool info
    getrawmempool,       # Get mempool transactions
    gettxout,            # Get transaction output
    gettxoutsetinfo,     # Get UTXO set info
    verifychain          # Verify blockchain database
)
```

### Asset Methods
```python
from rpc import (
    getassetdata,        # Get asset metadata
    getcacheinfo,        # Get asset cache info
    getsnapshot,         # Get asset holders snapshot
    issue,               # Issue new asset
    issueunique,         # Issue unique asset
    listassets,          # List all assets
    listmyassets,        # List owned assets
    reissue,             # Reissue existing asset
    transfer,            # Transfer assets
    transferfromaddress  # Transfer from specific address
)
```

### Wallet Methods
```python
from rpc import (
    getbalance,          # Get wallet balance
    getnewaddress,       # Get new address
    listunspent,         # List unspent outputs
    sendtoaddress,       # Send to address
    sendfrom,            # Send from account
    sendmany,            # Send to multiple addresses
    # ... and many more
)
```

## Error Handling

The module provides specific error types for different failure scenarios:

```python
from rpc import (
    RPCError,           # Base error type
    NodeConnectionError, # Connection failed
    NodeAuthError,      # Authentication failed
    EvrmoreError        # Evrmore-specific errors
)

try:
    balance = getbalance()
except NodeConnectionError as e:
    print(f"Failed to connect: {e}")
except NodeAuthError as e:
    print(f"Authentication failed: {e}")
except EvrmoreError as e:
    print(f"Evrmore error [{e.code}]: {e}")
```

### Common Error Codes

| Code | Description |
|------|-------------|
| -1   | General error during processing |
| -3   | Asset not found |
| -4   | Out of memory |
| -5   | Invalid parameter |
| -8   | Invalid parameter combination |
| -20  | Invalid address or key |
| -22  | Error parsing JSON |
| -25  | Error processing transaction |
| -26  | Transaction already in chain |
| -27  | Transaction already in mempool |

## Advanced Usage

### Custom RPC Calls

```python
from rpc import client

# Direct RPC call with custom parameters
result = client._call_method('custommethod', param1, param2)
```

### Batch Operations

```python
# Get multiple blocks efficiently
blocks = []
for height in range(1000, 1010):
    block_hash = getblockhash(height)
    block = getblock(block_hash)
    blocks.append(block)
```

### Asset Operations

```python
# Issue new asset
asset_name = "MYASSET"
qty = 1000
units = 0
reissuable = True
has_ipfs = False

try:
    result = issue(
        asset_name=asset_name,
        qty=qty,
        units=units,
        reissuable=reissuable,
        has_ipfs=has_ipfs
    )
    print(f"Asset issued: {result}")
except EvrmoreError as e:
    print(f"Failed to issue asset: {e}")
```

### Transaction Management

```python
# Create and send transaction
inputs = [
    {"txid": "abc...", "vout": 0},
    {"txid": "def...", "vout": 1}
]
outputs = {
    "addr1": 10.0,
    "addr2": 5.0
}

raw_tx = createrawtransaction(inputs, outputs)
signed_tx = signrawtransaction(raw_tx)
tx_id = sendrawtransaction(signed_tx['hex'])
```

## Best Practices

1. **Error Handling**
   - Always catch specific exceptions
   - Handle connection errors appropriately
   - Log RPC errors with their codes

2. **Performance**
   - Minimize RPC calls when possible
   - Use batch operations for multiple queries
   - Consider using ZMQ for real-time updates

3. **Security**
   - Keep RPC credentials secure
   - Use SSL/TLS when connecting remotely
   - Limit RPC access to necessary methods

4. **Resource Management**
   - Handle large responses carefully
   - Clean up resources after use
   - Monitor memory usage with large datasets

## Common Issues

1. **Connection Problems**
   - Verify RPC settings in `evrmore.conf`
   - Check network connectivity
   - Verify firewall settings

2. **Authentication Failures**
   - Double-check RPC credentials
   - Verify RPC user permissions
   - Check for special characters in password

3. **Performance Issues**
   - Reduce number of RPC calls
   - Use appropriate batch sizes
   - Monitor network latency

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 