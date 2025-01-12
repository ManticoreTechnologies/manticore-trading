# Manticore Technologies LLC
# (c) 2024 
# Manticore Crypto Faucet
#       rpc.py 

import requests
from helper import create_logger, settings


# Initialize the logger
logger = create_logger()

# Configuration settings for connecting to the Evrmore node
host = settings["Node"]["host"]
url = f'http://{host}:{settings["Node"]["port"]}'
auth = (settings["Node"]["username"], settings["Node"]["password"])

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
            return result
    
    except requests.ConnectionError as connection_error:
        # Handle connection errors with the Evrmore node
        logger.critical(f"Unable to connect to Evrmore node at {url}. Is the node running?")
        raise requests.HTTPError(f"Unable to connect to Evrmore node at {url}. Is the node running?") from connection_error

def test_connection():
    """ Test the connection to the Evrmore node """
    try:
        send_command('getblockchaininfo', [])
        return True
    except Exception as e:
        return False
    



def get_address_balances(address):
    """ Get the balances of an address """
    balances = send_command("getaddressbalance", [{"addresses": [address]}, True])
    return balances

def get_asset_balance(address, assetName):
    """ Get the balance of an asset """
    balances = get_address_balances(address)
    for balance in balances:
        if balance['assetName'] == assetName:
            return balance['balance']
    return 0

def get_address_mempool(address, assets=True):
    """ Get the mempool of an address """
    mempool = send_command("getaddressmempool", [{"addresses": [address]}, assets])
    return mempool

def check_asset_confirming(address, assetName):
    """ Check if an asset is in the mempool for an address """
    mempool_info = get_address_mempool(address)
    for tx in mempool_info:
        if assetName == tx["assetName"]:
            return True
    return False

def check_refund_confirmed(txid):
    """ Check if a refund tx is confirmed """
    tx_info = send_command("gettransaction", [txid])
    return tx_info['confirmations'] > 0

def check_evr_confirming(address):
    """ Check if an evr is in the mempool for an address """
    mempool_info = get_address_mempool(address, assets=False)
    logger.debug(f"Mempool info: {mempool_info}")
    if len(mempool_info) > 0:
        return True
    return False