# Listings Module

The listings module provides functionality for managing trading platform listings, including:
- Creating and managing listings
- Tracking listing balances
- Managing deposit addresses
- Price management

## Features

- Full CRUD operations for listings
- Clear separation of user-mutable vs system-managed fields
- Single deposit address per listing for receiving any asset
- Balance tracking with pending/confirmed states
- Multi-asset support
- Price management in EVR or other assets

## Usage

### Creating a Listing

```python
from listings import ListingManager

# Initialize manager
manager = ListingManager()

# Create a listing
listing = await manager.create_listing(
    seller_address="EZekLb2Epp...",
    name="My NFT Collection",
    description="A collection of unique NFTs",
    image_ipfs_hash="Qm...",
    prices=[
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
)

# Get the listing's deposit address for receiving any asset
deposit_address = await manager.get_deposit_address(listing['id'])
print(f"Deposit address: {deposit_address}")
```

### Checking Balances

```python
# Get all balances for a listing
balances = await manager.get_balances(listing['id'])
for asset, balance in balances.items():
    print(f"{asset}:")
    print(f"  Confirmed: {balance['confirmed_balance']}")
    print(f"  Pending: {balance['pending_balance']}")
```

### Updating a Listing

```python
# Update mutable fields
updated = await manager.update_listing(
    listing_id="550e8400-e29b-41d4-a716-446655440000",
    updates={
        "name": "Updated Name",
        "description": "New description",
        "status": "inactive"
    }
)
```

### Getting Listing Details

```python
# By ID
listing = await manager.get_listing("550e8400-e29b-41d4-a716-446655440000")
```

### Deleting a Listing

```python
await manager.delete_listing("550e8400-e29b-41d4-a716-446655440000")
```

## Field Management

### User-Mutable Fields
These fields can be modified by users:
- `name`
- `description`
- `image_ipfs_hash`
- `status`

### System-Managed Fields
These fields are managed by the system and cannot be modified directly:
- `id`
- `seller_address`
- `listing_address` (unique address for storing listing assets)
- `deposit_address` (single address for receiving any asset)
- `created_at`
- `updated_at`

### Balance Fields
These fields are managed by the monitor module:
- `confirmed_balance`
- `pending_balance`
- `last_confirmed_tx_hash`
- `last_confirmed_tx_time`

## Data Structure

### Listing Object
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "seller_address": "EZekLb2Epp...",
    "listing_address": "EbY5su2eyc...",
    "deposit_address": "EUQu16iM6V...",
    "name": "My NFT Collection",
    "description": "A collection of unique NFTs",
    "image_ipfs_hash": "Qm...",
    "status": "active",
    "created_at": "2024-01-23T00:00:00Z",
    "updated_at": "2024-01-23T00:00:00Z",
    "prices": [
        {
            "asset_name": "NFT1",
            "price_evr": 100.0,
            "price_asset_name": null,
            "price_asset_amount": null
        }
    ],
    "balances": [
        {
            "asset_name": "NFT1",
            "confirmed_balance": 1.0,
            "pending_balance": 0.5,
            "last_confirmed_tx_hash": "9dbe857e8846a84a...",
            "last_confirmed_tx_time": "2024-01-23T00:00:00Z"
        }
    ]
}
```

## Error Handling

The module provides several exception classes:

### ListingError
Base exception for listing operations.

### ListingNotFoundError
Raised when a listing is not found.

### InvalidPriceError
Raised when price specification is invalid.

## Integration with Monitor

The listings module provides methods used by the monitor module to track deposits and update balances:

```python
# Used by monitor module to handle new deposits
await manager.handle_new_deposit(
    deposit_address="EUQu16iM6V...",
    asset_name="NFT1",
    amount=1.0,
    tx_hash="9dbe857e8846a84a..."
)

# Used by monitor module to update balances
await manager.update_listing_balance(
    listing_id="550e8400-e29b-41d4-a716-446655440000",
    asset_name="NFT1",
    confirmed_delta=1.0,
    pending_delta=-1.0,
    tx_hash="9dbe857e8846a84a..."
)
```

## Deposit Address

Each listing has a single `deposit_address` that is automatically generated when the listing is created. This address is used to receive any asset type that the listing accepts. The monitor module tracks all deposits to this address and updates the appropriate asset balances based on the transaction details.

The deposit address is immutable and cannot be changed after creation. This ensures consistent tracking of deposits throughout the listing's lifecycle.
