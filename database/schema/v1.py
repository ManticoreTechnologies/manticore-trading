"""Initial database schema."""

schema = {
    'version': 1,
    'tables': [
        {
            'name': 'users',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True},
                {'name': 'username', 'type': 'STRING', 'unique': True},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()'}
            ]
        },
        {
            'name': 'assets',
            'columns': [
                {'name': 'id', 'type': 'UUID', 'primary_key': True},
                {'name': 'name', 'type': 'STRING', 'unique': True},
                {'name': 'symbol', 'type': 'STRING', 'unique': True},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'now()'}
            ]
        }
    ]
} 