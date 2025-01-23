"""Evrmore configuration loader module.

This module handles loading and parsing of the Evrmore node's configuration file (evrmore.conf).
The configuration file contains settings for the Evrmore node, including network settings,
RPC configuration, and various blockchain indexing options.

The configuration file uses a simple key=value format, with one setting per line.
Comments start with #.

Required settings:
    - server=1 (Required for RPC functionality)
    - rpcuser (RPC authentication username)
    - rpcpassword (RPC authentication password)
    - rpcport (Port for RPC connections)

Optional but recommended settings:
    - txindex=1 (Enable transaction indexing)
    - addressindex=1 (Enable address indexing)
    - assetindex=1 (Enable asset indexing)
    - timestampindex=1 (Enable timestamp indexing)
    - spentindex=1 (Enable spent transaction indexing)

Example evrmore.conf:
    server=1
    rpcuser=user
    rpcpassword=password
    rpcport=8819
    txindex=1
    
Raises:
    EvrmoreConfigError: If the configuration file is missing, invalid, or missing required settings
"""
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Any, Union, List
import logging

logger = logging.getLogger(__name__)

class ConfigValidationError:
    """Helper class to format configuration validation errors"""
    def __init__(self):
        self.missing: List[str] = []
        self.invalid: List[str] = []
        self.disabled: List[str] = []
        self.invalid_zmq: List[str] = []
    
    def has_errors(self) -> bool:
        """Check if any errors exist"""
        return bool(self.missing or self.invalid or self.disabled or self.invalid_zmq)
    
    def format_message(self) -> str:
        """Format error message in a clean, readable way"""
        messages = []
        
        if self.missing:
            messages.append("Missing required settings:")
            messages.extend(f"  - {item}" for item in self.missing)
            
        if self.invalid:
            if messages:
                messages.append("")
            messages.append("Invalid setting types:")
            messages.extend(f"  - {item}" for item in self.invalid)
            
        if self.disabled:
            if messages:
                messages.append("")
            messages.append("Required settings that must be enabled (set to 1):")
            messages.extend(f"  - {item}" for item in self.disabled)
            
        if self.invalid_zmq:
            if messages:
                messages.append("")
            messages.append("Invalid ZMQ endpoints (must start with tcp://):")
            messages.extend(f"  - {item}" for item in self.invalid_zmq)
            
        return "\n".join(messages)

class EvrmoreConfigError(Exception):
    """Raised when there's an error loading Evrmore configuration"""
    pass

def parse_value(value: str) -> Union[str, int, float, bool]:
    """Parse configuration values to appropriate types"""
    # Handle booleans
    if value.lower() in ('true', '1', 'yes', 'on'):
        return True
    if value.lower() in ('false', '0', 'no', 'off'):
        return False
        
    # Handle numbers
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        return value

def validate_zmq_settings(config: Dict[str, Any], errors: ConfigValidationError) -> None:
    """Validate ZMQ settings are properly configured"""
    required_zmq = [
        'zmqpubhashtx',
        'zmqpubrawblock',
        'zmqpubsequence',
        'zmqpubrawtx',
        'zmqpubhashblock'
    ]
    
    # Check for missing ZMQ settings
    missing_zmq = [key for key in required_zmq if key not in config]
    if missing_zmq:
        errors.missing.extend(missing_zmq)
        
    # Validate ZMQ URLs
    for key in required_zmq:
        if key in config:
            value = config[key]
            if not value.startswith('tcp://'):
                errors.invalid_zmq.append(f"{key}: {value}")

def load_evrmore_conf(evrmore_root: str) -> Dict[str, Any]:
    """
    Load and parse evrmore.conf file with strict validation
    
    Args:
        evrmore_root: Path to Evrmore configuration directory
        
    Returns:
        Dictionary containing parsed Evrmore settings
        
    Raises:
        EvrmoreConfigError: If file not found, parsing fails, or validation fails
    """
    config_path = Path(evrmore_root) / 'evrmore.conf'
    
    if not config_path.exists():
        raise EvrmoreConfigError(
            f"Evrmore configuration file not found at: {config_path}\n"
            "Please ensure evrmore.conf exists in your Evrmore configuration directory"
        )
        
    try:
        # Read the file manually first to handle the non-standard format
        with open(config_path, 'r') as f:
            lines = f.readlines()
            
        config = {}
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                try:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    config[key] = parse_value(value)
                except ValueError:
                    logger.warning(f"Skipping invalid line in evrmore.conf: {line}")
                    continue
        
        errors = ConfigValidationError()
                    
        # Validate required settings with types
        required_settings = {
            'rpcuser': str,
            'rpcpassword': str,
            'rpcport': int,
            'server': bool,
            'txindex': bool,
            'addressindex': bool
        }
        
        for key, expected_type in required_settings.items():
            if key not in config:
                errors.missing.append(key)
            elif not isinstance(config[key], expected_type):
                errors.invalid.append(f"{key} (expected {expected_type.__name__})")
            elif expected_type == bool and not config[key]:
                errors.disabled.append(key)
                
        # Validate ZMQ settings
        validate_zmq_settings(config, errors)
            
        if errors.has_errors():
            raise EvrmoreConfigError(
                "Evrmore Configuration Validation Failed\n\n" + 
                errors.format_message()
            )
            
        return config
        
    except Exception as e:
        if isinstance(e, EvrmoreConfigError):
            raise
        raise EvrmoreConfigError(f"Error parsing evrmore.conf: {str(e)}")

