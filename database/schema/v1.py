"""Schema v1 - Initial database schema.

This version includes tables for:
- Listings and prices
- Orders and balances
- Transaction tracking
- Analytics and metrics
- Rate limiting and system monitoring
- Authentication and sessions
"""

schema = {
    'version': 1,
    'tables': [
        {
            'name': 'listings',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'seller_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'listing_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'deposit_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'payout_address', 'type': 'TEXT'},
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
                {'name': 'price_asset_name', 'type': 'TEXT'},
                {'name': 'price_asset_amount', 'type': 'DECIMAL'},
                {'name': 'ipfs_hash', 'type': 'TEXT'},
                {'name': 'units', 'type': 'INT8', 'default': '8'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'idx_prices_asset', 'columns': ['asset_name']}
            ]
        },
        {
            'name': 'listing_balances',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'confirmed_balance', 'type': 'DECIMAL', 'default': '0'},
                {'name': 'pending_balance', 'type': 'DECIMAL', 'default': '0'},
                {'name': 'units', 'type': 'INT8', 'default': '8'},
                {'name': 'last_confirmed_tx_hash', 'type': 'TEXT'},
                {'name': 'last_confirmed_tx_time', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'idx_balances_asset', 'columns': ['asset_name']}
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
                {'name': 'payout_tx_hash', 'type': 'TEXT'},
                {'name': 'payout_error', 'type': 'TEXT'},
                {'name': 'payout_attempts', 'type': 'INT8', 'default': '0'},
                {'name': 'last_payout_attempt', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'idx_orders_listing', 'columns': ['listing_id']},
                {'name': 'idx_orders_buyer', 'columns': ['buyer_address']},
                {'name': 'idx_orders_payment', 'columns': ['payment_address'], 'unique': True},
                {'name': 'idx_orders_status', 'columns': ['status']}
            ]
        },
        {
            'name': 'order_items',
            'columns': [
                {'name': 'order_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'amount', 'type': 'DECIMAL'},
                {'name': 'price_evr', 'type': 'DECIMAL'},
                {'name': 'price_asset_name', 'type': 'TEXT'},
                {'name': 'price_asset_amount', 'type': 'DECIMAL'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['order_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['order_id'], 'references': 'orders(id)'}
            ]
        },
        {
            'name': 'order_balances',
            'columns': [
                {'name': 'order_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'confirmed_balance', 'type': 'DECIMAL', 'default': '0'},
                {'name': 'pending_balance', 'type': 'DECIMAL', 'default': '0'},
                {'name': 'required_amount', 'type': 'DECIMAL', 'default': '0'},
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
            'name': 'cart_orders',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'buyer_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'payment_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'status', 'type': 'TEXT', 'nullable': False, 'default': "'pending'"},
                {'name': 'payout_tx_hash', 'type': 'TEXT'},
                {'name': 'payout_error', 'type': 'TEXT'},
                {'name': 'payout_attempts', 'type': 'INT8', 'default': '0'},
                {'name': 'last_payout_attempt', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_cart_orders_buyer', 'columns': ['buyer_address']},
                {'name': 'idx_cart_orders_payment', 'columns': ['payment_address'], 'unique': True},
                {'name': 'idx_cart_orders_status', 'columns': ['status']}
            ]
        },
        {
            'name': 'cart_order_items',
            'columns': [
                {'name': 'cart_order_id', 'type': 'UUID'},
                {'name': 'listing_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'amount', 'type': 'DECIMAL'},
                {'name': 'price_evr', 'type': 'DECIMAL'},
                {'name': 'fee_evr', 'type': 'DECIMAL', 'default': '0'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['cart_order_id', 'listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['cart_order_id'], 'references': 'cart_orders(id)'},
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ]
        },
        {
            'name': 'cart_order_balances',
            'columns': [
                {'name': 'cart_order_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'confirmed_balance', 'type': 'DECIMAL', 'default': '0'},
                {'name': 'pending_balance', 'type': 'DECIMAL', 'default': '0'},
                {'name': 'required_amount', 'type': 'DECIMAL', 'default': '0'},
                {'name': 'last_confirmed_tx_hash', 'type': 'TEXT'},
                {'name': 'last_confirmed_tx_time', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['cart_order_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['cart_order_id'], 'references': 'cart_orders(id)'}
            ]
        },
        {
            'name': 'transaction_entries',
            'columns': [
                {'name': 'tx_hash', 'type': 'TEXT'},
                {'name': 'address', 'type': 'TEXT'},
                {'name': 'entry_type', 'type': 'TEXT'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'amount', 'type': 'DECIMAL'},
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
            'name': 'blocks',
            'columns': [
                {'name': 'hash', 'type': 'TEXT', 'primary_key': True},
                {'name': 'height', 'type': 'INT8', 'nullable': False},
                {'name': 'timestamp', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_blocks_height', 'columns': ['height'], 'unique': True},
                {'name': 'idx_blocks_time', 'columns': ['timestamp']}
            ]
        },
        {
            'name': 'featured_listings',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID', 'primary_key': True},
                {'name': 'featured_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'featured_by', 'type': 'TEXT', 'nullable': False},
                {'name': 'priority', 'type': 'INTEGER', 'default': '0'},
                {'name': 'expires_at', 'type': 'TIMESTAMP', 'nullable': False}
            ],
            'indexes': [
                {'name': 'idx_featured_at', 'columns': ['featured_at']},
                {'name': 'idx_featured_priority', 'columns': ['priority']},
                {'name': 'idx_featured_expires', 'columns': ['expires_at']}
            ],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)', 'on_delete': 'CASCADE'}
            ],
            'checks': [
                {'name': 'valid_featured_dates', 'expression': "expires_at > featured_at"}
            ]
        },
        {
            'name': 'featured_listing_payments',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'payment_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'amount_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'duration_days', 'type': 'INTEGER', 'nullable': False},
                {'name': 'priority_level', 'type': 'INTEGER', 'default': '0'},
                {'name': 'status', 'type': 'TEXT', 'nullable': False, 'default': "'pending'"},
                {'name': 'tx_hash', 'type': 'TEXT'},
                {'name': 'paid_at', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_featured_payments_listing', 'columns': ['listing_id']},
                {'name': 'idx_featured_payments_address', 'columns': ['payment_address'], 'unique': True},
                {'name': 'idx_featured_payments_status', 'columns': ['status']},
                {'name': 'idx_featured_payments_created', 'columns': ['created_at']}
            ],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)', 'on_delete': 'CASCADE'}
            ],
            'checks': [
                {'name': 'valid_payment_status', 'expression': "status IN ('pending', 'completed', 'expired')"},
                {'name': 'valid_duration', 'expression': "duration_days > 0"},
                {'name': 'valid_amount', 'expression': "amount_evr > 0"}
            ]
        },
        {
            'name': 'listing_views',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'viewer_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'view_time', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'source', 'type': 'TEXT'},
                {'name': 'session_id', 'type': 'TEXT'}
            ],
            'indexes': [
                {'name': 'idx_views_listing_id', 'columns': ['listing_id']},
                {'name': 'idx_views_viewer', 'columns': ['viewer_address']},
                {'name': 'idx_views_time', 'columns': ['view_time']}
            ],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)', 'on_delete': 'CASCADE'}
            ]
        },
        {
            'name': 'listing_metrics',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'timeframe', 'type': 'TEXT', 'nullable': False},  # '1h', '24h', '7d', '30d'
                {'name': 'unique_views', 'type': 'INTEGER', 'default': '0'},
                {'name': 'total_views', 'type': 'INTEGER', 'default': '0'},
                {'name': 'order_count', 'type': 'INTEGER', 'default': '0'},
                {'name': 'sale_count', 'type': 'INTEGER', 'default': '0'},
                {'name': 'revenue_evr', 'type': 'DECIMAL', 'default': '0'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_metrics_listing_id', 'columns': ['listing_id']},
                {'name': 'idx_metrics_timeframe', 'columns': ['timeframe']},
                {'name': 'idx_metrics_unique', 'columns': ['listing_id', 'timeframe'], 'unique': True}
            ],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)', 'on_delete': 'CASCADE'}
            ]
        },
        {
            'name': 'order_disputes',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'order_id', 'type': 'UUID', 'nullable': True},
                {'name': 'cart_order_id', 'type': 'UUID', 'nullable': True},
                {'name': 'reason', 'type': 'TEXT', 'nullable': False},
                {'name': 'description', 'type': 'TEXT', 'nullable': False},
                {'name': 'status', 'type': 'TEXT', 'nullable': False, 'default': "'opened'"},
                {'name': 'evidence', 'type': 'JSONB', 'nullable': True},
                {'name': 'resolution', 'type': 'TEXT', 'nullable': True},
                {'name': 'resolved_at', 'type': 'TIMESTAMP', 'nullable': True},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'foreign_keys': [
                {'columns': ['order_id'], 'references': 'orders(id)', 'nullable': True},
                {'columns': ['cart_order_id'], 'references': 'cart_orders(id)', 'nullable': True}
            ],
            'indexes': [
                {'name': 'idx_disputes_order', 'columns': ['order_id']},
                {'name': 'idx_disputes_cart_order', 'columns': ['cart_order_id']},
                {'name': 'idx_disputes_status', 'columns': ['status']}
            ],
            'checks': [
                {'name': 'valid_dispute_status', 'expression': "status IN ('opened', 'investigating', 'resolved', 'closed')"},
                {'name': 'valid_order_reference', 'expression': "(order_id IS NOT NULL AND cart_order_id IS NULL) OR (cart_order_id IS NOT NULL AND order_id IS NULL)"}
            ]
        },
        {
            'name': 'order_history',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'order_id', 'type': 'UUID', 'nullable': True},
                {'name': 'cart_order_id', 'type': 'UUID', 'nullable': True},
                {'name': 'status', 'type': 'TEXT', 'nullable': False},
                {'name': 'description', 'type': 'TEXT', 'nullable': False},
                {'name': 'details', 'type': 'JSONB', 'nullable': True},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'foreign_keys': [
                {'columns': ['order_id'], 'references': 'orders(id)', 'nullable': True},
                {'columns': ['cart_order_id'], 'references': 'cart_orders(id)', 'nullable': True}
            ],
            'indexes': [
                {'name': 'idx_history_order', 'columns': ['order_id']},
                {'name': 'idx_history_cart_order', 'columns': ['cart_order_id']},
                {'name': 'idx_history_status', 'columns': ['status']},
                {'name': 'idx_history_time', 'columns': ['created_at']}
            ],
            'checks': [
                {'name': 'valid_order_reference', 'expression': "(order_id IS NOT NULL AND cart_order_id IS NULL) OR (cart_order_id IS NOT NULL AND order_id IS NULL)"}
            ]
        },
        {
            'name': 'system_metrics',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'metric_type', 'type': 'TEXT', 'nullable': False},
                {'name': 'metric_name', 'type': 'TEXT', 'nullable': False},
                {'name': 'metric_value', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_metrics_type', 'columns': ['metric_type']},
                {'name': 'idx_metrics_name', 'columns': ['metric_name']},
                {'name': 'idx_metrics_time', 'columns': ['created_at']}
            ]
        },
        {
            'name': 'rate_limits',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'endpoint', 'type': 'TEXT', 'nullable': False},
                {'name': 'client_id', 'type': 'TEXT', 'nullable': False},
                {'name': 'request_count', 'type': 'INT8', 'nullable': False, 'default': '1'},
                {'name': 'reset_time', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_rate_limits_endpoint', 'columns': ['endpoint']},
                {'name': 'idx_rate_limits_client', 'columns': ['client_id']},
                {'name': 'idx_rate_limits_reset', 'columns': ['reset_time']},
                {'name': 'idx_rate_limits_unique', 'columns': ['endpoint', 'client_id'], 'unique': True}
            ]
        },
        {
            'name': 'order_payouts',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'order_id', 'type': 'UUID', 'nullable': True},
                {'name': 'cart_order_id', 'type': 'UUID', 'nullable': True},
                {'name': 'tx_hash', 'type': 'TEXT', 'nullable': True},
                {'name': 'amount', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'asset_name', 'type': 'TEXT', 'nullable': False},
                {'name': 'to_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'status', 'type': 'TEXT', 'nullable': False, 'default': "'pending'"},
                {'name': 'error', 'type': 'TEXT', 'nullable': True},
                {'name': 'attempts', 'type': 'INT8', 'default': '0'},
                {'name': 'last_attempt', 'type': 'TIMESTAMP', 'nullable': True},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'foreign_keys': [
                {'columns': ['order_id'], 'references': 'orders(id)', 'nullable': True},
                {'columns': ['cart_order_id'], 'references': 'cart_orders(id)', 'nullable': True}
            ],
            'indexes': [
                {'name': 'idx_payouts_order', 'columns': ['order_id']},
                {'name': 'idx_payouts_cart_order', 'columns': ['cart_order_id']},
                {'name': 'idx_payouts_status', 'columns': ['status']},
                {'name': 'idx_payouts_tx', 'columns': ['tx_hash']}
            ],
            'checks': [
                {'name': 'valid_order_reference', 'expression': "(order_id IS NOT NULL AND cart_order_id IS NULL) OR (cart_order_id IS NOT NULL AND order_id IS NULL)"}
            ]
        },
        {
            'name': 'sale_history',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'order_id', 'type': 'UUID', 'nullable': True},
                {'name': 'cart_order_id', 'type': 'UUID', 'nullable': True},
                {'name': 'asset_name', 'type': 'TEXT', 'nullable': False},
                {'name': 'amount', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'price_evr', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'seller_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'buyer_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'sale_time', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'},
                {'columns': ['order_id'], 'references': 'orders(id)', 'nullable': True},
                {'columns': ['cart_order_id'], 'references': 'cart_orders(id)', 'nullable': True}
            ],
            'indexes': [
                {'name': 'idx_sales_listing', 'columns': ['listing_id']},
                {'name': 'idx_sales_order', 'columns': ['order_id']},
                {'name': 'idx_sales_cart_order', 'columns': ['cart_order_id']},
                {'name': 'idx_sales_seller', 'columns': ['seller_address']},
                {'name': 'idx_sales_buyer', 'columns': ['buyer_address']},
                {'name': 'idx_sales_time', 'columns': ['sale_time']}
            ],
            'checks': [
                {'name': 'valid_sale_order_reference', 'expression': "(order_id IS NOT NULL AND cart_order_id IS NULL) OR (cart_order_id IS NOT NULL AND order_id IS NULL)"}
            ]
        },
        {
            'name': 'listing_price_history',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'asset_name', 'type': 'TEXT', 'nullable': False},
                {'name': 'price_evr', 'type': 'DECIMAL'},
                {'name': 'price_asset_name', 'type': 'TEXT'},
                {'name': 'price_asset_amount', 'type': 'DECIMAL'},
                {'name': 'change_type', 'type': 'TEXT', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'idx_price_history_listing', 'columns': ['listing_id']},
                {'name': 'idx_price_history_time', 'columns': ['created_at']}
            ]
        },
        {
            'name': 'seller_reputation',
            'columns': [
                {'name': 'seller_address', 'type': 'TEXT', 'primary_key': True},
                {'name': 'total_sales', 'type': 'INT8', 'default': '0'},
                {'name': 'successful_sales', 'type': 'INT8', 'default': '0'},
                {'name': 'disputed_sales', 'type': 'INT8', 'default': '0'},
                {'name': 'total_volume', 'type': 'DECIMAL', 'default': '0'},
                {'name': 'avg_rating', 'type': 'DECIMAL'},
                {'name': 'verified_at', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_reputation_rating', 'columns': ['avg_rating']},
                {'name': 'idx_reputation_volume', 'columns': ['total_volume']}
            ]
        },
        {
            'name': 'notification_settings',
            'columns': [
                {'name': 'user_address', 'type': 'TEXT', 'primary_key': True},
                {'name': 'email_enabled', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'email_address', 'type': 'TEXT'},
                {'name': 'order_updates', 'type': 'BOOLEAN', 'default': 'true'},
                {'name': 'listing_updates', 'type': 'BOOLEAN', 'default': 'true'},
                {'name': 'price_alerts', 'type': 'BOOLEAN', 'default': 'true'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ]
        },
        {
            'name': 'notifications',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'user_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'type', 'type': 'TEXT', 'nullable': False},
                {'name': 'title', 'type': 'TEXT', 'nullable': False},
                {'name': 'message', 'type': 'TEXT', 'nullable': False},
                {'name': 'data', 'type': 'JSONB'},
                {'name': 'read', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_notifications_user', 'columns': ['user_address']},
                {'name': 'idx_notifications_read', 'columns': ['read']},
                {'name': 'idx_notifications_time', 'columns': ['created_at']}
            ]
        },
        {
            'name': 'inventory_history',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'asset_name', 'type': 'TEXT', 'nullable': False},
                {'name': 'change_amount', 'type': 'DECIMAL', 'nullable': False},
                {'name': 'change_type', 'type': 'TEXT', 'nullable': False},
                {'name': 'tx_hash', 'type': 'TEXT'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'idx_inventory_listing', 'columns': ['listing_id']},
                {'name': 'idx_inventory_time', 'columns': ['created_at']}
            ]
        },
        {
            'name': 'auth_challenges',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'address', 'type': 'TEXT', 'nullable': False},
                {'name': 'challenge', 'type': 'TEXT', 'nullable': False},
                {'name': 'expires_at', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'used', 'type': 'BOOLEAN', 'nullable': False, 'default': 'false'}
            ],
            'indexes': [
                {'name': 'auth_challenges_address_idx', 'columns': ['address']},
                {'name': 'auth_challenges_expires_at_idx', 'columns': ['expires_at']}
            ]
        },
        {
            'name': 'auth_sessions',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'address', 'type': 'TEXT', 'nullable': False},
                {'name': 'token', 'type': 'TEXT', 'nullable': False},
                {'name': 'expires_at', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'last_used_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'user_agent', 'type': 'TEXT', 'nullable': True},
                {'name': 'ip_address', 'type': 'TEXT', 'nullable': True},
                {'name': 'revoked', 'type': 'BOOLEAN', 'nullable': False, 'default': 'false'}
            ],
            'indexes': [
                {'name': 'auth_sessions_token_idx', 'columns': ['token']},
                {'name': 'auth_sessions_address_idx', 'columns': ['address']},
                {'name': 'auth_sessions_expires_at_idx', 'columns': ['expires_at']}
            ]
        },
        {
            'name': 'user_profiles',
            'columns': [
                {'name': 'address', 'type': 'TEXT', 'primary_key': True},
                {'name': 'friendly_name', 'type': 'TEXT', 'nullable': False, 'default': "''"},
                {'name': 'bio', 'type': 'TEXT', 'nullable': False, 'default': "''"},
                {'name': 'profile_ipfs', 'type': 'TEXT', 'nullable': False, 'default': "''"},
                {'name': 'status', 'type': 'TEXT', 'nullable': False, 'default': "'active'"},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_profiles_status', 'columns': ['status']}
            ]
        },
        {
            'name': 'user_favorite_assets',
            'columns': [
                {'name': 'address', 'type': 'TEXT'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_favorites_address', 'columns': ['address']},
                {'name': 'idx_favorites_asset', 'columns': ['asset_name']},
                {'name': 'idx_favorites_unique', 'columns': ['address', 'asset_name'], 'unique': True}
            ]
        },
        {
            'name': 'chat_messages',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'text', 'type': 'TEXT', 'nullable': False},
                {'name': 'sender', 'type': 'TEXT', 'nullable': False},
                {'name': 'channel', 'type': 'TEXT'},
                {'name': 'type', 'type': 'TEXT', 'nullable': False},  # 'global', 'asset', 'direct'
                {'name': 'ipfs_hash', 'type': 'TEXT'},
                {'name': 'edited', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'deleted', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_chat_messages_sender', 'columns': ['sender']},
                {'name': 'idx_chat_messages_channel', 'columns': ['channel']},
                {'name': 'idx_chat_messages_type', 'columns': ['type']},
                {'name': 'idx_chat_messages_created', 'columns': ['created_at']}
            ]
        },
        {
            'name': 'chat_reactions',
            'columns': [
                {'name': 'message_id', 'type': 'UUID', 'nullable': False},
                {'name': 'user_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'emoji', 'type': 'TEXT', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_chat_reactions_message', 'columns': ['message_id']},
                {'name': 'idx_chat_reactions_user', 'columns': ['user_address']}
            ],
            'constraints': [
                {'name': 'pk_chat_reactions', 'type': 'PRIMARY KEY', 'columns': ['message_id', 'user_address', 'emoji']},
                {'name': 'fk_chat_reactions_message', 'type': 'FOREIGN KEY', 'columns': ['message_id'], 'references': ['chat_messages', 'id']}
            ]
        },
        {
            'name': 'chat_channel_subscriptions',
            'columns': [
                {'name': 'user_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'channel', 'type': 'TEXT', 'nullable': False},
                {'name': 'type', 'type': 'TEXT', 'nullable': False},  # 'global', 'asset', 'direct'
                {'name': 'last_read_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_chat_subs_user', 'columns': ['user_address']},
                {'name': 'idx_chat_subs_channel', 'columns': ['channel']}
            ],
            'constraints': [
                {'name': 'pk_chat_subs', 'type': 'PRIMARY KEY', 'columns': ['user_address', 'channel']}
            ]
        },
        {
            'name': 'chat_presence',
            'columns': [
                {'name': 'user_address', 'type': 'TEXT', 'primary_key': True},
                {'name': 'status', 'type': 'TEXT', 'nullable': False},  # 'online', 'away', 'offline'
                {'name': 'last_active', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ]
        },
        {
            'name': 'chat_attachments',
            'columns': [
                {'name': 'ipfs_hash', 'type': 'TEXT', 'primary_key': True},
                {'name': 'url', 'type': 'TEXT', 'nullable': False},
                {'name': 'type', 'type': 'TEXT', 'nullable': False},
                {'name': 'size', 'type': 'BIGINT', 'nullable': False},
                {'name': 'uploader', 'type': 'TEXT', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ]
        },
        {
            'name': 'chat_reports',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'message_id', 'type': 'UUID', 'nullable': False},
                {'name': 'reporter', 'type': 'TEXT', 'nullable': False},
                {'name': 'reason', 'type': 'TEXT', 'nullable': False},
                {'name': 'status', 'type': 'TEXT', 'nullable': False, 'default': "'pending'"},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_chat_reports_message', 'columns': ['message_id']},
                {'name': 'idx_chat_reports_reporter', 'columns': ['reporter']},
                {'name': 'idx_chat_reports_status', 'columns': ['status']}
            ],
            'constraints': [
                {'name': 'fk_chat_reports_message', 'type': 'FOREIGN KEY', 'columns': ['message_id'], 'references': ['chat_messages', 'id']}
            ]
        }
    ],
    
    'triggers': [
        {
            'name': 'record_order_history_trigger',
            'function_name': 'record_order_history',
            'table': 'orders',
            'timing': 'AFTER',
            'events': ['UPDATE'],
            'level': 'ROW',
            'function_body': '''
                BEGIN
                    IF (OLD).status != (NEW).status THEN
                        INSERT INTO order_history (
                            order_id,
                            status,
                            description,
                            details
                        ) VALUES (
                            (NEW).id,
                            (NEW).status,
                            'Order status changed from ' || (OLD).status || ' to ' || (NEW).status,
                            ('{"previous_status":"' || (OLD).status || 
                             '","new_status":"' || (NEW).status || 
                             '"}')::jsonb
                        );
                    END IF;
                    RETURN NEW;
                END;
            '''
        }
    ]
}