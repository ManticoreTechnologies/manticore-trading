# Manticore Trading Requirements

This document outlines the core requirements and functionality of the Manticore Trading platform.

## 1. Listing Management ✓

### Asset Management
- [] Create listings with deposit addresses
- [] Track deposits in real-time via ZMQ
- [] Support asset withdrawals to seller address
- [] View deposit/withdrawal history
- [] Track balances with pending/confirmed states

### Implementation Details
- `listings/__init__.py`: Core listing management
- `monitor/__init__.py`: Real-time deposit tracking
- `database/schema/v1.py`: Balance and transaction tracking tables
- `api/__init__.py`: REST endpoints for listing operations

## 2. Order Processing ✓

### Single Orders
- [] Place orders for assets in listings
- [] Track payment status
- [] Process fulfillment when payment confirmed
- [] Support partial fulfillment
- [] Log transaction IDs for all operations

### Cart Orders
- [] Support multiple assets from multiple listings
- [] Calculate total price and fees
- [] Process all items in transaction
- [] Handle partial fulfillment scenarios
- [] Track individual item status

### Implementation Details
- `orders/__init__.py`: Order management and processing
- `monitor/__init__.py`: Payment detection and confirmation
- `database/schema/v1.py`: Order and item tracking tables
- `api/__init__.py`: Order placement and status endpoints

## 3. Payment Processing ✓

### Seller Payments
- [] Calculate correct payment amounts
- [] Process marketplace fees
- [] Send EVR to fee address
- [] Track all payment transactions
- [] Handle failed payments

### Implementation Details
- `orders/__init__.py`: Payment processing logic
- `monitor/__init__.py`: Transaction confirmation tracking
- `database/schema/v1.py`: Payment and fee tracking tables

## 4. Asset Transfer ✓

### Buyer Fulfillment
- [] Transfer assets when payment confirmed
- [] Support partial fulfillment
- [] Track transaction IDs
- [] Log errors for manual review
- [] Update order status appropriately

### Implementation Details
- `orders/__init__.py`: Asset transfer logic
- `monitor/__init__.py`: Transaction tracking
- `database/schema/v1.py`: Transaction and status tracking

## 5. Order Management ✓

### Status Tracking
- [] View order status and history
- [] Track payment status
- [] View fulfillment status
- [] See transaction IDs
- [] Check deposit/withdrawal history

### Error Recovery
- [] Support manual investigation
- [] Allow excess withdrawal
- [] Track failed operations
- [] Provide retry mechanisms

### Implementation Details
- `orders/__init__.py`: Status management
- `api/__init__.py`: Status endpoints
- `database/schema/v1.py`: Status and history tables

## 6. Asset Management ✓

### Hold System
- [] Place holds on listing assets when ordered
- [] Track hold expiration (15 minutes)
- [] Automatically release expired holds
- [] Update available balances
- [] Handle concurrent orders

### Implementation Details
- `orders/__init__.py`: Hold management
- `monitor/__init__.py`: Expiration checking
- `database/schema/v1.py`: Balance and hold tracking

## 7. Sales Tracking ✓

### Statistics
- [x] Track all completed sales
- [x] Calculate OHLCV data
- [x] Support per-asset statistics
- [x] Support per-listing statistics
- [x] Track volume and price history

### API Endpoints
- [x] `/api/v1/stats/ohlcv/{asset}`
- [x] `/api/v1/stats/ohlcv/listing/{id}`
- [x] Query parameters for time range
- [x] Support different intervals
- [x] Include volume data

### Implementation Details
- `api/__init__.py`: Statistics endpoints
- `database/schema/v1.py`: Sales and OHLCV tables

## Database Schema ✓

### Core Tables
- [x] `listings`: Listing management
- [x] `balances`: Asset balances
- [x] `orders`: Order tracking
- [x] `order_items`: Individual items
- [x] `transactions`: Transaction history
- [x] `sales`: Completed sales
- [x] `ohlcv`: Price statistics

### Implementation
- `database/schema/v1.py`: Complete schema
- `database/__init__.py`: Database management
- `database/exceptions.py`: Error handling

## Monitoring System ✓

### Real-time Tracking
- [x] ZMQ integration for transactions
- [x] Block confirmation tracking
- [x] Balance updates
- [x] Order status updates
- [x] Hold management

### Implementation
- `monitor/__init__.py`: Core monitoring
- `rpc/zmq/__init__.py`: ZMQ integration
- `rpc/__init__.py`: Node communication

## Testing Requirements

### Test Coverage
- [ ] Unit tests for core functionality
- [ ] Integration tests for order flow
- [ ] API endpoint testing
- [ ] Error handling verification
- [ ] Load testing for concurrent operations

### Manual Testing
- [ ] Deposit/withdrawal flow
- [ ] Order placement and fulfillment
- [ ] Cart order processing
- [ ] Error recovery procedures
- [ ] Statistics calculation

## Documentation Requirements

### API Documentation
- [x] Endpoint descriptions
- [x] Request/response formats
- [x] Error codes
- [x] Example usage
- [x] Authentication details

### Code Documentation
- [x] Module documentation
- [x] Function documentation
- [x] Type hints
- [x] Error handling
- [x] Configuration options

## Deployment Requirements

### Configuration
- [x] Environment variables
- [x] Database settings
- [x] Node connection details
- [x] Fee settings
- [x] Monitoring parameters

### Monitoring
- [x] Error logging
- [x] Transaction logging
- [x] Performance metrics
- [x] Balance tracking
- [x] System health checks 