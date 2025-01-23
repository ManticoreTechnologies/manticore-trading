"""Database schema management module.

This module handles database schema versioning, validation, and migrations.
It supports creating and updating tables, indexes, foreign keys, triggers, and scheduled jobs.
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
    """Manages database schema versioning and migrations."""
    
    def __init__(self, pool, schema_dir: str = 'database/schema/') -> None:
        """Initialize schema manager.
        
        Args:
            pool: Database connection pool
            schema_dir: Directory containing schema version files
        """
        self.pool = pool
        self._schema_dir = Path(schema_dir)
        self.current_version = 0
        self._schema_files = {}
    
    async def initialize(self) -> None:
        """Initialize schema management.
        
        Creates schema version table if it doesn't exist and runs any pending migrations.
        
        Raises:
            DatabaseSchemaError: If schema initialization fails or no valid schema files are found
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
                logger.error("No valid schema files found in schema directory")
                raise DatabaseSchemaError("No valid schema files found in schema directory")
                
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
                
        self._schema_files = dict(sorted(schema_files.items()))
        return self._schema_files
    
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
                # If this is a fresh install (version 0), create all tables
                if self.current_version == 0:
                    await self._create_fresh_schema(conn, schema_files[latest_version])
                else:
                    # Apply incremental migrations for each version
                    for version in range(self.current_version + 1, latest_version + 1):
                        if version in schema_files:
                            schema = schema_files[version]
                            await self._apply_version_migrations(conn, schema)
                            
                            # Update schema version after each successful migration
                            await conn.execute(
                                'INSERT INTO schema_version (version) VALUES ($1)',
                                version
                            )
                            logger.info(f"Successfully migrated to version {version}")
                
        except Exception as e:
            logger.error(f"Schema migration failed: {e}")
            raise DatabaseSchemaError(f"Failed to apply schema migrations: {e}")
    
    async def _create_function(self, conn, function: Dict[str, Any]) -> None:
        """Create a standalone database function.
        
        Args:
            conn: Database connection
            function: Function definition dictionary
        """
        try:
            args = []
            for arg in function.get('args', []):
                args.append(f"{arg['name']} {arg['type']}")
                
            args_str = ', '.join(args)
            
            await conn.execute(f'''
                CREATE OR REPLACE FUNCTION {function['name']}({args_str})
                RETURNS {function['returns']}
                AS $${function['body']}$$ 
                LANGUAGE {function['language']};
            ''')
            logger.info(f"Created function {function['name']}")
        except Exception as e:
            if 'already exists' not in str(e):
                raise
            logger.debug(f"Function already exists: {str(e)}")

    async def _create_fresh_schema(self, conn, schema: Dict[str, Any]) -> None:
        """Create a fresh schema installation.
        
        Args:
            conn: Database connection
            schema: Latest schema definition
        """
        # Drop all existing tables except schema_version
        await self._drop_all_tables(conn)
        
        # Create all tables without foreign keys first
        for table in schema.get('tables', []):
            await self._create_table(conn, table)
        
        # Add foreign keys and indexes
        for table in schema.get('tables', []):
            await self._add_constraints(conn, table)
            
        # Create standalone functions after tables exist
        for function in schema.get('functions', []):
            await self._create_function(conn, function)
            
        # Create triggers last since they may depend on functions
        for trigger in schema.get('triggers', []):
            await self._create_trigger(conn, trigger)

        # Create scheduled jobs
        for job in schema.get('scheduled_jobs', []):
            await self._create_scheduled_job(conn, job)
            
        # Update schema version
        await conn.execute(
            'INSERT INTO schema_version (version) VALUES ($1)',
            schema['version']
        )
        logger.info(f"Successfully created fresh schema version {schema['version']}")

    async def _apply_version_migrations(self, conn, schema: Dict[str, Any]) -> None:
        """Apply migrations for a specific version.
        
        Args:
            conn: Database connection
            schema: Schema definition for this version
        """
        # First create any new tables
        for table in schema.get('tables', []):
            await self._create_table(conn, table)
            
        # Add foreign keys and indexes
        for table in schema.get('tables', []):
            await self._add_constraints(conn, table)
            
        # Create standalone functions after tables exist
        for function in schema.get('functions', []):
            await self._create_function(conn, function)
            
        # Apply raw SQL migrations if any
        for migration in schema.get('migrations', []):
            try:
                await conn.execute(migration)
            except Exception as e:
                if 'already exists' not in str(e):
                    raise
                logger.debug(f"Skipping existing object: {str(e)}")
                
        # Create triggers last since they may depend on functions
        for trigger in schema.get('triggers', []):
            await self._create_trigger(conn, trigger)

        # Create scheduled jobs
        for job in schema.get('scheduled_jobs', []):
            await self._create_scheduled_job(conn, job)

    async def _create_scheduled_job(self, conn, job: Dict[str, Any]) -> None:
        """Create a scheduled job using CockroachDB Cloud syntax.
        
        Args:
            conn: Database connection
            job: Job definition dictionary with name, schedule, and sql
            
        Note:
            CockroachDB Cloud only supports specific schedule formats:
            - '@hourly'
            - '@daily'
            - '@weekly'
            - '@monthly'
            - '@yearly'
            - '@every <interval>' where interval is in the format '1h', '1d', etc.
        """
        try:
            # First try to pause any existing schedule with this name
            try:
                await conn.execute(f'''
                    ALTER SCHEDULE {job['name']} PAUSE;
                ''')
            except Exception:
                pass  # Schedule might not exist
            
            # Create the new schedule
            # Note: We use full_schedule_name to avoid name conflicts
            full_schedule_name = f"{job['name']}_v{self.current_version}"
            await conn.execute(f'''
                CREATE SCHEDULE {full_schedule_name}
                FOR {job['sql']}
                WHEN CURRENT_DATABASE = current_database()
                WITH SCHEDULE = '{job['schedule']}'
            ''')
            logger.info(f"Created scheduled job {full_schedule_name}")
        except Exception as e:
            if 'already exists' not in str(e):
                raise
            logger.debug(f"Schedule already exists: {str(e)}")

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
        try:
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
            
            # Add TTL options if specified
            options = []
            if 'options' in table:
                if 'ttl_expire_after' in table['options']:
                    options.extend([
                        f"ttl_expire_after = '{table['options']['ttl_expire_after']}'",
                        f"ttl_job_cron = '{table['options']['ttl_job_cron']}'"
                    ])
                    if 'ttl_select_statement' in table['options']:
                        options.append(
                            f"ttl_select_statement = '{table['options']['ttl_select_statement']}'"
                        )

            # Create table with options if any
            if options:
                await conn.execute(f'''
                    CREATE TABLE {table['name']} (
                        {table_def}
                    ) WITH (
                        {', '.join(options)}
                    )
                ''')
            else:
                await conn.execute(f'''
                    CREATE TABLE {table['name']} (
                        {table_def}
                    )
                ''')
            logger.info(f"Created table {table['name']}")
        except Exception as e:
            if 'already exists' not in str(e):
                raise
            logger.debug(f"Table {table['name']} already exists")
    
    async def _add_constraints(self, conn, table: Dict[str, Any]) -> None:
        """Add foreign keys and indexes to a table.
        
        Args:
            conn: Database connection
            table: Table definition dictionary
        """
        try:
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
                    where = f" WHERE {idx['where']}" if 'where' in idx else ''
                    await conn.execute(f'''
                        CREATE {unique}INDEX {idx['name']} 
                        ON {table['name']}({', '.join(idx['columns'])})
                        {where}
                    ''')
                    logger.info(f"Created index {idx['name']} on {table['name']}")
        except Exception as e:
            if 'already exists' not in str(e):
                raise
            logger.debug(f"Constraint or index already exists: {str(e)}")
            
    async def _create_trigger(self, conn, trigger: Dict[str, Any]) -> None:
        """Create a trigger function and trigger.
        
        Args:
            conn: Database connection
            trigger: Trigger definition dictionary
        """
        try:
            # Create function
            await conn.execute(f'''
                CREATE OR REPLACE FUNCTION {trigger['function_name']}()
                RETURNS TRIGGER
                AS $${trigger['function_body']}$$ 
                LANGUAGE plpgsql;
            ''')
            logger.info(f"Created trigger function {trigger['function_name']}")
            
            # Handle both 'event' and 'events' keys for backward compatibility
            events = trigger.get('events', [trigger.get('event')] if trigger.get('event') else [])
            if not events:
                raise DatabaseSchemaError(f"Trigger {trigger['name']} missing 'event' or 'events'")
            
            events_str = ' OR '.join(events)
            level = trigger.get('level', 'ROW')
            
            # Create trigger
            await conn.execute(f'''
                CREATE TRIGGER {trigger['name']}
                {trigger['timing']} {events_str} ON {trigger['table']}
                FOR EACH {level}
                EXECUTE FUNCTION {trigger['function_name']}();
            ''')
            logger.info(f"Created trigger {trigger['name']} on {trigger['table']}")
        except Exception as e:
            if 'already exists' not in str(e):
                raise
            logger.debug(f"Trigger or function already exists: {str(e)}") 