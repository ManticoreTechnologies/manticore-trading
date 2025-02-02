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
                {'name': 'tags', 'type': 'TEXT'},
                {'name': 'description', 'type': 'TEXT'},
                {'name': 'image_ipfs_hash', 'type': 'TEXT'},
                {'name': 'status', 'type': 'TEXT', 'default': "'active'"},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_listings_seller', 'columns': ['seller_address']},
                {'name': 'idx_listings_address', 'columns': ['listing_address'], 'unique': True},
                {'name': 'idx_listings_deposit', 'columns': ['deposit_address'], 'unique': True}
            ]
        },
        {
            'name': 'listing_prices',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'price_evr', 'type': 'DECIMAL'},
                {'name': 'ipfs_hash', 'type': 'TEXT'},
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
            'name': 'orders',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'buyer_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'payment_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'status', 'type': 'TEXT', 'nullable': False, 'default': "'pending'"},
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
                {'name': 'idx_orders_payment_address', 'columns': ['payment_address'], 'unique': True}
            ],
            'checks': [
                {'name': 'valid_order_status', 'expression': "status IN ('pending', 'partially_paid', 'paid', 'confirming', 'fulfilling', 'completed', 'cancelled', 'refunded')"}
            ]
        },
        {
            'name': 'order_items',
            'columns': [
                {'name': 'order_id', 'type': 'UUID', 'nullable': False},
                {'name': 'asset_name', 'type': 'TEXT', 'nullable': False},
                {'name': 'amount', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'price_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'fee_evr', 'type': 'DECIMAL', 'nullable': False},
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
                {'name': 'positive_price', 'expression': "price_evr > 0"},
                {'name': 'positive_fee', 'expression': "fee_evr >= 0"}
            ]
        },
        {
            'name': 'order_balances',
            'columns': [
                {'name': 'order_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'confirmed_balance', 'type': 'DECIMAL', 'nullable': False, 'default': '0'},
                {'name': 'pending_balance', 'type': 'DECIMAL', 'nullable': False, 'default': '0'},
                {'name': 'last_confirmed_tx_hash', 'type': 'TEXT'},
                {'name': 'last_confirmed_tx_time', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['order_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['order_id'], 'references': 'orders(id)'}
            ]
        },
        {
            'name': 'sale_history',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'order_id', 'type': 'UUID', 'nullable': False},
                {'name': 'asset_name', 'type': 'TEXT', 'nullable': False},
                {'name': 'amount', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'price_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'seller_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'buyer_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'sale_time', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_sales_listing', 'columns': ['listing_id']},
                {'name': 'idx_sales_asset', 'columns': ['asset_name']},
                {'name': 'idx_sales_time', 'columns': ['sale_time']},
                {'name': 'idx_sales_price', 'columns': ['price_evr']},
                {'name': 'idx_sales_asset_time', 'columns': ['asset_name', 'sale_time']},
                {'name': 'idx_sales_listing_time', 'columns': ['listing_id', 'sale_time']},
                {'name': 'idx_sales_asset_listing', 'columns': ['asset_name', 'listing_id']}
            ],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'},
                {'columns': ['order_id'], 'references': 'orders(id)'}
            ]
        }
    ],
    'triggers': [
        {
            'name': 'update_listing_balance_trigger',
            'function_name': 'update_listing_balance',
            'table': 'transaction_entries',
            'timing': 'AFTER',
            'events': ['INSERT', 'UPDATE OF confirmations'],
            'level': 'ROW',
            'function_body': '''
                BEGIN
                    -- Handle both new transactions and confirmation updates
                    IF (NEW).entry_type = 'receive' THEN
                        -- For new transactions, add to pending balance
                        IF TG_OP = 'INSERT' THEN
                            INSERT INTO listing_balances (
                                listing_id, asset_name, confirmed_balance, pending_balance,
                                last_confirmed_tx_hash, last_confirmed_tx_time, created_at, updated_at
                            )
                            SELECT 
                                l.id,
                                (NEW).asset_name,
                                0,
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
                                END,
                                NULL,
                                NULL,
                                now(),
                                now()
                            FROM listings l
                            WHERE l.deposit_address = (NEW).address
                            ON CONFLICT (listing_id, asset_name) DO UPDATE
                            SET 
                                pending_balance = listing_balances.pending_balance + (
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
                                updated_at = now();

                        -- For confirmation updates
                        ELSIF TG_OP = 'UPDATE' AND (NEW).confirmations >= 2 AND ((OLD).confirmations IS NULL OR (OLD).confirmations < 2) THEN
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
                    -- Handle both new transactions and confirmation updates
                    IF (NEW).entry_type = 'receive' THEN
                        -- For new transactions, add to pending balance
                        IF TG_OP = 'INSERT' THEN
                            INSERT INTO order_balances (
                                order_id, asset_name, confirmed_balance, pending_balance,
                                last_confirmed_tx_hash, last_confirmed_tx_time, created_at, updated_at
                            )
                            SELECT 
                                o.id,
                                (NEW).asset_name,
                                0,
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
                                END,
                                NULL,
                                NULL,
                                now(),
                                now()
                            FROM orders o
                            WHERE o.payment_address = (NEW).address
                            ON CONFLICT (order_id, asset_name) DO UPDATE
                            SET 
                                pending_balance = order_balances.pending_balance + (
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
                                updated_at = now();

                        -- For confirmation updates
                        ELSIF TG_OP = 'UPDATE' AND (NEW).confirmations >= 2 AND ((OLD).confirmations IS NULL OR (OLD).confirmations < 2) THEN
                            UPDATE order_balances ob
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
                            FROM orders o
                            WHERE o.payment_address = (NEW).address
                            AND o.id = ob.order_id
                            AND ob.asset_name = (NEW).asset_name;
                        END IF;
                    END IF;
                    
                    RETURN NEW;
                END;
            '''
        },
        {
            'name': 'update_order_status_trigger',
            'function_name': 'update_order_status',
            'table': 'order_balances',
            'timing': 'AFTER',
            'events': ['INSERT', 'UPDATE OF pending_balance, confirmed_balance'],
            'level': 'ROW',
            'function_body': '''
                DECLARE total_payment DECIMAL;
                DECLARE current_status TEXT;
                DECLARE new_status TEXT;
                BEGIN
                    -- Only process EVR balance changes
                    IF (NEW).asset_name = 'EVR' THEN
                        -- Get the total payment required and current status
                        SELECT 
                            COALESCE(SUM(price_evr + fee_evr), 0),
                            o.status 
                        INTO total_payment, current_status
                        FROM orders o 
                        LEFT JOIN order_items oi ON oi.order_id = o.id
                        WHERE o.id = (NEW).order_id
                        GROUP BY o.id, o.status;

                        -- Determine new status based on balances
                        new_status := CASE
                            -- Fully paid
                            WHEN (NEW).confirmed_balance >= total_payment THEN 'paid'
                            -- Partially paid with pending
                            WHEN (NEW).confirmed_balance > 0 AND (NEW).pending_balance > 0 THEN 'confirming'
                            -- Partially paid
                            WHEN (NEW).confirmed_balance > 0 THEN 'partially_paid'
                            -- Only pending payments
                            WHEN (NEW).pending_balance > 0 THEN 'confirming'
                            -- No payments
                            ELSE 'pending'
                        END;

                        -- Update order status if changed
                        IF new_status != current_status THEN
                            UPDATE orders
                            SET status = new_status,
                                updated_at = now()
                            WHERE id = (NEW).order_id;
                        END IF;
                    END IF;

                    RETURN NEW;
                END;
            '''
        },
        {
            'name': 'record_sale_on_order_paid_trigger',
            'function_name': 'record_sale_on_order_paid',
            'table': 'orders',
            'timing': 'AFTER',
            'events': ['UPDATE OF status'],
            'level': 'ROW',
            'function_body': '''
                BEGIN
                    -- Only process when status changes to 'paid'
                    IF (NEW).status = 'paid' AND (OLD).status != 'paid' THEN
                        -- Insert sale records for each item in the order
                        INSERT INTO sale_history (
                            listing_id,
                            order_id,
                            asset_name,
                            amount,
                            price_evr,
                            seller_address,
                            buyer_address,
                            sale_time
                        )
                        SELECT 
                            o.listing_id,
                            o.id as order_id,
                            oi.asset_name,
                            oi.amount,
                            oi.price_evr,
                            l.seller_address,
                            o.buyer_address,
                            o.updated_at as sale_time
                        FROM orders o
                        JOIN order_items oi ON oi.order_id = o.id
                        JOIN listings l ON l.id = o.listing_id
                        WHERE o.id = (NEW).id;
                    END IF;
                    
                    RETURN NEW;
                END;
            '''
        }
    ]
}