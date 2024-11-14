import os
import configparser
""" Load the environment variables """
from dotenv import load_dotenv

load_dotenv()

node_username = os.getenv('EVRMORE_NODE_USERNAME')
node_password = os.getenv('EVRMORE_NODE_PASSWORD')
node_host = os.getenv('EVRMORE_NODE_HOST')
node_port = os.getenv('EVRMORE_NODE_PORT')

""" Validate the settings 
    This function will validate the settings file and the environment variables
    and exit if there are any issues, below are the checks that are performed:

    1. Check if the settings file exists
    2. Check if the settings file is empty
    3. Check if the NODE_USERNAME and NODE_PASSWORD environment variables are set
    4. Check for the following keys in the settings file:
        a. Logging
            - log_file

"""
def validate_settings(settings, settings_file, logger):

    """ 1. Check if the settings file exists """
    if not os.path.exists(settings_file):
        logger.error(f"The settings file {settings_file} does not exist.")
        exit(1)
    
    """ 2. Check if the settings file is empty """
    if os.path.getsize(settings_file) == 0:
        logger.error(f"The settings file {settings_file} is empty.")
        exit(1)

    """ 3. Check if the NODE_USERNAME and NODE_PASSWORD environment variables are set """
    if not node_username or not node_password or not node_host or not node_port:
        logger.error("NODE_USERNAME, NODE_PASSWORD, NODE_HOST, and NODE_PORT environment variables must be set.")
        exit(1)

    """ 4. Check for the keys """

    # [Logging] *Optional*
    # log_file = None
    if 'Logging' in settings and 'log_file' in settings['Logging']:
        log_file = settings['Logging']['log_file']
        if log_file == 'None':
            log_file = None
    else:
        logger.warning("No log file specified in the settings file. No log file will be created.")
    
    # [Server] *Optional*
    # ip = 0.0.0.0
    if 'Server' in settings and 'ip' in settings['Server']:
        pass
    else:
        logger.warning("No ip specified in the settings file. Defaulting to 0.0.0.0.")

    # port = 8000
    if 'Server' in settings and 'port' in settings['Server']:
        pass
    else:
        logger.warning("No port specified in the settings file. Defaulting to 8000.")

    # Workers = 4
    if 'Server' in settings and 'workers' in settings['Server']:
        pass
    else:
        logger.warning("No workers specified in the settings file. Defaulting to 4.")
    
    """ Add more settings checks here if needed """


""" Gather the settings, validate them, and add the node username and password 
    to the settings under the 'Node' section then return the settings
"""
def gather_settings(settings_file, logger):

    """ Create a ConfigParser object """
    settings = configparser.ConfigParser()

    """ Read the settings file """
    settings.read(settings_file)

    """ Validate the settings """
    validate_settings(settings, settings_file, logger)

    """ Add the node username and password to the settings under the 'Node' section """
    if 'Node' not in settings:
        settings['Node'] = {}
        settings['Node']['username'] = node_username
        settings['Node']['password'] = node_password
        settings['Node']['host'] = node_host
        settings['Node']['port'] = node_port

    """ Return the settings """
    return settings