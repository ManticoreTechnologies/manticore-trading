"""Schema management for database module.

This module handles schema versioning, validation, and migrations.
"""
import importlib
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from asyncpg.pool import Pool

from ..exceptions import DatabaseSchemaError

logger = logging.getLogger(__name__)

class SchemaManager:
    """Manages database schema versions and migrations."""
    
    def __init__(self, pool: Pool):
        self.pool = pool
        self.current_version: Optional[int] = None
        self._schema_dir = Path(__file__).parent.parent / 'schema'
        
    async def initialize(self) -> None:
        """Initialize schema management.
        
        Creates schema version table if it doesn't exist and runs any pending migrations.
        """
        try:
            # Create schema version table if it doesn't exist
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INT8 PRIMARY KEY,
                        applied_at TIMESTAMP NOT NULL DEFAULT now()
                    )
                ''')
                
                # Get current version
                row = await conn.fetchrow(
                    'SELECT version FROM schema_version ORDER BY version DESC LIMIT 1'
                )
                self.current_version = row['version'] if row else 0
                
            # Load and validate all schema versions
            schema_files = self._load_schema_files()
            if not schema_files:
                logger.warning("No schema files found")
                return
                
            # Apply any pending migrations
            await self._apply_migrations(schema_files)
                
        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")
            raise DatabaseSchemaError(f"Failed to initialize schema: {e}")
    
    def _load_schema_files(self) -> Dict[int, Dict[str, Any]]:
        """Load all schema version files.
        
        Returns:
            Dict mapping version numbers to schema definitions
        """
        schema_files = {}
        
        if not self._schema_dir.exists():
            return schema_files
            
        # Load all vX.py files
        for file in self._schema_dir.glob('v*.py'):
            try:
                version = int(file.stem[1:])  # Extract number from vX.py
                module_path = f"database.schema.{file.stem}"
                module = importlib.import_module(module_path)
                
                if not hasattr(module, 'schema'):
                    raise DatabaseSchemaError(
                        f"Schema file {file} missing 'schema' definition"
                    )
                    
                schema = module.schema
                if schema['version'] != version:
                    raise DatabaseSchemaError(
                        f"Schema version mismatch in {file}: "
                        f"Expected v{version}, got v{schema['version']}"
                    )
                    
                schema_files[version] = schema
                
            except ValueError:
                logger.warning(f"Invalid schema filename: {file}")
            except ImportError as e:
                logger.error(f"Failed to import schema {file}: {e}")
            except Exception as e:
                logger.error(f"Error loading schema {file}: {e}")
                
        return dict(sorted(schema_files.items()))  # Sort by version
    
    async def _apply_migrations(self, schema_files: Dict[int, Dict[str, Any]]) -> None:
        """Apply any pending schema migrations.
        
        Args:
            schema_files: Dict mapping version numbers to schema definitions
        """
        if not schema_files:
            return
            
        latest_version = max(schema_files.keys())
        if self.current_version >= latest_version:
            logger.info("Schema is up to date")
            return
            
        logger.info(
            f"Updating schema from version {self.current_version} to {latest_version}"
        )
        
        try:
            async with self.pool.acquire() as conn:
                # Drop all existing tables except schema_version
                await self._drop_all_tables(conn)
                
                # Get the latest schema
                schema = schema_files[latest_version]
                
                # Create all tables without foreign keys first
                for table in schema.get('tables', []):
                    await self._create_table(conn, table)
                
                # Add foreign keys and indexes
                for table in schema.get('tables', []):
                    await self._add_constraints(conn, table)
                
                # Update schema version
                await conn.execute(
                    'INSERT INTO schema_version (version) VALUES ($1)',
                    latest_version
                )
                logger.info(f"Successfully migrated to version {latest_version}")
                    
        except Exception as e:
            logger.error(f"Schema migration failed: {e}")
            raise DatabaseSchemaError(f"Failed to apply schema migrations: {e}")
    
    async def _drop_all_tables(self, conn) -> None:
        """Drop all existing tables in the database.
        
        Args:
            conn: Database connection
        """
        try:
            # Get all tables except schema_version
            tables = await conn.fetch('''
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name != 'schema_version'
                ORDER BY table_name DESC
            ''')
            
            # Drop each table with CASCADE
            for table in tables:
                await conn.execute(f'DROP TABLE IF EXISTS {table["table_name"]} CASCADE')
                logger.info(f"Dropped table {table['table_name']}")
                    
        except Exception as e:
            logger.error(f"Error during table cleanup: {e}")
            raise
    
    async def _create_table(self, conn, table: Dict[str, Any]) -> None:
        """Create a single table without foreign keys.
        
        Args:
            conn: Database connection
            table: Table definition dictionary
        """
        columns = []
        constraints = []
        
        for col in table['columns']:
            col_def = f"{col['name']} {col['type']}"
            
            if col.get('primary_key'):
                constraints.append(f"PRIMARY KEY ({col['name']})")
            elif col.get('unique'):
                constraints.append(f"UNIQUE ({col['name']})")
                
            if 'default' in col:
                col_def += f" DEFAULT {col['default']}"
                
            if col.get('nullable') is False:
                col_def += " NOT NULL"
                
            columns.append(col_def)
            
        # Add composite primary key if specified
        if 'primary_key' in table:
            if isinstance(table['primary_key'], list):
                constraints.append(
                    f"PRIMARY KEY ({', '.join(table['primary_key'])})"
                )
            
        # Combine columns and constraints
        table_def = ', '.join(columns + constraints)
        
        # Create table
        await conn.execute(f'''
            CREATE TABLE {table['name']} (
                {table_def}
            )
        ''')
        logger.info(f"Created table {table['name']}")
    
    async def _add_constraints(self, conn, table: Dict[str, Any]) -> None:
        """Add foreign keys and indexes to a table.
        
        Args:
            conn: Database connection
            table: Table definition dictionary
        """
        # Add foreign key constraints
        if 'foreign_keys' in table:
            for fk in table['foreign_keys']:
                await conn.execute(f'''
                    ALTER TABLE {table['name']}
                    ADD CONSTRAINT fk_{table['name']}_{fk['columns'][0]}
                    FOREIGN KEY ({', '.join(fk['columns'])})
                    REFERENCES {fk['references']}
                ''')
                logger.info(
                    f"Added foreign key constraint to {table['name']} "
                    f"referencing {fk['references']}"
                )
        
        # Create indexes
        if 'indexes' in table:
            for idx in table['indexes']:
                unique = 'UNIQUE ' if idx.get('unique') else ''
                await conn.execute(f'''
                    CREATE {unique}INDEX {idx['name']} 
                    ON {table['name']}({', '.join(idx['columns'])})
                ''')
                logger.info(f"Created index {idx['name']} on {table['name']}") 