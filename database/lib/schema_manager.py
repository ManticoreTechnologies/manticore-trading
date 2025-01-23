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
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT now()
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
                # Apply each version in sequence
                for version in range(self.current_version + 1, latest_version + 1):
                    if version not in schema_files:
                        raise DatabaseSchemaError(
                            f"Missing schema version {version}"
                        )
                    
                    schema = schema_files[version]
                    async with conn.transaction():
                        # Apply migrations if they exist
                        if 'migrations' in schema:
                            for sql in schema['migrations']:
                                await conn.execute(sql)
                                
                        # Create/modify tables based on schema
                        await self._apply_schema_version(conn, schema)
                        
                        # Update schema version
                        await conn.execute(
                            'INSERT INTO schema_version (version) VALUES ($1)',
                            version
                        )
                        
                    logger.info(f"Applied schema version {version}")
                    
        except Exception as e:
            logger.error(f"Schema migration failed: {e}")
            raise DatabaseSchemaError(f"Failed to apply schema migrations: {e}")
    
    async def _apply_schema_version(self, conn, schema: Dict[str, Any]) -> None:
        """Apply a single schema version.
        
        Args:
            conn: Database connection
            schema: Schema definition dictionary
        """
        for table in schema['tables']:
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
                    
                columns.append(col_def)
                
            # Combine columns and constraints
            table_def = ', '.join(columns + constraints)
            
            # Create table if it doesn't exist
            await conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {table['name']} (
                    {table_def}
                )
            ''') 