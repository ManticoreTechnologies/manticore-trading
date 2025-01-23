"""Configuration module for loading and managing application settings"""
from typing import Dict, Any
from .lib.load_evrmore_conf import load_evrmore_conf, EvrmoreConfigError
from .lib.load_settings_conf import load_settings_conf, SettingsError

__all__ = ['settings_conf', 'evrmore_conf', 'SettingsError', 'EvrmoreConfigError']

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