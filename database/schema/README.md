# Database Schema Migration Guidelines

This document outlines the strict guidelines for managing database schema migrations in the Manticore Trading application.

## Schema Version Files

Each schema version should be in a separate file named `vN.py` where N is the version number. For example: `v1.py`, `v2.py`, etc.

### File Structure
```python
"""Schema vN - Brief Title

This version adds/changes/removes:
1. List major changes
2. ...

Changes:
- Detailed list of modifications
- Include table/column names affected

Rollback:
- SQL statements to undo changes
- In reverse order of application
"""

schema = {
    'version': N,  # Must match filename
    'migrations': [...],  # SQL statements
    # 'tables': [...],  # Only in v1 or for new tables
}
```

## Migration Rules

### 1. Migration Statements
- Use only ALTER, CREATE, or DROP statements
- Make statements idempotent with IF EXISTS/IF NOT EXISTS
- One change per statement for clarity
- Include comments explaining complex changes

```python
'migrations': [
    # Add new column
    '''
    ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS priority INT8 NOT NULL DEFAULT 0;
    ''',
    
    # Create index
    '''
    CREATE INDEX IF NOT EXISTS idx_orders_priority 
    ON orders(priority DESC);
    '''
]
```

### 2. Table Definitions
- Only include in v1.py or when creating new tables
- For modifications, use migrations array instead
- Never redefine existing tables in later versions
- When adding a table, include all constraints and indexes

### 3. Naming Conventions
All database objects must follow these naming patterns:

```sql
-- Foreign Keys
fk_{table}_{column}

-- Indexes
idx_{table}_{column}
idx_{table}_{column1}_{column2}  # For multi-column

-- Unique Constraints
uq_{table}_{column}

-- Primary Keys
pk_{table}

-- Check Constraints
chk_{table}_{rule}

-- Triggers
trg_{table}_{action}
```

### 4. Best Practices

#### Do's:
- Make incremental, focused changes
- Test migrations both up and down
- Document all changes clearly
- Include rollback instructions
- Use consistent naming conventions
- Add appropriate indexes for foreign keys
- Make migrations idempotent

#### Don'ts:
- Don't modify existing migrations
- Don't redefine existing tables
- Don't create duplicate constraint names
- Don't combine multiple schema changes
- Don't forget to update version number
- Don't use ambiguous names

### 5. Example Migration

```python
"""Schema v3 - Add order priority

This version adds:
1. priority column to orders table
2. index on priority for efficient querying

Changes:
- Add priority column (INT8, NOT NULL, DEFAULT 0) to orders table
- Add descending index on priority column
- No table structure changes, only additive modifications

Rollback:
- DROP INDEX idx_orders_priority;
- ALTER TABLE orders DROP COLUMN priority;
"""

schema = {
    'version': 3,
    'migrations': [
        '''
        ALTER TABLE orders
        ADD COLUMN IF NOT EXISTS priority INT8 NOT NULL DEFAULT 0;
        ''',
        '''
        CREATE INDEX IF NOT EXISTS idx_orders_priority 
        ON orders(priority DESC);
        '''
    ]
}
```

## Testing Migrations

1. Always test migrations on a development database first
2. Verify both upgrade and downgrade paths
3. Check for:
   - Data integrity
   - Constraint violations
   - Index effectiveness
   - Performance impact

## Common Issues

1. **Duplicate Constraints**
   - Error: "duplicate constraint name"
   - Solution: Use unique names following conventions
   - Prevention: Don't redefine existing tables

2. **Missing Dependencies**
   - Error: "relation does not exist"
   - Solution: Create tables in correct order
   - Prevention: Use migrations array for modifications

3. **Invalid Syntax**
   - Error: Various syntax errors
   - Solution: Follow CockroachDB syntax exactly
   - Prevention: Test statements in development first

## Questions?

If you're unsure about a migration:
1. Review existing migrations for patterns
2. Test in development environment
3. Keep changes small and focused
4. Document clearly
5. Include rollback instructions 