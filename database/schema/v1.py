"""Schema v1 - Initial schema.

This version creates all core tables including blocks, transactions, and listings.
The listings table includes the listing_address field and automatic balance updates via trigger.
Compatible with CockroachDB Cloud.
"""

schema = {
    'version': 1,
    'tables': [
        {
            'name': 'blocks',
            'columns': [
                {'name': 'hash', 'type': 'TEXT', 'primary_key': True},
                {'name': 'height', 'type': 'INT8', 'nullable': False},
                {'name': 'timestamp', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_blocks_height', 'columns': ['height'], 'unique': True}
            ]
        },
        {
            'name': 'transaction_entries',
            'columns': [
                {'name': 'tx_hash', 'type': 'TEXT'},
                {'name': 'address', 'type': 'TEXT'},
                {'name': 'entry_type', 'type': 'TEXT'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'amount', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'fee', 'type': 'DECIMAL'},
                {'name': 'confirmations', 'type': 'INT8', 'default': '0'},
                {'name': 'time', 'type': 'TIMESTAMP'},
                {'name': 'asset_type', 'type': 'TEXT'},
                {'name': 'asset_message', 'type': 'TEXT'},
                {'name': 'vout', 'type': 'INT8'},
                {'name': 'trusted', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'bip125_replaceable', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'abandoned', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['tx_hash', 'address', 'entry_type', 'asset_name'],
            'indexes': [
                {'name': 'idx_tx_entries_address', 'columns': ['address']},
                {'name': 'idx_tx_entries_asset', 'columns': ['asset_name']},
                {'name': 'idx_tx_entries_time', 'columns': ['time']},
                {'name': 'idx_tx_entries_confirmations', 'columns': ['confirmations'], 'where': "entry_type = 'receive'"}
            ]
        },
        {
            'name': 'listings',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'seller_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'listing_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'deposit_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'name', 'type': 'TEXT', 'nullable': False},
                {'name': 'description', 'type': 'TEXT'},
                {'name': 'image_ipfs_hash', 'type': 'TEXT'},
                {'name': 'status', 'type': 'TEXT', 'default': "'active'"},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_listings_seller', 'columns': ['seller_address']},
                {'name': 'idx_listings_address', 'columns': ['listing_address'], 'unique': True},
                {'name': 'idx_listings_deposit', 'columns': ['deposit_address'], 'unique': True}  # Add index for deposit_address
            ]
        },
        {
            'name': 'listing_prices',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'price_evr', 'type': 'DECIMAL'},
                {'name': 'price_asset_name', 'type': 'TEXT'},
                {'name': 'price_asset_amount', 'type': 'DECIMAL'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ]
        },
        {
            'name': 'listing_balances',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'confirmed_balance', 'type': 'DECIMAL', 'nullable': False, 'default': '0'},
                {'name': 'pending_balance', 'type': 'DECIMAL', 'nullable': False, 'default': '0'},
                {'name': 'last_confirmed_tx_hash', 'type': 'TEXT'},
                {'name': 'last_confirmed_tx_time', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ]
        },
        {
            'name': 'archived_orders',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True},
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'buyer_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'status', 'type': 'TEXT', 'nullable': False},
                {'name': 'total_price_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'fee_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'payment_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'confirmed_paid_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'pending_paid_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'last_payment_tx_hash', 'type': 'TEXT'},
                {'name': 'last_payment_time', 'type': 'TIMESTAMP'},
                {'name': 'expires_at', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'archived_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_archived_orders_listing', 'columns': ['listing_id']},
                {'name': 'idx_archived_orders_created', 'columns': ['created_at']}
            ]
        },
        {
            'name': 'archived_order_items',
            'columns': [
                {'name': 'order_id', 'type': 'UUID', 'nullable': False},
                {'name': 'asset_name', 'type': 'TEXT', 'nullable': False},
                {'name': 'amount', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'price_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'fulfillment_tx_hash', 'type': 'TEXT'},
                {'name': 'fulfillment_time', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'archived_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['order_id', 'asset_name'],
            'indexes': [
                {'name': 'idx_archived_order_items_created', 'columns': ['created_at']}
            ]
        },
        {
            'name': 'orders',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'buyer_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'status', 'type': 'TEXT', 'nullable': False, 'default': "'pending'"},
                {'name': 'total_price_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'fee_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'payment_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'confirmed_paid_evr', 'type': 'DECIMAL', 'nullable': False, 'default': '0'},
                {'name': 'pending_paid_evr', 'type': 'DECIMAL', 'nullable': False, 'default': '0'},
                {'name': 'last_payment_tx_hash', 'type': 'TEXT'},
                {'name': 'last_payment_time', 'type': 'TIMESTAMP'},
                {'name': 'expires_at', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'idx_orders_listing', 'columns': ['listing_id']},
                {'name': 'idx_orders_buyer', 'columns': ['buyer_address']},
                {'name': 'idx_orders_status', 'columns': ['status']},
                {'name': 'idx_orders_payment_address', 'columns': ['payment_address'], 'unique': True},
                {'name': 'idx_orders_expires_at', 'columns': ['expires_at']}
            ],
            'checks': [
                {'name': 'valid_order_status', 'expression': "status IN ('pending', 'partially_paid', 'paid', 'confirming', 'fulfilling', 'completed', 'cancelled', 'refunded', 'expired')"},
                {'name': 'positive_total_price', 'expression': "total_price_evr > 0"},
                {'name': 'positive_fee', 'expression': "fee_evr > 0"}
            ]
        },
        {
            'name': 'order_items',
            'columns': [
                {'name': 'order_id', 'type': 'UUID', 'nullable': False},
                {'name': 'asset_name', 'type': 'TEXT', 'nullable': False},
                {'name': 'amount', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'price_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'fulfillment_tx_hash', 'type': 'TEXT'},
                {'name': 'fulfillment_time', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['order_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['order_id'], 'references': 'orders(id)'}
            ],
            'checks': [
                {'name': 'positive_amount', 'expression': "amount > 0"},
                {'name': 'positive_price', 'expression': "price_evr > 0"}
            ]
        }
    ],
    'triggers': [
        {
            'name': 'update_listing_balance_trigger',
            'function_name': 'update_listing_balance',
            'table': 'transaction_entries',
            'timing': 'AFTER',
            'events': ['UPDATE OF confirmations'],
            'level': 'ROW',
            'function_body': '''
                BEGIN
                    -- Only handle receive transactions that reach min_confirmations
                    IF (NEW).entry_type = 'receive' AND (NEW).confirmations >= 2 AND 
                       ((OLD).confirmations IS NULL OR (OLD).confirmations < 2) THEN
                        
                        -- Update listing balances for this transaction
                        UPDATE listing_balances lb
                        SET 
                            confirmed_balance = confirmed_balance + (
                                CASE 
                                    WHEN (
                                        SELECT COUNT(*) 
                                        FROM transaction_entries 
                                        WHERE tx_hash = (NEW).tx_hash 
                                        AND asset_name = (NEW).asset_name 
                                        AND entry_type = 'receive'
                                    ) > 1 
                                    THEN (NEW).amount / (
                                        SELECT COUNT(*) 
                                        FROM transaction_entries 
                                        WHERE tx_hash = (NEW).tx_hash 
                                        AND asset_name = (NEW).asset_name 
                                        AND entry_type = 'receive'
                                    )
                                    ELSE (NEW).amount
                                END
                            ),
                            pending_balance = GREATEST(0, pending_balance - (
                                CASE 
                                    WHEN (
                                        SELECT COUNT(*) 
                                        FROM transaction_entries 
                                        WHERE tx_hash = (NEW).tx_hash 
                                        AND asset_name = (NEW).asset_name 
                                        AND entry_type = 'receive'
                                    ) > 1 
                                    THEN (NEW).amount / (
                                        SELECT COUNT(*) 
                                        FROM transaction_entries 
                                        WHERE tx_hash = (NEW).tx_hash 
                                        AND asset_name = (NEW).asset_name 
                                        AND entry_type = 'receive'
                                    )
                                    ELSE (NEW).amount
                                END
                            )),
                            last_confirmed_tx_hash = (NEW).tx_hash,
                            last_confirmed_tx_time = (NEW).time,
                            updated_at = now()
                        FROM listings l
                        WHERE l.deposit_address = (NEW).address
                        AND l.id = lb.listing_id
                        AND lb.asset_name = (NEW).asset_name;
                    END IF;
                    
                    RETURN NEW;
                END;
            '''
        },
        {
            'name': 'update_order_balance_trigger',
            'function_name': 'update_order_balance',
            'table': 'transaction_entries',
            'timing': 'AFTER',
            'events': ['INSERT', 'UPDATE OF confirmations'],
            'level': 'ROW',
            'function_body': '''
                BEGIN
                    -- Only handle receive transactions to order payment addresses
                    IF (NEW).entry_type = 'receive' AND (NEW).asset_name = 'EVR' THEN
                        -- Update order payment tracking
                        UPDATE orders
                        SET 
                            confirmed_paid_evr = CASE 
                                WHEN (NEW).confirmations >= 6 THEN confirmed_paid_evr + (NEW).amount
                                ELSE confirmed_paid_evr
                            END,
                            pending_paid_evr = CASE 
                                WHEN (NEW).confirmations >= 6 THEN pending_paid_evr - (NEW).amount
                                ELSE pending_paid_evr + (NEW).amount
                            END,
                            last_payment_tx_hash = (NEW).tx_hash,
                            last_payment_time = (NEW).time,
                            status = CASE
                                WHEN confirmed_paid_evr + CASE 
                                    WHEN (NEW).confirmations >= 6 THEN (NEW).amount
                                    ELSE 0
                                END >= total_price_evr THEN 'paid'
                                WHEN pending_paid_evr + CASE
                                    WHEN (NEW).confirmations >= 6 THEN -1 * (NEW).amount
                                    ELSE (NEW).amount
                                END > 0 THEN 'partially_paid'
                                ELSE status
                            END,
                            updated_at = now()
                        WHERE payment_address = (NEW).address;
                    END IF;
                    
                    RETURN NEW;
                END;
            '''
        },
        {
            'name': 'archive_expired_orders_trigger',
            'function_name': 'archive_expired_orders',
            'table': 'orders',
            'timing': 'BEFORE',
            'events': ['DELETE'],
            'level': 'ROW',
            'function_body': '''
                BEGIN
                    -- First return balances to confirmed state
                    UPDATE listing_balances lb
                    SET 
                        confirmed_balance = confirmed_balance + oi.amount,
                        pending_balance = pending_balance - oi.amount,
                        updated_at = now()
                    FROM order_items oi
                    WHERE oi.order_id = (OLD).id
                    AND lb.listing_id = (OLD).listing_id
                    AND lb.asset_name = oi.asset_name;

                    -- Archive the order items
                    INSERT INTO archived_order_items
                    SELECT 
                        order_id,
                        asset_name,
                        amount,
                        price_evr,
                        fulfillment_tx_hash,
                        fulfillment_time,
                        created_at,
                        updated_at,
                        now() as archived_at
                    FROM order_items
                    WHERE order_id = (OLD).id;

                    -- Delete the order items
                    DELETE FROM order_items WHERE order_id = (OLD).id;

                    -- Archive the order
                    INSERT INTO archived_orders
                    SELECT 
                        id,
                        listing_id,
                        buyer_address,
                        'expired',  -- Force status to expired
                        total_price_evr,
                        fee_evr,
                        payment_address,
                        confirmed_paid_evr,
                        pending_paid_evr,
                        last_payment_tx_hash,
                        last_payment_time,
                        expires_at,
                        created_at,
                        updated_at,
                        now() as archived_at
                    FROM orders
                    WHERE id = (OLD).id;

                    RETURN OLD;
                END;
            '''
        }
    ]
}