"""Tests for the monitor module's listing balance tracking."""

import pytest
import pytest_asyncio
from datetime import datetime
from uuid import uuid4
from unittest.mock import patch

from database import init_db, get_pool
from listings import ListingManager
from monitor import TransactionMonitor

@pytest_asyncio.fixture
async def db_pool():
    """Create and return a database connection pool."""
    await init_db()
    pool = await get_pool()  # Await the pool
    yield pool

@pytest_asyncio.fixture
async def listing_manager(db_pool):
    """Create and return a listing manager."""
    return ListingManager(db_pool)

@pytest_asyncio.fixture
async def monitor(db_pool):
    """Create and return a transaction monitor."""
    return TransactionMonitor(db_pool, min_confirmations=2)  # Lower confirmations for testing

@pytest_asyncio.fixture
async def test_listing(listing_manager):
    """Create a test listing with deposit addresses."""
    name = "Test Listing"
    description = "Test listing for balance tracking"
    seller_address = "EfGvJkSqvyv5LJ3NzwvJhpPcrZxk5gPYCz"
    image_ipfs_hash = "QmTest..."
    prices = [
        {
            'asset_name': 'EVR',
            'price_evr': 100
        },
        {
            'asset_name': 'TEST',
            'price_evr': 50
        }
    ]
    
    listing = await listing_manager.create_listing(
        name=name,
        description=description,
        seller_address=seller_address,
        image_ipfs_hash=image_ipfs_hash,
        prices=prices
    )
    return listing

@pytest.mark.asyncio
async def test_listing_balance_updates(db_pool, test_listing, monitor):
    """Test that listing balances are updated when transactions reach min_confirmations."""
    
    # Get deposit addresses
    async with db_pool.acquire() as conn:
        addresses = await conn.fetch(
            'SELECT deposit_address, asset_name FROM listing_addresses WHERE listing_id = $1',
            test_listing['id']
        )
        
        # Insert test transaction for EVR deposit
        evr_address = next(addr for addr in addresses if addr['asset_name'] == 'EVR')
        tx_hash = '0x' + '1' * 64  # Dummy transaction hash
        
        # Insert initial transaction with 0 confirmations
        await conn.execute(
            '''
            INSERT INTO transaction_entries (
                tx_hash, address, entry_type, asset_name,
                amount, confirmations, time, trusted
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ''',
            tx_hash,
            evr_address['deposit_address'],
            'receive',
            'EVR',
            50.0,  # Amount
            0,     # Initial confirmations
            datetime.now(),
            True
        )
        
        # Mock RPC responses
        mock_wallet_tx = {
            'details': [{
                'address': evr_address['deposit_address'],
                'category': 'receive',
                'amount': 50.0,
                'vout': 0
            }],
            'trusted': True,
            'bip125-replaceable': 'no',
            'fee': 0.0001
        }
        
        mock_raw_tx = {
            'confirmations': 0,
            'time': int(datetime.now().timestamp())
        }
        
        # Patch RPC calls for transaction processing
        with patch('monitor.gettransaction', return_value=mock_wallet_tx), \
             patch('monitor.getrawtransaction', return_value=mock_raw_tx):
            # Verify initial pending balance
            await monitor.process_new_transaction(tx_hash)
        
        # Check pending balance was updated
        row = await conn.fetchrow(
            '''
            SELECT pending_balance, confirmed_balance 
            FROM listing_balances 
            WHERE listing_id = $1 AND asset_name = $2
            ''',
            test_listing['id'],
            'EVR'
        )
        assert row['pending_balance'] == 50.0
        assert row['confirmed_balance'] == 0.0
        
        # Update confirmations to trigger confirmation logic
        await conn.execute(
            'UPDATE transaction_entries SET confirmations = $1 WHERE tx_hash = $2',
            monitor.min_confirmations,
            tx_hash
        )
        
        # Mock block data for processing
        mock_block = {
            'hash': '0x' + '2' * 64,
            'height': 1000,
            'time': int(datetime.now().timestamp())
        }
        
        # Process a block to trigger balance updates
        with patch('monitor.getblock', return_value=mock_block):
            await monitor.process_new_block(mock_block['hash'])
        
        # Verify balances after confirmation
        row = await conn.fetchrow(
            '''
            SELECT pending_balance, confirmed_balance 
            FROM listing_balances 
            WHERE listing_id = $1 AND asset_name = $2
            ''',
            test_listing['id'],
            'EVR'
        )
        assert row['pending_balance'] == 0.0
        assert row['confirmed_balance'] == 50.0 