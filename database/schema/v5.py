"""Add confirmations tracking to transactions."""

schema = {
    'version': 5,
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
                {'name': 'confirmations', 'type': 'INT8', 'default': '0'},  # Track confirmations
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'default': 'now()'}
            ]
        }
    ],
    'migrations': [
        # Migration SQL from v4 to v5 - Simplified for CockroachDB
        '''
        -- Add confirmations and updated_at to transactions
        ALTER TABLE transactions 
        ADD COLUMN IF NOT EXISTS confirmations INT8 DEFAULT 0,
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT now();
        '''
    ]
} 