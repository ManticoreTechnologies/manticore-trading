"""Configuration module for loading and managing application settings"""
from typing import Dict, Any, Optional
from .lib.load_evrmore_conf import load_evrmore_conf, EvrmoreConfigError
from .lib.load_settings_conf import load_settings_conf, SettingsError
import os
import configparser

__all__ = ['settings_conf', 'evrmore_conf', 'SettingsError', 'EvrmoreConfigError']

# Default settings
DEFAULTS = {
    'evrmore_root': os.path.expanduser('~/.evrmore'),
    'db_url': 'postgresql://root@localhost:26257/defaultdb?sslmode=disable',
    'min_confirmations': '6'  # Default to 6 confirmations for listing deposits
}

def load_config(config_path: Optional[str] = None) -> configparser.ConfigParser:
    """Load configuration from file.
    
    Args:
        config_path: Optional path to config file. If not provided,
                    will look for settings.conf in current directory.
    
    Returns:
        ConfigParser object with loaded settings
    """
    config = configparser.ConfigParser(defaults=DEFAULTS)
    
    if config_path:
        config.read(config_path)
    else:
        config.read('settings.conf')
    
    return config

try:
    # Load settings first
    settings_conf: Dict[str, Any] = load_settings_conf()
    
    # Use settings to load Evrmore config
    evrmore_conf: Dict[str, Any] = load_evrmore_conf(settings_conf['evrmore_root'])
    
except (SettingsError, EvrmoreConfigError) as e:
    # Re-raise the error but provide more context
    raise type(e)(
        f"Configuration Error\n"
        "=================\n\n"
        f"{str(e)}\n\n"
        "Please ensure both settings.conf and evrmore.conf are properly configured.\n"
        "See config/README.md for configuration requirements."
    )