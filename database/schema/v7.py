"""Schema v7 - Add asset transaction details."""

schema = {
    'version': 7,
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
            'name': 'transactions',
            'columns': [
                {'name': 'hash', 'type': 'STRING', 'primary_key': True},
                {'name': 'version', 'type': 'INT8'},
                {'name': 'size', 'type': 'INT8'},
                {'name': 'time', 'type': 'INT8', 'nullable': True},  # Mempool txs might not have time
                {'name': 'confirmations', 'type': 'INT8', 'default': '0'},
                {'name': 'fee', 'type': 'DECIMAL(20,8)', 'default': '0'},
                {'name': 'total_sent', 'type': 'DECIMAL(20,8)', 'default': '0'},
                {'name': 'total_received', 'type': 'DECIMAL(20,8)', 'default': '0'},
                {'name': 'category', 'type': 'STRING', 'default': "'unknown'"},
                {'name': 'from_addresses', 'type': 'STRING[]'},
                {'name': 'to_addresses', 'type': 'STRING[]'},
                {'name': 'trusted', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'bip125_replaceable', 'type': 'BOOLEAN', 'default': 'false'},
                {'name': 'abandoned', 'type': 'BOOLEAN', 'default': 'false'},
                # Asset transaction details
                {'name': 'asset_type', 'type': 'STRING', 'nullable': True},  # transfer_asset, new_asset, etc
                {'name': 'asset_name', 'type': 'STRING', 'nullable': True},  # CREDITS, etc
                {'name': 'asset_amount', 'type': 'DECIMAL(20,8)', 'default': '0'},
                {'name': 'asset_message', 'type': 'STRING', 'nullable': True},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'tx_asset_name_idx', 'columns': ['asset_name']},
                {'name': 'tx_category_idx', 'columns': ['category']},
                {'name': 'tx_confirmations_idx', 'columns': ['confirmations']},
                {'name': 'tx_time_idx', 'columns': ['time']},
                {'name': 'tx_updated_at_idx', 'columns': ['updated_at']}
            ]
        }
    ],
    'migrations': [
        '''
        -- Add asset-specific columns to transactions
        ALTER TABLE transactions
        ADD COLUMN IF NOT EXISTS asset_type STRING,
        ADD COLUMN IF NOT EXISTS asset_name STRING,
        ADD COLUMN IF NOT EXISTS asset_amount DECIMAL(20, 8) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS asset_message STRING;

        -- Create indexes for efficient asset queries
        CREATE INDEX IF NOT EXISTS tx_asset_name_idx ON transactions(asset_name);
        '''
    ]
} 