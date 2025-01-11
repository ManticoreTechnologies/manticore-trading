# Manticore Technologies LLC
# (c) 2024 
# Manticore Asset Explorer
#    helper.py
# 
#  This is a helper file for the Flask service
#  It will load the configuration and settings
#

# Import the configuration settings
import configparser
import re
settings = configparser.ConfigParser()
settings_file = 'settings.conf'

""" Create a logger """
import logging
import colorlog
import os

log_file=None

def create_logger(log_level="DEBUG"):
    logger = logging.getLogger(os.path.basename(__file__))
    


    # Set the logging level
    logger.setLevel(log_level)

    # Clear existing handlers if any
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a stream handler with color formatting
    ch = logging.StreamHandler()
    ch.setLevel(log_level)

    formatter = colorlog.ColoredFormatter(
        fmt=(
            "%(log_color)s%(asctime)s %(levelname)-8s %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        reset=True,
        log_colors={
            'INFO': 'green',
            'DEBUG': 'blue',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_white,bg_red',
        }
    )
    
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # Create a file handler
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    
    return logger
# Create the first logger
logger = create_logger(log_level="DEBUG")

""" Import settings.py :) """
from settings import gather_settings
settings = gather_settings(settings_file, logger)

# Remake the logger to use the new log file
logger = create_logger(settings['Logging']['log_level'])

""" Welcome message """
def welcome_message():
    logger.info("Manticore Asset Explorer")
    logger.info("Version 0.1.0")
    logger.info("(c) 2024 Manticore Technologies LLC")

welcome_message()

""" Log level message """
def log_level_message():
    log_level = settings['Logging']['log_level'] or 'DEBUG'
    log_message = "Logger initialized with {} level {}".format(log_level.lower(), log_level)
    
    if log_level == 'DEBUG':
        logger.debug(log_message)
    elif log_level == 'INFO':
        logger.info(log_message)
    elif log_level == 'WARNING':
        logger.warning(log_message)
    elif log_level == 'ERROR':
        logger.error(log_message)
    elif log_level == 'CRITICAL':
        logger.critical(log_message)
    
log_level_message()


""" Check password strength """
def check_password_strength(password):
    # Minimum length of 8 characters
    if len(password) < 8:
        return "Weak", "Password must be at least 8 characters long."

    # Check for uppercase letters
    if not re.search(r'[A-Z]', password):
        return "Weak", "Password must contain at least one uppercase letter."

    # Check for lowercase letters
    if not re.search(r'[a-z]', password):
        return "Weak", "Password must contain at least one lowercase letter."

    # Check for digits
    if not re.search(r'[0-9]', password):
        return "Weak", "Password must contain at least one digit."

    # Check for special characters
    if not re.search(r'[@$!%*?&#]', password):
        return "Weak", "Password must contain at least one special character (@, $, !, %, *, ?, &, or #)."

    # If all conditions are met
    return "Strong", "Password is strong."