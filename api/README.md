# REST API Module

This module provides a REST API for the Manticore Trading platform using FastAPI. It enables creating and managing listings and orders through HTTP endpoints.

## Features

- RESTful API with OpenAPI/Swagger documentation
- Input validation using Pydantic models
- Proper error handling and status codes
- CORS support for web clients
- Async database operations
- Comprehensive logging

## Endpoints

### Listings

#### POST /listings/
Create a new listing.

Request body:
```json
{
    "seller_address": "EVR...",
    "name": "My NFT Collection",
    "description": "A collection of unique NFTs",
    "image_ipfs_hash": "Qm...",
    "prices": [
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
}
```

#### GET /listings/{listing_id}
Get listing details by ID.

Response:
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "seller_address": "EVR...",
    "listing_address": "EVR...",
    "deposit_address": "EVR...",
    "name": "My NFT Collection",
    "description": "A collection of unique NFTs",
    "image_ipfs_hash": "Qm...",
    "status": "active",
    "created_at": "2024-01-23T00:00:00Z",
    "updated_at": "2024-01-23T00:00:00Z",
    "prices": [
        {
            "asset_name": "NFT1",
            "price_evr": 100.0
        }
    ],
    "balances": [
        {
            "asset_name": "NFT1",
            "confirmed_balance": 1.0,
            "pending_balance": 0.0
        }
    ]
}
```

#### GET /listings/{listing_id}/balances
Get listing balances.

Response:
```json
{
    "NFT1": {
        "confirmed_balance": 1.0,
        "pending_balance": 0.0
    }
}
```

### Orders

#### POST /listings/{listing_id}/orders/
Create a new order for a listing.

Request body:
```json
{
    "buyer_address": "EVR...",
    "items": [
        {
            "asset_name": "NFT1",
            "amount": 1.0
        }
    ]
}
```

Response:
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "listing_id": "123e4567-e89b-12d3-a456-426614174000",
    "buyer_address": "EVR...",
    "payment_address": "EVR...",
    "status": "pending",
    "created_at": "2024-01-23T00:00:00Z",
    "updated_at": "2024-01-23T00:00:00Z",
    "items": [
        {
            "asset_name": "NFT1",
            "amount": 1.0,
            "price_evr": 100.0,
            "fee_evr": 1.0
        }
    ],
    "balances": [
        {
            "asset_name": "EVR",
            "confirmed_balance": 0.0,
            "pending_balance": 0.0
        }
    ],
    "total_price_evr": 100.0,
    "total_fee_evr": 1.0,
    "total_payment_evr": 101.0
}
```

#### GET /orders/{order_id}
Get order details by ID.

#### GET /orders/{order_id}/balances
Get order payment balances.

Response:
```json
{
    "EVR": {
        "confirmed_balance": 50.0,
        "pending_balance": 51.0
    }
}
```

## Error Handling

The API uses standard HTTP status codes:

- 200: Success
- 400: Bad Request (invalid input)
- 404: Not Found
- 500: Internal Server Error

Error responses include a detail message:
```json
{
    "detail": "Error message here"
}
```

## Usage Example

```python
import requests
from decimal import Decimal

# Create a listing
listing = requests.post(
    "http://localhost:8000/listings/",
    json={
        "seller_address": "EVR123...",
        "name": "My NFT",
        "description": "A unique NFT",
        "prices": [{
            "asset_name": "NFT1",
            "price_evr": 100.0
        }]
    }
).json()

# Create an order
order = requests.post(
    f"http://localhost:8000/listings/{listing['id']}/orders/",
    json={
        "buyer_address": "EVR456...",
        "items": [{
            "asset_name": "NFT1",
            "amount": 1.0
        }]
    }
).json()

# Check order balances
balances = requests.get(
    f"http://localhost:8000/orders/{order['id']}/balances"
).json()
```

## Development

### Running the API Server

```bash
# Install dependencies
pip install fastapi uvicorn

# Run the server
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### API Documentation

When running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Testing

```bash
# Install test dependencies
pip install pytest httpx

# Run tests
pytest tests/test_api.py
```

## Security Considerations

1. **CORS Configuration**
   - Configure allowed origins properly in production
   - Don't use wildcard (*) in production

2. **Input Validation**
   - All inputs are validated using Pydantic models
   - Additional validation in manager classes

3. **Error Handling**
   - Errors are logged for debugging
   - User-facing errors don't expose internals

4. **Rate Limiting**
   - Consider adding rate limiting for production
   - Use Redis or similar for distributed rate limiting

## Integration with Other Modules

The API module integrates with:
- `listings`: For listing management
- `orders`: For order processing
- `database`: For data persistence
- `monitor`: For balance tracking 