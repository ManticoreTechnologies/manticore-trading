# Listings Module

The listings module provides functionality for managing marketplace listings, including:
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
```

### Getting Listing Details

```python
# By ID
listing = await manager.get_listing("550e8400-e29b-41d4-a716-446655440000")

# By deposit address
listing = await manager.get_listing_by_deposit_address("EUQu16iM6V...")

# Get just the deposit address
deposit_address = await manager.get_deposit_address("550e8400-e29b-41d4-a716-446655440000")
```

### Checking Balances

```python
# Get all balances for a listing
balances = await manager.get_balances(listing_id)
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
- `listing_address`
- `deposit_address`
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
            "pending_balance": 0.5
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

## Database Integration

The module uses an async database pool for all operations. The pool can be provided during initialization or will be automatically retrieved from the database module:

```python
# With custom pool
manager = ListingManager(pool=my_pool)

# With default pool
manager = ListingManager()  # Will get pool from database module
```

Each database operation is performed in its own transaction for data consistency. The module handles:
- Creating listings with associated prices and balance entries
- Retrieving listings with all related data
- Updating mutable fields
- Deleting listings and all associated data in the correct order

## Deposit Address System

Each listing has a unique deposit address generated at creation time using the `getnewaddress()` RPC call. This address is immutable and stored in the `deposit_address` field. The address can be used to:
- Receive any supported asset type
- Look up the associated listing
- Track deposits and balances
