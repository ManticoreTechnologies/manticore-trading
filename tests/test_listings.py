"""Tests for the listings module."""

import uuid
import pytest
import pytest_asyncio
from decimal import Decimal
from typing import Dict, Any

from database import init_db, close as close_db
from listings import (
    ListingManager, 
    ListingError,
    ListingNotFoundError,
    InvalidPriceError
)

# Test data
SELLER_ADDRESS = "EfwuhAAAWyXWYHZZ3rYm4rUuQCy3qVFiEU"
SAMPLE_LISTING = {
    "name": "Test NFT Collection",
    "description": "A test collection of NFTs",
    "image_ipfs_hash": "QmTest123",
    "prices": [
        {
            "asset_name": "TEST/NFT1",
            "price_evr": Decimal("100.0")
        },
        {
            "asset_name": "TEST/NFT2",
            "price_asset_name": "USDT",
            "price_asset_amount": Decimal("50.0")
        }
    ]
}

@pytest_asyncio.fixture
async def db_pool():
    """Create and return a database connection pool."""
    await init_db()
    yield
    await close_db()

@pytest_asyncio.fixture
async def listing_manager(db_pool):
    """Create and return a ListingManager instance."""
    return ListingManager()

@pytest_asyncio.fixture
async def sample_listing(listing_manager) -> Dict[str, Any]:
    """Create and return a sample listing."""
    listing = await listing_manager.create_listing(
        seller_address=SELLER_ADDRESS,
        **SAMPLE_LISTING
    )
    return listing

@pytest.mark.asyncio
async def test_create_listing(listing_manager):
    """Test creating a new listing."""
    # Create listing
    listing = await listing_manager.create_listing(
        seller_address=SELLER_ADDRESS,
        **SAMPLE_LISTING
    )
    
    # Verify base listing fields
    assert isinstance(listing["id"], uuid.UUID)
    assert listing["seller_address"] == SELLER_ADDRESS
    assert listing["name"] == SAMPLE_LISTING["name"]
    assert listing["description"] == SAMPLE_LISTING["description"]
    assert listing["image_ipfs_hash"] == SAMPLE_LISTING["image_ipfs_hash"]
    assert "created_at" in listing
    assert "updated_at" in listing
    
    # Verify prices
    assert len(listing["prices"]) == 2
    for i, price in enumerate(listing["prices"]):
        assert price["listing_id"] == listing["id"]
        assert price["asset_name"] == SAMPLE_LISTING["prices"][i]["asset_name"]
        if "price_evr" in SAMPLE_LISTING["prices"][i]:
            assert price["price_evr"] == SAMPLE_LISTING["prices"][i]["price_evr"]
        if "price_asset_name" in SAMPLE_LISTING["prices"][i]:
            assert price["price_asset_name"] == SAMPLE_LISTING["prices"][i]["price_asset_name"]
        if "price_asset_amount" in SAMPLE_LISTING["prices"][i]:
            assert price["price_asset_amount"] == SAMPLE_LISTING["prices"][i]["price_asset_amount"]
    
    # Verify addresses and balances
    assert len(listing["addresses"]) == 2
    assert len(listing["balances"]) == 2
    for address, balance in zip(listing["addresses"], listing["balances"]):
        assert address["listing_id"] == listing["id"]
        assert balance["listing_id"] == listing["id"]
        assert address["asset_name"] == balance["asset_name"]
        assert balance["confirmed_balance"] == 0
        assert balance["pending_balance"] == 0
        assert balance["deposit_address"] == address["deposit_address"]

@pytest.mark.asyncio
async def test_get_listing(listing_manager, sample_listing):
    """Test retrieving a listing by ID."""
    # Get listing
    listing = await listing_manager.get_listing(sample_listing["id"])
    
    # Verify it matches the sample
    assert listing["id"] == sample_listing["id"]
    assert listing["seller_address"] == sample_listing["seller_address"]
    assert listing["name"] == sample_listing["name"]
    assert listing["description"] == sample_listing["description"]
    assert listing["image_ipfs_hash"] == sample_listing["image_ipfs_hash"]
    
    # Verify related data is loaded
    assert len(listing["prices"]) == len(sample_listing["prices"])
    assert len(listing["addresses"]) == len(sample_listing["addresses"])
    assert len(listing["balances"]) == len(sample_listing["balances"])

@pytest.mark.asyncio
async def test_listing_not_found(listing_manager):
    """Test that getting a non-existent listing raises an error."""
    with pytest.raises(ListingNotFoundError):
        await listing_manager.get_listing(uuid.uuid4())

@pytest.mark.asyncio
async def test_update_listing(listing_manager, sample_listing):
    """Test updating a listing."""
    # Update fields
    updates = {
        "name": "Updated Name",
        "description": "Updated description",
        "image_ipfs_hash": "QmUpdated"
    }
    
    updated = await listing_manager.update_listing(sample_listing["id"], updates)
    
    # Verify updates
    assert updated["id"] == sample_listing["id"]
    assert updated["name"] == updates["name"]
    assert updated["description"] == updates["description"]
    assert updated["image_ipfs_hash"] == updates["image_ipfs_hash"]
    
    # Verify immutable fields haven't changed
    assert updated["seller_address"] == sample_listing["seller_address"]
    assert updated["created_at"] == sample_listing["created_at"]

@pytest.mark.asyncio
async def test_update_immutable_field(listing_manager, sample_listing):
    """Test that updating immutable fields raises an error."""
    with pytest.raises(ListingError):
        await listing_manager.update_listing(
            sample_listing["id"],
            {"seller_address": "NewAddress"}
        )

@pytest.mark.asyncio
async def test_listing_balances(listing_manager, sample_listing):
    """Test updating listing balances."""
    asset_name = sample_listing["prices"][0]["asset_name"]
    
    # Update balances
    updated = await listing_manager.update_listing_balance(
        listing_id=sample_listing["id"],
        asset_name=asset_name,
        confirmed_delta=Decimal("1.0"),
        pending_delta=Decimal("0.5"),
        tx_hash="0x123"
    )
    
    # Find the balance for our asset
    balance = next(
        b for b in updated["balances"] 
        if b["asset_name"] == asset_name
    )
    
    # Verify balance updates
    assert balance["confirmed_balance"] == Decimal("1.0")
    assert balance["pending_balance"] == Decimal("0.5")
    assert balance["last_confirmed_tx_hash"] == "0x123"
    assert balance["last_confirmed_tx_time"] is not None

@pytest.mark.asyncio
async def test_get_by_deposit_address(listing_manager, sample_listing):
    """Test retrieving a listing by deposit address."""
    # Get a deposit address from the sample listing
    deposit_address = sample_listing["addresses"][0]["deposit_address"]
    
    # Look up by deposit address
    listing = await listing_manager.get_listing_by_deposit_address(deposit_address)
    
    # Verify it's the same listing
    assert listing["id"] == sample_listing["id"]

@pytest.mark.asyncio
async def test_delete_listing(listing_manager, sample_listing):
    """Test deleting a listing."""
    # Delete the listing
    await listing_manager.delete_listing(sample_listing["id"])
    
    # Verify it's gone
    with pytest.raises(ListingNotFoundError):
        await listing_manager.get_listing(sample_listing["id"]) 