"""Complete database reset and recreation."""

schema = {
    'version': 4,
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
        # Migration SQL from v3 to v4 - Complete reset
        '''
        -- Drop all tables in correct order (dependent tables first)
        DROP TABLE IF EXISTS listing_deposits;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS assets;
        DROP TABLE IF EXISTS blocks;
        DROP TABLE IF EXISTS transactions;
        DROP TABLE IF EXISTS schema_version;
        
        -- Recreate schema version tracking
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT now()
        );
        
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