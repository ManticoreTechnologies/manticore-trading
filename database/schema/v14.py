"""Schema v14 - Add listing_address to listings table.

This version adds a unique listing_address field to the listings table.
This address will be used to store all assets for sale in the listing.
"""

schema = {
    'version': 14,
    'tables': [
        {
            'name': 'blocks',
            'columns': [
                {'name': 'hash', 'type': 'TEXT', 'primary_key': True},
                {'name': 'height', 'type': 'INT8', 'nullable': False},
                {'name': 'timestamp', 'type': 'TIMESTAMP', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_blocks_height', 'columns': ['height'], 'unique': True}
            ]
        },
        {
            'name': 'transaction_entries',
            'columns': [
                {'name': 'tx_hash', 'type': 'TEXT'},
                {'name': 'address', 'type': 'TEXT'},
                {'name': 'entry_type', 'type': 'TEXT'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'amount', 'type': 'DECIMAL', 'nullable': False},
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
                {'name': 'idx_tx_entries_time', 'columns': ['time']}
            ]
        },
        {
            'name': 'listings',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True, 'default': 'gen_random_uuid()'},
                {'name': 'seller_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'listing_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'name', 'type': 'TEXT', 'nullable': False},
                {'name': 'description', 'type': 'TEXT'},
                {'name': 'image_ipfs_hash', 'type': 'TEXT'},
                {'name': 'status', 'type': 'TEXT', 'default': "'active'"},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'indexes': [
                {'name': 'idx_listings_seller', 'columns': ['seller_address']},
                {'name': 'idx_listings_address', 'columns': ['listing_address'], 'unique': True}
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
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ]
        },
        {
            'name': 'listing_addresses',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'deposit_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'}
            ],
            'indexes': [
                {'name': 'idx_listing_addresses_deposit', 'columns': ['deposit_address'], 'unique': True}
            ]
        },
        {
            'name': 'listing_balances',
            'columns': [
                {'name': 'listing_id', 'type': 'UUID'},
                {'name': 'asset_name', 'type': 'TEXT'},
                {'name': 'deposit_address', 'type': 'TEXT', 'nullable': False},
                {'name': 'confirmed_balance', 'type': 'DECIMAL', 'nullable': False, 'default': '0'},
                {'name': 'pending_balance', 'type': 'DECIMAL', 'nullable': False, 'default': '0'},
                {'name': 'last_confirmed_tx_hash', 'type': 'TEXT'},
                {'name': 'last_confirmed_tx_time', 'type': 'TIMESTAMP'},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'},
                {'name': 'updated_at', 'type': 'TIMESTAMP', 'nullable': False, 'default': 'now()'}
            ],
            'primary_key': ['listing_id', 'asset_name'],
            'foreign_keys': [
                {'columns': ['listing_id'], 'references': 'listings(id)'},
                {'columns': ['deposit_address'], 'references': 'listing_addresses(deposit_address)'}
            ]
        }
    ],
    'migrations': [
        # Add listing_address column
        '''
        ALTER TABLE listings
        ADD COLUMN listing_address TEXT;
        ''',
        
        # Create unique index
        '''
        CREATE UNIQUE INDEX idx_listings_address ON listings(listing_address);
        ''',
        
        # Make listing_address NOT NULL
        '''
        ALTER TABLE listings
        ALTER COLUMN listing_address SET NOT NULL;
        '''
    ]
} 