"""Database module exceptions."""

class DatabaseError(Exception):
    """Base exception for database errors."""
    pass

class DatabaseConnectionError(DatabaseError):
    """Raised when there are connection-related issues."""
    pass

class DatabaseSchemaError(DatabaseError):
    """Raised when there are schema validation or migration issues."""
    pass

class DatabaseQueryError(DatabaseError):
    """Raised when there are query execution errors."""
    pass

class DatabasePoolError(DatabaseError):
    """Raised when there are connection pool issues."""
    pass 