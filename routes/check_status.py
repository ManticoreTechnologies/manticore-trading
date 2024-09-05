# Manticore Technologies LLC
# (c) 2024 
# Manticore Asset Explorer
#       check_status.py 

from startup import app
from rpc import send_command
from utils import create_logger, config, load_map
from flask import jsonify, request, send_file, abort
import re
import math
import os
import json
import uuid
from datetime import datetime
import bcrypt

@app.route('/status/<listing_id>', methods=['GET'])
def check_status(listing_id):
    """
    Check the status of a listing, including order status, confirmations, and other relevant details.
    """
    listing_file_path = os.path.join('./data', f"{listing_id}.json")
    
    if not os.path.exists(listing_file_path):
        return "Listing not found.", 404
    
    with open(listing_file_path, 'r') as listing_file:
        listing_data = json.load(listing_file)
    
    # Default response data
    response_data = {
        "listing_id": listing_id,
        "order_status": listing_data.get("order_status", "UNKNOWN"),
        "confirmations": listing_data.get("confirmations", 0),
        "listing_address": listing_data.get("listing_address", ""),
        "remaining_quantity": listing_data.get("remaining_quantity", 0),
        "message": "Order status is being tracked."
    }

    # Check the balance and mempool for the latest status
    if listing_data.get("order_status") == "PENDING" or listing_data.get("order_status") == "CONFIRMING":
        listing_address = listing_data["listing_address"]
        
        # Check the balance for the listing address
        try:
            balance_info = send_command('getaddressbalance', [{"addresses": [listing_address]}, True])
        except Exception as e:
            logger.error(e)

        print(f"Balance info for {listing_address}: {balance_info}")
        
        # Check if the desired asset has been received
        received_asset = False
        desired_asset = listing_data.get("asset_name")
        confirmations = 0

        if balance_info:
            for asset in balance_info:
                print(asset)
                if asset["assetName"] == desired_asset and asset["received"] > 0:
                    received_asset = True
                    confirmations = asset.get("confirmations", 0)
                    break
        
        if received_asset:
            # Update order status to COMPLETE
            listing_data["order_status"] = "COMPLETE"
            listing_data["confirmations"] = confirmations
            response_data["order_status"] = "COMPLETE"
            response_data["confirmations"] = confirmations
            response_data["message"] = "Order has been completed with sufficient confirmations."
        else:
            # Check the mempool for transactions related to the listing address
            try:
                mempool_info = send_command('getaddressmempool', [{"addresses": [listing_data['listing_address']]}, True])
            except Exception as e:
                logger.error(e)
                
            print(f"Mempool info for {listing_address}: {mempool_info}")

            in_mempool = False
            if mempool_info:
                for tx in mempool_info:
                    if tx["assetName"] == desired_asset:
                        in_mempool = True
                        confirmations = 0
                        break

            if in_mempool:
                listing_data["order_status"] = "CONFIRMING"
                listing_data["confirmations"] = confirmations
                response_data["order_status"] = "CONFIRMING"
                response_data["confirmations"] = confirmations
                response_data["message"] = "Order is currently in the mempool and awaiting confirmation."
            else:
                response_data["message"] = "Order is still pending."

        # Save the updated listing data
        with open(listing_file_path, 'w') as listing_file:
            json.dump(listing_data, listing_file, indent=4)

    return jsonify(response_data)