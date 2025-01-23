"""Schema v10 - Remove redundant counterparty_address column."""

schema = {
    'version': 10,
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
        }
    ],
    'migrations': [
        '''
        -- Drop the counterparty_address column and its index
        DROP INDEX IF EXISTS tx_entries_counterparty_idx;
        ALTER TABLE transaction_entries DROP COLUMN IF EXISTS counterparty_address;
        '''
    ]
} 