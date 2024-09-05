# Manticore Technologies LLC
# (c) 2024 
# Manticore IPFS Mirror
#       utils.py 




import json
import re
import logging
import colorlog
import os

def create_logger():
    logger = logging.getLogger(os.path.basename(__file__))
    
    try:
        log_level = config['General']['log_level']
    except KeyError:
        raise KeyError("The 'log_level' setting is missing in the 'General' section of the configuration.")
    
    try:
        log_file = config['Logging']['log_file']
    except KeyError:
        raise KeyError("The 'log_file' setting is missing in the 'Logging' section of the configuration.")

    # Set the logging level
    logger.setLevel(log_level)

    # Clear existing handlers if any
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a stream handler with color formatting
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    formatter = colorlog.ColoredFormatter(
        fmt=(
            "%(log_color)s%(asctime)s - %(name)-15s - %(levelname)-8s - %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )
    
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # Create a file handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(log_level)
    logger.addHandler(fh)
    
    return logger
# Arguments #
import argparse

def parse_args():
    # Get the logging level argument
    parser = argparse.ArgumentParser(
        prog='Manticore Crypto Faucet',
        description='This cryptocurrency faucet is designed for Evrmore and Evrmore assets.',
        epilog='Manticore Technologies LLC'
    )
    parser.add_argument('--log-level', 
                        choices=['DEBUG', 'WARNING', 'CRITICAL', 'INFO', 'ERROR'], 
                        default='CRITICAL', 
                        help='Set the logging level (default: INFO)')

    return parser.parse_args()

# Settings #
import configparser
settings = configparser.ConfigParser()
settings.read('settings.conf')
config = configparser.ConfigParser()
config.read(settings['General']['config_path'])

# Welcome #
welcome_message =(
        "\n"
        "========================================\n"
        "        MANTICORE Trading Service       \n"
        "========================================\n"
        "  (c) 2024 Manticore Technologies LLC   \n"
        "----------------------------------------\n"
        "Welcome to the Manticore Trading Service\n"
        "This service is designed to facilitate  \n"
        "trading of Evrmore assets.              \n"
        "----------------------------------------\n"
)
def save_json(data, file_path):
    """
    Saves the given data to the specified file path in JSON format.

    Parameters:
    data (dict or list): The data to be saved in JSON format.
    file_path (str): The path to the file where the data will be saved.
    """
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)
        print(f"Data saved to {file_path}")

# Cache #
def initialize_directories():
    directories = ['./data/images', './data/maps']

    # Create directories if they don't exist
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Directory '{directory}' created.")
        else:
            print(f"Directory '{directory}' already exists.")



def save_maps(maps):
    """
    Saves the given maps to their respective file paths.

    Parameters:
    maps (list of tuples): A list where each tuple contains a map (dictionary) and the corresponding file path.
    """
    for map_data, file_path in maps:
        with open(file_path, 'w') as file:
            json.dump(map_data, file, indent=4)
            print(f"Saved map to {file_path}")

def load_maps(map_paths):
    """
    Loads the maps from the given file paths into memory.

    Parameters:
    map_paths (list of tuples): A list where each tuple contains a variable name and the corresponding file path.

    Returns:
    dict: A dictionary with variable names as keys and loaded maps as values.
    """
    loaded_maps = {}
    for map_name, file_path in map_paths:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                loaded_maps[map_name] = json.load(file)
                print(f"Loaded map '{map_name}' from {file_path}")
        else:
            print(f"File '{file_path}' does not exist. Map '{map_name}' not loaded.")
            loaded_maps[map_name] = {}
    return loaded_maps
def load_map(map_name):
    """
    Loads the maps from the given file paths into memory.

    Parameters:
    map_paths (list of tuples): A list where each tuple contains a variable name and the corresponding file path.

    Returns:
    dict: A dictionary with variable names as keys and loaded maps as values.
    """
    if os.path.exists(f"./data/maps/{map_name}.json"):
        with open(f"./data/maps/{map_name}.json", 'r') as file:
            return json.load(file)
    else:
        print(f"File '{map_name}' does not exist. Map '{map_name}' not loaded.")
        return {}


# Download image from local ipfs daemon
import requests
import time
def download_image(ipfs_hash):
    image_path = os.path.join(f"./data/images/{ipfs_hash}.png")
    
    # Return if already cached
    if os.path.exists(image_path): 
        return

    # Try downloading the image
    try:
        response = requests.get(f"http://localhost:8080/ipfs/{ipfs_hash}", stream=True, timeout=10)
        response.raise_for_status()
        
        with open(image_path, 'wb') as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)
        
        #print(f"Downloaded image for IPFS hash {ipfs_hash} from {gateway}")
        time.sleep(2)
        return
    except (requests.RequestException, requests.Timeout) as e:
        pass
        print(f"Failed to download image for IPFS hash {ipfs_hash}")


        import re

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