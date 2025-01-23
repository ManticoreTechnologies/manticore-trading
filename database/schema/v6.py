"""Schema v6 - Add wallet transaction details."""

schema = {
    'version': 6,
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
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'tx_category_idx', 'columns': ['category']},
                {'name': 'tx_confirmations_idx', 'columns': ['confirmations']},
                {'name': 'tx_time_idx', 'columns': ['time']},
                {'name': 'tx_updated_at_idx', 'columns': ['updated_at']}
            ]
        }
    ],
    'migrations': [
        '''
        -- Add wallet-specific columns to transactions
        ALTER TABLE transactions
        ADD COLUMN IF NOT EXISTS fee DECIMAL(20, 8) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS total_sent DECIMAL(20, 8) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS total_received DECIMAL(20, 8) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS category STRING DEFAULT 'unknown',
        ADD COLUMN IF NOT EXISTS from_addresses STRING[], -- Array of sending addresses
        ADD COLUMN IF NOT EXISTS to_addresses STRING[], -- Array of receiving addresses
        ADD COLUMN IF NOT EXISTS trusted BOOLEAN DEFAULT false,
        ADD COLUMN IF NOT EXISTS bip125_replaceable BOOLEAN DEFAULT false,
        ADD COLUMN IF NOT EXISTS abandoned BOOLEAN DEFAULT false;

        -- Create indexes for common queries
        CREATE INDEX IF NOT EXISTS tx_category_idx ON transactions(category);
        CREATE INDEX IF NOT EXISTS tx_confirmations_idx ON transactions(confirmations);
        CREATE INDEX IF NOT EXISTS tx_time_idx ON transactions(time);
        CREATE INDEX IF NOT EXISTS tx_updated_at_idx ON transactions(updated_at);
        '''
    ]
} 