"""Schema v12 - Add support for multiple prices per listing."""

schema = {
    'version': 12,
    'tables': [
        {
            'name': 'blocks',
            'columns': [
                {'name': 'hash', 'type': 'STRING', 'primary_key': True},
                {'name': 'height', 'type': 'INT8', 'unique': True},
                {'name': 'timestamp', 'type': 'INT8'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()'}
            ]
        },
        {
            'name': 'transaction_entries',
            'columns': [
                {'name': 'tx_hash', 'type': 'STRING'},
                {'name': 'address', 'type': 'STRING'},
                {'name': 'entry_type', 'type': 'STRING'},  # 'send' or 'receive' relative to our wallet
                {'name': 'asset_name', 'type': 'STRING', 'default': "'EVR'"},  # EVR for regular transactions
                {'name': 'amount', 'type': 'DECIMAL(20,8)', 'default': '0'},
                {'name': 'fee', 'type': 'DECIMAL(20,8)', 'default': '0'},
                {'name': 'confirmations', 'type': 'INT8', 'default': '0'},
                {'name': 'time', 'type': 'INT8', 'nullable': True},
                {'name': 'asset_type', 'type': 'STRING', 'nullable': True},  # transfer_asset, new_asset, etc
                {'name': 'asset_message', 'type': 'STRING', 'nullable': True},
                {'name': 'vout', 'type': 'INT8', 'nullable': True},
                {'name': 'trusted', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'bip125_replaceable', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'abandoned', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'default': 'now()'}
            ],
            'primary_key': ['tx_hash', 'address', 'entry_type', 'asset_name'],  # Composite primary key
            'indexes': [
                {'name': 'tx_entries_address_idx', 'columns': ['address']},
                {'name': 'tx_entries_asset_name_idx', 'columns': ['asset_name']},
                {'name': 'tx_entries_entry_type_idx', 'columns': ['entry_type']},
                {'name': 'tx_entries_time_idx', 'columns': ['time']},
                {'name': 'tx_entries_confirmations_idx', 'columns': ['confirmations']},
                {'name': 'tx_entries_updated_at_idx', 'columns': ['updated_at']}
            ]
        },
        {
            'name': 'listings',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'seller_address', 'type': 'STRING', 'nullable': False},
                {'name': 'name', 'type': 'STRING', 'nullable': False},
                {'name': 'description', 'type': 'STRING', 'nullable': True},
                {'name': 'image_ipfs_hash', 'type': 'STRING', 'nullable': True},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()', 'nullable': False},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'default': 'now()', 'nullable': False},
                {'name': 'status', 'type': 'STRING', 'default': "'active'", 'nullable': False}
            ],
            'indexes': [
                {'name': 'listings_by_seller', 'columns': ['seller_address']},
                {'name': 'listings_by_status', 'columns': ['status']},
                {'name': 'listings_by_created', 'columns': ['created_at DESC']}
            ]
        },
        {
            'name': 'listing_prices',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'asset_name', 'type': 'STRING', 'nullable': False},
                {'name': 'price_evr', 'type': 'DECIMAL(24,8)', 'nullable': True},
                {'name': 'price_asset_name', 'type': 'STRING', 'nullable': True},
                {'name': 'price_asset_amount', 'type': 'DECIMAL(24,8)', 'nullable': True},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()', 'nullable': False},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'default': 'now()', 'nullable': False}
            ],
            'primary_key': ['listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'listing_prices_by_asset', 'columns': ['asset_name']}
            ]
        },
        {
            'name': 'listing_addresses',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'deposit_address', 'type': 'STRING', 'nullable': False},
                {'name': 'asset_name', 'type': 'STRING', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()', 'nullable': False}
            ],
            'primary_key': ['listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'listing_addresses_by_address', 'columns': ['deposit_address'], 'unique': True}
            ]
        },
        {
            'name': 'listing_balances',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'asset_name', 'type': 'STRING', 'nullable': False},
                {'name': 'confirmed_balance', 'type': 'DECIMAL(24,8)', 'default': '0', 'nullable': False},
                {'name': 'pending_balance', 'type': 'DECIMAL(24,8)', 'default': '0', 'nullable': False},
                {'name': 'last_confirmed_tx_hash', 'type': 'STRING', 'nullable': True},
                {'name': 'last_confirmed_tx_time', 'type': 'TIMESTAMP', 'nullable': True},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'default': 'now()', 'nullable': False}
            ],
            'primary_key': ['listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'listing_balances_by_asset', 'columns': ['asset_name']}
            ]
        },
        {
            'name': 'listing_transactions',
            'columns': [
                {'name': 'tx_hash', 'type': 'STRING', 'nullable': False},
                {'name': 'listing_id', 'type': 'UUID', 'nullable': False},
                {'name': 'asset_name', 'type': 'STRING', 'nullable': False},
                {'name': 'amount', 'type': 'DECIMAL(24,8)', 'nullable': False},
                {'name': 'tx_type', 'type': 'STRING', 'nullable': False},
                {'name': 'confirmations', 'type': 'INT8', 'default': '0', 'nullable': False},
                {'name': 'status', 'type': 'STRING', 'default': "'pending'", 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()', 'nullable': False},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'default': 'now()', 'nullable': False}
            ],
            'primary_key': ['tx_hash', 'listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'listing_txs_by_listing', 'columns': ['listing_id']},
                {'name': 'listing_txs_by_status', 'columns': ['status']},
                {'name': 'listing_txs_by_created', 'columns': ['created_at DESC']}
            ]
        }
    ],
    'migrations': [
        '''
        -- Remove price columns from listings table
        ALTER TABLE listings DROP COLUMN IF EXISTS price_evr;
        ALTER TABLE listings DROP COLUMN IF EXISTS price_asset_name;
        ALTER TABLE listings DROP COLUMN IF EXISTS price_asset_amount;
        ''',
        
        '''
        -- Create the listing_prices table
        CREATE TABLE listing_prices (
            listing_id UUID NOT NULL REFERENCES listings(id),
            asset_name STRING NOT NULL,
            price_evr DECIMAL(24,8),
            price_asset_name STRING,
            price_asset_amount DECIMAL(24,8),
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now(),
            PRIMARY KEY (listing_id, asset_name)
        );
        CREATE INDEX listing_prices_by_asset ON listing_prices(asset_name);
        '''
    ]
} 