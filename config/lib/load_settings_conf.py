"""Settings configuration loader module.

This module handles loading and parsing of the main settings.conf file which contains
general application settings, including the path to the Evrmore configuration directory.

The settings file uses INI format with a [DEFAULT] section containing key-value pairs.

Required settings:
    evrmore_root: Path to the Evrmore configuration directory
    db_url: Database connection URL (e.g., postgresql://user:pass@host:port/db)

Example settings.conf:
    [DEFAULT]
    evrmore_root = /home/user/.evrmore/
    db_url = postgresql://user:pass@host:port/db

Raises:
    SettingsError: If the settings file is missing, invalid, or missing required settings
"""
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Any, List

class ConfigValidationError:
    """Helper class to format configuration validation errors"""
    def __init__(self):
        self.missing: List[str] = []
        self.invalid_paths: List[str] = []
        self.missing_sections: List[str] = []
    
    def has_errors(self) -> bool:
        """Check if any errors exist"""
        return bool(self.missing or self.invalid_paths or self.missing_sections)
    
    def format_message(self) -> str:
        """Format error message in a clean, readable way"""
        messages = []
        
        if self.missing_sections:
            messages.append("Missing required sections:")
            messages.extend(f"  - {item}" for item in self.missing_sections)
            
        if self.missing:
            if messages:
                messages.append("")
            messages.append("Missing required settings:")
            messages.extend(f"  - {item}" for item in self.missing)
            
        if self.invalid_paths:
            if messages:
                messages.append("")
            messages.append("Invalid paths (directory does not exist):")
            messages.extend(f"  - {item}" for item in self.invalid_paths)
            
        return "\n".join(messages)

class SettingsError(Exception):
    """Raised when there are issues loading or parsing the settings configuration."""
    pass

def load_settings_conf(settings_path: str = ".") -> Dict[str, Any]:
    """Load and parse settings.conf file with strict validation
    
    Args:
        settings_path: Directory containing settings.conf
        
    Returns:
        Dictionary containing parsed settings
        
    Raises:
        SettingsError: If file not found, parsing fails, or validation fails
    """
    config_path = Path(settings_path) / 'settings.conf'
    
    if not config_path.exists():
        raise SettingsError(
            f"Settings file not found at: {config_path}\n"
            "Please create settings.conf based on examples/settings.conf.example"
        )
        
    try:
        parser = ConfigParser()
        parser.read(config_path)
        
        errors = ConfigValidationError()
        
        # Ensure DEFAULT section exists
        if 'DEFAULT' not in parser:
            errors.missing_sections.append('[DEFAULT]')
            raise SettingsError(
                "Settings Configuration Validation Failed\n\n" +
                errors.format_message()
            )
        
        # Get settings from DEFAULT section
        settings = dict(parser['DEFAULT'])
        
        # Validate required settings
        required_settings = ['evrmore_root', 'db_url']
        missing = [key for key in required_settings if key not in settings]
        
        if missing:
            errors.missing.extend(missing)
        
        # Only validate paths if we have all required settings
        if not missing:
            # Validate evrmore_root path exists
            evrmore_root = Path(settings['evrmore_root']).resolve()
            if not evrmore_root.exists():
                errors.invalid_paths.append(f"evrmore_root: {evrmore_root}")
            else:
                # Convert paths to absolute paths only if valid
                settings['evrmore_root'] = str(evrmore_root)
                
        if errors.has_errors():
            raise SettingsError(
                "Settings Configuration Validation Failed\n\n" +
                errors.format_message()
            )
            
        return settings
        
    except Exception as e:
        if isinstance(e, SettingsError):
            raise
        raise SettingsError(f"Error parsing settings.conf: {str(e)}")