"""Worker to monitor and process featured listing payments."""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
import traceback

from database import get_pool
from rpc import client as rpc_client

# Configure logging
logger = logging.getLogger(__name__)

async def process_pending_payments():
    """Check for and process pending featured listing payments."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Get pending payments
            pending_payments = await conn.fetch(
                '''
                SELECT id, payment_address, amount_evr, listing_id,
                       duration_days, priority_level
                FROM featured_listing_payments
                WHERE status = 'pending'
                AND created_at > NOW() - INTERVAL '24 hours'
                '''
            )
            
            logger.info(f"Found {len(pending_payments)} pending payments to process")
            
            for payment in pending_payments:
                try:
                    logger.info(f"Processing payment {payment['id']} for address {payment['payment_address']}")
                    
                    # Check payment address balance
                    try:
                        balance = Decimal(str(rpc_client.getreceivedbyaddress(payment['payment_address'])))
                        logger.info(f"Address {payment['payment_address']} has balance: {balance} EVR")
                    except Exception as e:
                        logger.error(f"Failed to get balance for {payment['payment_address']}: {str(e)}")
                        continue
                    
                    if balance >= payment['amount_evr']:
                        logger.info(f"Sufficient balance found ({balance} >= {payment['amount_evr']})")
                        
                        # Get transaction details safely
                        try:
                            txns = rpc_client.listtransactions("*", 100)  # Get more transactions and search all accounts
                            logger.info(f"Found {len(txns)} recent transactions to search through")
                        except Exception as e:
                            logger.error(f"Failed to get transactions: {str(e)}")
                            continue
                            
                        tx_hash = None
                        
                        # Find the matching transaction
                        for tx in txns:
                            try:
                                if (tx.get('category') == 'receive' and 
                                    tx.get('address') == payment['payment_address']):
                                    # Use approximate decimal comparison due to potential rounding
                                    tx_amount = Decimal(str(tx.get('amount', 0)))
                                    if abs(tx_amount - payment['amount_evr']) < Decimal('0.00000001'):
                                        tx_hash = tx['txid']
                                        logger.info(f"Found matching transaction: {tx_hash}")
                                        break
                            except Exception as e:
                                logger.warning(f"Error checking transaction: {str(e)}")
                                continue
                                
                        if not tx_hash:
                            logger.warning(f"Payment received but transaction not found for payment {payment['id']}")
                            continue
                        
                        try:
                            # Payment received - update payment status
                            tx = await conn.fetchrow(
                                '''
                                UPDATE featured_listing_payments
                                SET status = 'completed',
                                    paid_at = NOW(),
                                    tx_hash = $1
                                WHERE id = $2
                                RETURNING paid_at
                                ''',
                                tx_hash,
                                payment['id']
                            )
                            
                            if not tx:
                                logger.error(f"Failed to update payment status for {payment['id']}")
                                continue
                                
                            # Create featured listing entry
                            await conn.execute(
                                '''
                                INSERT INTO featured_listings (
                                    listing_id,
                                    featured_at,
                                    featured_by,
                                    priority,
                                    expires_at
                                ) VALUES ($1, $2, $3, $4, $5)
                                ON CONFLICT (listing_id) DO UPDATE
                                SET featured_at = EXCLUDED.featured_at,
                                    featured_by = EXCLUDED.featured_by,
                                    priority = EXCLUDED.priority,
                                    expires_at = EXCLUDED.expires_at
                                ''',
                                payment['listing_id'],
                                tx['paid_at'],
                                payment['payment_address'],
                                payment['priority_level'],
                                tx['paid_at'] + timedelta(days=payment['duration_days'])
                            )
                            
                            logger.info(f"Featured listing payment {payment['id']} processed successfully")
                            
                        except Exception as e:
                            logger.error(f"Database error processing payment {payment['id']}: {str(e)}")
                            logger.error(traceback.format_exc())
                            continue
                    else:
                        logger.info(f"Insufficient balance for payment {payment['id']}: {balance} < {payment['amount_evr']}")
                        
                except Exception as e:
                    logger.error(f"Error processing payment {payment['id']}: {str(e)}")
                    logger.error(traceback.format_exc())
                    continue
            
            # Cancel expired pending payments
            expired = await conn.execute(
                '''
                UPDATE featured_listing_payments
                SET status = 'expired'
                WHERE status = 'pending'
                AND created_at < NOW() - INTERVAL '24 hours'
                '''
            )
            if expired != '0':
                logger.info(f"Expired {expired} pending payments")
            
    except Exception as e:
        logger.error(f"Error in process_pending_payments: {str(e)}")
        logger.error(traceback.format_exc())

async def cleanup_expired_listings():
    """Remove expired featured listings."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                '''
                DELETE FROM featured_listings
                WHERE expires_at < NOW()
                '''
            )
            if result != '0':
                logger.info(f"Cleaned up {result} expired featured listings")
            
    except Exception as e:
        logger.error(f"Error in cleanup_expired_listings: {str(e)}")
        logger.error(traceback.format_exc())

async def run_worker():
    """Main worker loop."""
    logger.info("Featured payments worker starting up")
    while True:
        try:
            await process_pending_payments()
            await cleanup_expired_listings()
            
        except Exception as e:
            logger.error(f"Error in worker loop: {str(e)}")
            logger.error(traceback.format_exc())
            
        finally:
            # Run every minute
            await asyncio.sleep(60)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run_worker())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close() 