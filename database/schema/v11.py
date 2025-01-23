"""Schema v11 - Add support for trading platform listings with CockroachDB Cloud compatibility."""

schema = {
    'version': 11,
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
                {'name': 'status', 'type': 'STRING', 'default': "'active'", 'nullable': False},
                {'name': 'price_evr', 'type': 'DECIMAL(24,8)', 'nullable': True},
                {'name': 'price_asset_name', 'type': 'STRING', 'nullable': True},
                {'name': 'price_asset_amount', 'type': 'DECIMAL(24,8)', 'nullable': True}
            ],
            'indexes': [
                {'name': 'listings_by_seller', 'columns': ['seller_address']},
                {'name': 'listings_by_status', 'columns': ['status']},
                {'name': 'listings_by_created', 'columns': ['created_at DESC']}
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
        -- Drop existing tables to start fresh
        DROP TABLE IF EXISTS listing_transactions CASCADE;
        DROP TABLE IF EXISTS listing_balances CASCADE;
        DROP TABLE IF EXISTS listing_addresses CASCADE;
        DROP TABLE IF EXISTS listings CASCADE;
        DROP TABLE IF EXISTS transaction_entries CASCADE;
        DROP TABLE IF EXISTS blocks CASCADE;
        ''',
        
        '''
        -- Create the blocks table
        CREATE TABLE blocks (
            hash STRING PRIMARY KEY,
            height INT8 UNIQUE,
            timestamp INT8,
            created_at TIMESTAMP DEFAULT now()
        );
        ''',
        
        '''
        -- Create the transaction_entries table
        CREATE TABLE transaction_entries (
            tx_hash STRING NOT NULL,
            address STRING NOT NULL,
            entry_type STRING NOT NULL,
            asset_name STRING NOT NULL DEFAULT 'EVR',
            amount DECIMAL(20,8) DEFAULT 0,
            fee DECIMAL(20,8) DEFAULT 0,
            confirmations INT8 DEFAULT 0,
            time INT8,
            asset_type STRING,
            asset_message STRING,
            vout INT8,
            trusted BOOLEAN DEFAULT false,
            bip125_replaceable BOOLEAN DEFAULT false,
            abandoned BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now(),
            PRIMARY KEY (tx_hash, address, entry_type, asset_name)
        );
        CREATE INDEX tx_entries_address_idx ON transaction_entries(address);
        CREATE INDEX tx_entries_asset_name_idx ON transaction_entries(asset_name);
        CREATE INDEX tx_entries_entry_type_idx ON transaction_entries(entry_type);
        CREATE INDEX tx_entries_time_idx ON transaction_entries(time);
        CREATE INDEX tx_entries_confirmations_idx ON transaction_entries(confirmations);
        CREATE INDEX tx_entries_updated_at_idx ON transaction_entries(updated_at);
        ''',
        
        '''
        -- Create the listings table
        CREATE TABLE listings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            seller_address STRING NOT NULL,
            name STRING NOT NULL,
            description STRING,
            image_ipfs_hash STRING,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now(),
            status STRING NOT NULL DEFAULT 'active',
            price_evr DECIMAL(24,8),
            price_asset_name STRING,
            price_asset_amount DECIMAL(24,8)
        );
        CREATE INDEX listings_by_seller ON listings(seller_address);
        CREATE INDEX listings_by_status ON listings(status);
        CREATE INDEX listings_by_created ON listings(created_at DESC);
        ''',
        
        '''
        -- Create the listing_addresses table
        CREATE TABLE listing_addresses (
            listing_id UUID NOT NULL REFERENCES listings(id),
            deposit_address STRING NOT NULL,
            asset_name STRING NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            PRIMARY KEY (listing_id, asset_name)
        );
        CREATE UNIQUE INDEX listing_addresses_by_address ON listing_addresses(deposit_address);
        ''',
        
        '''
        -- Create the listing_balances table
        CREATE TABLE listing_balances (
            listing_id UUID NOT NULL REFERENCES listings(id),
            asset_name STRING NOT NULL,
            confirmed_balance DECIMAL(24,8) NOT NULL DEFAULT 0,
            pending_balance DECIMAL(24,8) NOT NULL DEFAULT 0,
            last_confirmed_tx_hash STRING,
            last_confirmed_tx_time TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT now(),
            PRIMARY KEY (listing_id, asset_name)
        );
        CREATE INDEX listing_balances_by_asset ON listing_balances(asset_name);
        ''',
        
        '''
        -- Create the listing_transactions table
        CREATE TABLE listing_transactions (
            tx_hash STRING NOT NULL,
            listing_id UUID NOT NULL REFERENCES listings(id),
            asset_name STRING NOT NULL,
            amount DECIMAL(24,8) NOT NULL,
            tx_type STRING NOT NULL,
            confirmations INT8 NOT NULL DEFAULT 0,
            status STRING NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now(),
            PRIMARY KEY (tx_hash, listing_id, asset_name)
        );
        CREATE INDEX listing_txs_by_listing ON listing_transactions(listing_id);
        CREATE INDEX listing_txs_by_status ON listing_transactions(status);
        CREATE INDEX listing_txs_by_created ON listing_transactions(created_at DESC);
        '''
    ]
} 