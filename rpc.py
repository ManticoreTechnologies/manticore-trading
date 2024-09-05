# Manticore Technologies LLC
# (c) 2024 
# Manticore Crypto Faucet
#       rpc.py 

import requests
from utils import create_logger, config


# Initialize the logger
logger = create_logger()

# Configuration settings for connecting to the Evrmore node
host = config["Node"]["host"]
url = f'http://{host}:{config["Node"]["port"]}'
auth = (config["Node"]["user"], config["Node"]["password"])

class AuthenticationError(Exception):
    """Custom exception for handling authentication errors."""
    pass

def send_command(command, params=[]):
    """
    Sends a JSON-RPC command to the Evrmore node and handles the response.

    Args:
        command (str): The command to be executed on the Evrmore node.
        params (list): A list of parameters for the command.

    Returns:
        dict: The result of the command if successful.

    Raises:
        AuthenticationError: If authentication with the Evrmore node fails.
        requests.HTTPError: If there is a connection error with the Evrmore node.
    """
    try:
        logger.debug(f'Sending command: "{command}" to host: {host} with params: {params}')
        
        # Prepare the JSON-RPC payload and headers
        payload = {"jsonrpc": "2.0", "id": "curltext", "method": command, "params": params}
        headers = {"Content-Type": "text/plain"}
        
        # Send the request to the Evrmore node
        response = requests.post(url, json=payload, headers=headers, auth=auth)
        
        # Check for authentication failure (HTTP status code 401)
        if response.status_code == 401:
            logger.error("Authentication failed: Invalid credentials provided for the Evrmore node.")
            raise AuthenticationError("Authentication failed: Invalid credentials provided for the Evrmore node.")
        
        # Parse the JSON response from the node
        response_json = response.json()
        
        # Handle errors returned by the node
        if 'error' in response_json and response_json['error']: 
            error = response_json['error']
            message = error['message']
            logger.error(f"Node replied with error: {message}")
        else:
            # Log the length of the result and return it
            result = response_json.get('result')
            if result is not None:
                logger.debug(f"Node replied with result of length {len(str(result))}")
            return result
    
    except requests.ConnectionError as connection_error:
        # Handle connection errors with the Evrmore node
        logger.critical(f"Unable to connect to Evrmore node at {url}. Is the node running?")
        raise requests.HTTPError(f"Unable to connect to Evrmore node at {url}. Is the node running?") from connection_error
