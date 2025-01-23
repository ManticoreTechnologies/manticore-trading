# Configuration Module

This module handles the loading and management of application configuration settings for the Manticore Trading system.

## Quick Setup Guide

1. Create `settings.conf` in the project root directory:
   ```bash
   cp examples/settings.conf.example settings.conf
   ```
   Then edit `settings.conf` and set your configuration:
   ```ini
   [DEFAULT]
   evrmore_root = /home/your_user/.evrmore/  # Path to your Evrmore config directory
   db_url = postgresql://user:pass@host:port/db  # Database connection URL
   ```

2. Configure your Evrmore node (`evrmore.conf`):
   - Location: Inside the directory specified by `evrmore_root`
   - If starting fresh, copy the example:
     ```bash
     cp examples/evrmore.conf.example ~/.evrmore/evrmore.conf
     ```
   - Edit the following required settings:
     ```ini
     # Core Settings (Required)
     server=1
     rpcuser=your_username          # Choose a secure username
     rpcpassword=your_password      # Choose a secure password
     rpcport=8819                   # Default port, change if needed
     txindex=1
     addressindex=1

     # ZMQ Settings (Required) - Default ports shown
     zmqpubhashtx=tcp://127.0.0.1:2936
     zmqpubrawblock=tcp://127.0.0.1:2935
     zmqpubsequence=tcp://127.0.0.1:2934
     zmqpubrawtx=tcp://127.0.0.1:29332
     zmqpubhashblock=tcp://127.0.0.1:29333
     ```

3. Verify your configuration:
   ```bash
   python -m config
   ```
   This will validate your settings and show any missing or invalid configurations.

## Modifying Configuration Requirements

To modify what settings are required by the config module, you'll need to update the following files:

### Adding/Removing Settings Requirements

1. For `settings.conf` requirements:
   - Edit `config/lib/load_settings_conf.py`
   - Modify the `required_settings` list:
     ```python
     # Add or remove settings from this list
     required_settings = ['evrmore_root', 'db_url']
     ```

2. For `evrmore.conf` requirements:
   - Edit `config/lib/load_evrmore_conf.py`
   - Modify the `required_settings` dictionary:
     ```python
     required_settings = {
         'rpcuser': str,          # Add/remove settings and their expected types
         'rpcpassword': str,
         'rpcport': int,
         'server': bool,
         'txindex': bool,
         'addressindex': bool
     }
     ```
   - For ZMQ settings, modify the `required_zmq` list in `validate_zmq_settings()`:
     ```python
     required_zmq = [
         'zmqpubhashtx',          # Add/remove required ZMQ endpoints
         'zmqpubrawblock',
         'zmqpubsequence',
         # ...
     ]
     ```

3. Update the documentation:
   - Update this README
   - Update the example files in `examples/`
   - Update docstrings in the respective modules

### Adding New Types of Validation

1. To add new validation rules:
   - Add new fields to the `ConfigValidationError` class
   - Add validation logic in the respective loader
   - Update error formatting in `format_message()`

Example:
```python
class ConfigValidationError:
    def __init__(self):
        self.missing: List[str] = []
        self.invalid: List[str] = []
        # Add new error types here
        self.custom_validation: List[str] = []
```

## Required Configuration

The application requires specific configurations to be present and valid before it can start. If any required configuration is missing or invalid, the application will fail to start with a detailed error message.

### settings.conf Requirements
Located in the root directory:
```ini
[DEFAULT]
# REQUIRED: Full path to Evrmore configuration directory
evrmore_root = /path/to/evrmore/directory/

# REQUIRED: Database connection URL
db_url = postgresql://user:pass@host:port/db
```

### evrmore.conf Requirements
Located in the directory specified by `evrmore_root`:
```ini
# REQUIRED Core Settings
server=1                  # Must be enabled for RPC functionality
rpcuser=your_username    # RPC authentication username
rpcpassword=your_pass    # RPC authentication password
rpcport=8819            # Port for RPC connections
txindex=1               # Must be enabled for transaction indexing
addressindex=1          # Must be enabled for address indexing

# REQUIRED ZMQ Settings
zmqpubhashtx=tcp://127.0.0.1:2936
zmqpubrawblock=tcp://127.0.0.1:2935
zmqpubsequence=tcp://127.0.0.1:2934
zmqpubrawtx=tcp://127.0.0.1:29332
zmqpubhashblock=tcp://127.0.0.1:29333

# Recommended Settings
assetindex=1            # Enable asset indexing
timestampindex=1        # Enable timestamp indexing
spentindex=1           # Enable spent transaction indexing
```

## Configuration Validation

The module performs strict validation of both configuration files at startup:

1. Verifies existence of both configuration files
2. Checks all required settings are present
3. Validates setting types (e.g., integers, booleans, URLs)
4. Verifies ZMQ endpoint formats
5. Ensures server mode and indexing are enabled

If any validation fails, the application will immediately exit with a detailed error message indicating what needs to be fixed.

## Usage

```python
from config import settings_conf, evrmore_conf

# Configuration is automatically validated on import
# If any required settings are missing, an error will be raised

# Access settings
evrmore_root = settings_conf['evrmore_root']

# Access Evrmore configuration
rpc_port = evrmore_conf['rpcport']
```

## Error Handling

The module provides two custom exception types:
- `SettingsError`: Raised for issues with settings.conf
- `EvrmoreConfigError`: Raised for issues with evrmore.conf

Example error messages:
```
SettingsError: Required setting 'evrmore_root' not found in settings.conf

EvrmoreConfigError: Configuration validation failed:
- Missing required settings: rpcuser, rpcpassword
- Invalid setting types: rpcport (expected int)
- Missing required ZMQ endpoints: zmqpubhashtx, zmqpubrawblock
```

## Module Structure

- `__init__.py`: Main module interface and validation
- `__main__.py`: CLI tool for testing configuration
- `lib/`
  - `load_settings_conf.py`: Settings file loader and validator
  - `load_evrmore_conf.py`: Evrmore configuration loader and validator

## Command Line Interface

The module includes a command-line interface for testing configuration loading:

```bash
python -m config
```

This will display the currently loaded configuration and verify all required settings are present.

## Example Files

Example configuration files are provided in the `examples/` directory:
- `settings.conf.example`
- `evrmore.conf.example`