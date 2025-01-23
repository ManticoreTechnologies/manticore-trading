"""Schema v9 - Add counterparty address tracking for transaction entries."""

schema = {
    'version': 9,
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
                # Composite primary key of transaction hash and address
                {'name': 'tx_hash', 'type': 'STRING'},
                {'name': 'address', 'type': 'STRING'},
                {'name': 'entry_type', 'type': 'STRING'},  # 'send' or 'receive'
                {'name': 'asset_name', 'type': 'STRING', 'default': "'EVR'"},  # EVR for regular transactions
                {'name': 'amount', 'type': 'DECIMAL(20,8)', 'default': '0'},
                {'name': 'fee', 'type': 'DECIMAL(20,8)', 'default': '0'},
                {'name': 'confirmations', 'type': 'INT8', 'default': '0'},
                {'name': 'time', 'type': 'INT8', 'nullable': True},
                {'name': 'asset_type', 'type': 'STRING', 'nullable': True},  # transfer_asset, new_asset, etc
                {'name': 'asset_message', 'type': 'STRING', 'nullable': True},
                {'name': 'vout', 'type': 'INT8', 'nullable': True},
                {'name': 'counterparty_address', 'type': 'STRING', 'nullable': True},  # The to/from address
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
                {'name': 'tx_entries_updated_at_idx', 'columns': ['updated_at']},
                {'name': 'tx_entries_counterparty_idx', 'columns': ['counterparty_address']}  # New index
            ]
        }
    ],
    'migrations': [
        '''
        -- Add counterparty_address column to transaction_entries
        ALTER TABLE transaction_entries ADD COLUMN IF NOT EXISTS counterparty_address STRING;

        -- Create index for counterparty address lookups
        CREATE INDEX IF NOT EXISTS tx_entries_counterparty_idx ON transaction_entries(counterparty_address);
        '''
    ]
} 