# Orders Module

This module handles order management for the marketplace, including:
- Order creation and validation
- Balance tracking
- Payment address management
- Fee calculation

## Features

- Automatic payment address generation
- Multi-asset order support
- Balance validation before order creation
- Automatic fee calculation
- Detailed order tracking

## Usage

```python
from orders import OrderManager
from decimal import Decimal

# Initialize manager
manager = OrderManager()

# Create an order
order = await manager.create_order(
    listing_id="550e8400-e29b-41d4-a716-446655440000",
    buyer_address="EVR...",
    items=[
        {
            "asset_name": "NFT1",
            "amount": Decimal("1.0")
        },
        {
            "asset_name": "NFT2",
            "amount": Decimal("2.0")
        }
    ]
)

# Get order details
order = await manager.get_order(order['id'])

# Check order balances
balances = await manager.get_order_balances(order['id'])
```

## Configuration

The module uses these default settings:

```python
DEFAULT_FEE_PERCENT = Decimal('0.01')  # 1% fee
DEFAULT_FEE_ADDRESS = "EVRFeeAddressGoesHere"  # Fee collection address
```

## Database Integration

The module integrates with several database tables:

### orders
Stores core order information:
- Order ID
- Listing ID
- Buyer address
- Payment address
- Status
- Timestamps

### order_items
Stores individual items in each order:
- Asset name
- Amount
- Price in EVR
- Fee in EVR

### order_balances
Tracks payment balances:
- Confirmed balance
- Pending balance
- Per asset tracking

## Error Handling

The module provides several exception classes:

### OrderError
Base exception for order-related errors.

### InsufficientBalanceError
Raised when a listing has insufficient balance for order items.
```python
try:
    await manager.create_order(...)
except InsufficientBalanceError as e:
    print(f"Not enough {e.asset_name}: have {e.available}, need {e.requested}")
```

### ListingNotFoundError
Raised when the requested listing is not found or inactive.

### AssetNotFoundError
Raised when the requested asset is not found in the listing.

## Data Structures

### Order Object
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "listing_id": "123e4567-e89b-12d3-a456-426614174000",
    "buyer_address": "EVR...",
    "payment_address": "EVR...",
    "created_at": "2024-01-23T00:00:00Z",
    "updated_at": "2024-01-23T00:00:00Z",
    "items": [
        {
            "asset_name": "NFT1",
            "amount": "1.0",
            "price_evr": "100.0",
            "fee_evr": "1.0"
        }
    ],
    "balances": [
        {
            "asset_name": "EVR",
            "confirmed_balance": "0.0",
            "pending_balance": "0.0"
        }
    ],
    "total_price_evr": "100.0",
    "total_fee_evr": "1.0",
    "total_payment_evr": "101.0"
}
```

## Order Creation Process

1. Generate unique payment address
2. Verify listing exists and is active
3. Check asset availability and balances
4. Calculate prices and fees
5. Create order record
6. Create order items
7. Initialize balance tracking
8. Return complete order details

## Database Operations

All database operations are performed in individual transactions for data consistency:
- Listing verification
- Balance checking
- Order creation
- Item creation
- Balance initialization

## Integration with Other Modules

The order module integrates with:
- `listings`: For checking asset availability
- `database`: For persistent storage
- `rpc`: For payment address generation 