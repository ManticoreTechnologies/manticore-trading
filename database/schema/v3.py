"""Recreate blockchain tables."""

schema = {
    'version': 3,
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
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()'}
            ]
        }
    ],
    'migrations': [
        # Migration SQL from v2 to v3
        '''
        -- Drop existing tables
        DROP TABLE IF EXISTS blocks;
        DROP TABLE IF EXISTS transactions;
        
        -- Create blocks table
        CREATE TABLE blocks (
            hash STRING PRIMARY KEY,
            height INT8 UNIQUE,
            timestamp INT8,
            created_at TIMESTAMP DEFAULT now()
        );
        
        -- Create transactions table
        CREATE TABLE transactions (
            hash STRING PRIMARY KEY,
            version INT8,
            size INT8,
            time INT8,
            created_at TIMESTAMP DEFAULT now()
        );
        '''
    ]
} 