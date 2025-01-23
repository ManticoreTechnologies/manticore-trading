from rpc import (
    # Blockchain
    getblockcount, getbestblockhash, getblock, getmempoolinfo,
    # Network
    getnetworkinfo, getconnectioncount,
    # Assets
    listassets, getassetdata,
    # Wallet
    getwalletinfo, getbalance,
    # Utility
    uptime, validateaddress
)

def print_section(title):
    print(f"\n{'-'*20} {title} {'-'*20}")

# Test blockchain methods
print_section("Blockchain Info")
count = getblockcount()
print(f"Current block height: {count}")

best_hash = getbestblockhash()
print(f"Best block hash: {best_hash}")

latest_block = getblock(best_hash)
print(f"Latest block time: {latest_block.get('time')}")
print(f"Block size: {latest_block.get('size')} bytes")
print(f"Block weight: {latest_block.get('weight')}")

mempool = getmempoolinfo()
print(f"Mempool size: {mempool.get('size')} transactions")
print(f"Mempool bytes: {mempool.get('bytes')} bytes")

# Test network info
print_section("Network Info")
net_info = getnetworkinfo()
print(f"Version: {net_info.get('version')}")
print(f"Subversion: {net_info.get('subversion')}")
print(f"Protocol version: {net_info.get('protocolversion')}")
print(f"Connections: {getconnectioncount()}")

# Test asset info
print_section("Asset Info")
assets = listassets()
print(f"Total assets: {len(assets)}")
if assets:
    # Get details of first asset
    first_asset = next(iter(assets))
    asset_data = getassetdata(first_asset)
    print(f"\nFirst asset details:")
    print(f"Name: {first_asset}")
    print(f"Amount: {asset_data.get('amount')}")
    print(f"Units: {asset_data.get('units')}")
    print(f"Reissuable: {asset_data.get('reissuable')}")

# Test wallet info
print_section("Wallet Info")
wallet = getwalletinfo()
print(f"Wallet version: {wallet.get('walletversion')}")
print(f"Balance: {wallet.get('balance')}")
print(f"Unconfirmed balance: {wallet.get('unconfirmed_balance')}")
print(f"Immature balance: {wallet.get('immature_balance')}")
print(f"Total balance: {getbalance()}")

# Test utility methods
print_section("Node Status")
print(f"Node uptime: {uptime()} seconds")

# Test address validation
test_address = "mxVFsFW5N4mu1HPkxPttorvocvzeZ7KZyk"  # Example testnet address
address_info = validateaddress(test_address)
print(f"\nAddress validation for {test_address}:")
print(f"Is valid: {address_info.get('isvalid')}")
if address_info.get('isvalid'):
    print(f"Is mine: {address_info.get('ismine', False)}")
    print(f"Is script: {address_info.get('isscript', False)}")
    print(f"Is witness: {address_info.get('iswitness', False)}") 