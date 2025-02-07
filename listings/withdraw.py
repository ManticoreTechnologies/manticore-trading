"""Handle withdrawals from listing addresses."""

import logging
from typing import Dict, Any
from decimal import Decimal
from uuid import UUID
from datetime import datetime

from database import get_pool
from rpc import transferfromaddress, RPCError

logger = logging.getLogger(__name__)

class WithdrawError(Exception):
    """Base exception for withdrawal errors."""
    pass

async def withdraw(
    listing_id: UUID,
    asset_name: str,
    amount: Decimal,
    to_address: str
) -> Dict[str, Any]:
    """Withdraw assets from a listing.
    
    Args:
        listing_id: UUID of the listing
        asset_name: Name of asset to withdraw
        amount: Amount to withdraw
        to_address: Address to send assets to
        
    Returns:
        Dict containing:
            - tx_hash: Transaction hash
            - amount: Amount withdrawn
            - asset_name: Asset name
            - from_address: Address withdrawn from
            - to_address: Address sent to
            
    Raises:
        WithdrawError: If withdrawal fails
        RPCError: If RPC call fails
    """
    try:
        pool = await get_pool()
        
        async with pool.acquire() as conn:
            # Get listing details and verify ownership
            listing = await conn.fetchrow(
                '''
                SELECT 
                    l.*,
                    lb.confirmed_balance,
                    lb.pending_balance,
                    lb.units
                FROM listings l
                JOIN listing_balances lb ON lb.listing_id = l.id
                WHERE l.id = $1 AND lb.asset_name = $2
                ''',
                listing_id,
                asset_name
            )
            
            if not listing:
                raise WithdrawError(f"Listing {listing_id} not found")
                
            # Check balance
            confirmed_balance = listing['confirmed_balance'] or Decimal('0')
            if confirmed_balance < amount:
                raise WithdrawError(
                    f"Insufficient balance for {asset_name}: "
                    f"available {confirmed_balance}, requested {amount}"
                )
            
            # Determine which address to withdraw from based on asset
            from_address = listing['deposit_address']
            
            # Convert amount to float for RPC
            amount_float = float(amount)
            
            # First deduct the balance
            await conn.execute(
                '''
                UPDATE listing_balances
                SET 
                    confirmed_balance = confirmed_balance - $3,
                    updated_at = now()
                WHERE listing_id = $1 AND asset_name = $2
                ''',
                listing_id,
                asset_name,
                amount
            )
            
            # Now try the withdrawal
            try:
                # Execute withdrawal using transferfromaddress
                tx_hash = transferfromaddress(
                    asset_name,      # Asset name
                    from_address,    # From address
                    amount_float,    # Amount
                    to_address,      # To address
                    "",             # Message
                    0,              # Expire time
                    from_address,   # EVR change address
                    from_address    # Asset change address
                )
                
                if isinstance(tx_hash, list):
                    tx_hash = tx_hash[0]
                    
                logger.info(
                    f"Withdrawal successful: {amount} {asset_name} from listing {listing_id} "
                    f"(tx: {tx_hash})"
                )
                
                # Record outgoing transaction
                await conn.execute(
                    '''
                    INSERT INTO transaction_entries (
                        tx_hash, address, entry_type, asset_name,
                        amount, fee, confirmations, time,
                        asset_type, asset_message, trusted,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, now(), $8, $9, $10, now(), now())
                    ''',
                    tx_hash,                    # tx_hash
                    from_address,               # address
                    'withdraw',                 # entry_type
                    asset_name,                 # asset_name
                    amount,                     # amount
                    Decimal('0'),               # fee
                    0,                          # confirmations
                    'withdraw',                 # asset_type
                    '',                         # asset_message
                    True                        # trusted
                )
                
                return {
                    'tx_hash': tx_hash,
                    'amount': str(amount),
                    'asset_name': asset_name,
                    'from_address': from_address,
                    'to_address': to_address
                }
                
            except Exception as e:
                # If the withdrawal fails, restore the balance
                await conn.execute(
                    '''
                    UPDATE listing_balances
                    SET 
                        confirmed_balance = confirmed_balance + $3,
                        updated_at = now()
                    WHERE listing_id = $1 AND asset_name = $2
                    ''',
                    listing_id,
                    asset_name,
                    amount
                )
                raise
            
    except RPCError as e:
        logger.error(f"RPC error during withdrawal: {e}")
        raise
    except WithdrawError:
        raise
    except Exception as e:
        logger.error(f"Error processing withdrawal: {e}")
        raise WithdrawError(f"Withdrawal failed: {str(e)}") 