# Orders Module

This module handles order management for the marketplace, including:
- Order creation and validation
- Payment tracking
- Order fulfillment
- Fee distribution

## Key Components

### Database Tables

- `orders`: Tracks order details, payment status, and overall state
- `order_items`: Stores individual assets being purchased in each order

### Status Flow

1. `pending` - Initial state, waiting for payment
2. `partially_paid` - Some payment received but not complete
3. `paid` - Full payment received
4. `fulfilling` - Processing asset transfers
5. `completed` - All assets transferred and payments distributed
6. `error` - Error occurred during processing
7. `cancelled` - Order cancelled (manual intervention)
8. `refunded` - Payment refunded to buyer

### Error Handling

- `OrderError`: Base class for order-related errors
- `InsufficientBalanceError`: Raised when listing lacks required asset balance
- `InvalidOrderStatusError`: Raised for invalid status transitions

## Usage Example

```python
# Create an order
order = await order_manager.create_order(
    listing_id=listing_id,
    buyer_address="EVR...",
    items=[{
        "asset_name": "ASSET1",
        "amount": Decimal("1.0")
    }]
)

# Get order details
order = await order_manager.get_order(order_id)

# Process paid orders (called periodically)
await order_manager.process_paid_orders()
```

## Configuration

Required settings in `settings.conf`:

```ini
[marketplace]
fee_percent = 0.01  # 1% marketplace fee
fee_address = EVR...  # Address to receive fees
```

## Security Features

1. Balance validation before order creation
2. Atomic transactions for state changes
3. Payment tracking with confirmations
4. Automatic fee calculation and distribution
5. Error state tracking for manual review 