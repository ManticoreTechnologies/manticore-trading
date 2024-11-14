from startup import app, listing_manager
from rpc import send_command
from flask import jsonify, request, abort
from utils import create_logger
import bcrypt
import logging
import redis

# Set up logging
logger = create_logger()

@app.route('/manage', methods=['POST'])
def manage_listing():
    """
    Manage a listing by providing the listing ID, password, and action.
    Possible actions include canceling the listing, updating the price, description, or quantity,
    and refunding the surplus.
    """
    logger.debug("Received request to manage listing.")

    # Get the post body
    data = request.json

    # Get the listing ID
    listing_id = data.get('listing_id')
    
    # 
    password = data.get('password')
    action = data.get('action', None)

    logger.debug(f"Action: {action}, Listing ID: {listing_id}")

    # Validate inputs
    if not listing_id or not password:
        logger.warning("Listing ID or password missing.")
        return jsonify({"message": "Listing ID and password are required."}), 400

    # Load the listing data
    listing_data = listing_manager.get_listing(listing_id)

    if not listing_data:
        logger.error(f"Listing not found: {listing_id}")
        return jsonify({"message": "Listing not found."}), 404

    # Validate password
    if not bcrypt.checkpw(password.encode('utf-8'), listing_data['password_hash'].encode('utf-8')):
        logger.warning("Invalid password attempt.")
        return jsonify({"message": "Invalid password."}), 403

    # Handle actions
    if action == 'fetch':
        logger.debug(f"Fetching data for listing {listing_id}")
        return jsonify(listing_data), 200

    if action == 'update':
        logger.debug(f"Updating listing {listing_id}")
        if 'unit_price' in data:
            new_price = data['unit_price']
            listing_manager.update_listing_field(listing_id, 'unit_price', new_price)
            logger.debug(f"Updated unit price: {new_price}")

        if 'description' in data:
            new_description = data['description']
            listing_manager.update_listing_field(listing_id, 'description', new_description)
            logger.debug(f"Updated description: {new_description}")

        if 'listing_status' in data:
            new_status = data['listing_status']
            listing_manager.update_listing_field(listing_id, 'listing_status', new_status)
            logger.debug(f"Updated listing status: {new_status}")

        return jsonify({"message": "Listing updated successfully."}), 200

    if action == 'refund':
        if listing_data['listing_status'] == "REFUNDING":
            return jsonify({"message": "This listing is already processing a refund. Please wait."}), 400

        logger.debug(f"Processing refund for listing {listing_id}")
        # Change the listing status to REFUNDING
        listing_balance = send_command("getaddressbalance", [{"addresses": [listing_data["listing_address"]]}, True])
        if listing_balance == []:
            return jsonify({"message": "Listing balance is zero. Unable to process refund."}), 400
            
        for asset in listing_balance:
            if asset['assetName'] == listing_data['asset_name']:
                try:
                    refund_balance = asset['balance'] / 100000000
                    if refund_balance == 0:
                        return jsonify({"message": "Listing balance is zero. Unable to process refund."}), 400
                    refund_txid = send_command("transferfromaddress", [listing_data['asset_name'], listing_data['listing_address'], refund_balance, listing_data['payout_address']])                
                    listing_manager.update_listing_field(listing_id, 'listing_status', 'REFUNDING')
                    listing_manager.update_listing_field(listing_id, 'refund_txid', f"{refund_txid[0]}")
                    listing_manager.update_listing_field(listing_id, 'remaining_quantity', 0)
                    return jsonify({"message": "Refund process started.", "listing_id": listing_id, "refund_txid": f"{refund_txid[0]}"}), 200
                except Exception as e:
                    return jsonify({"message": "The server encountered an error while processing this refund. Please try again in a few minutes.", "error": f"{e}"}), 400

    if action == 'cancel':
        logger.debug(f"Cancelling listing {listing_id}")
        if listing_data['listing_status'] == "REFUNDING":
            return jsonify({"message": "This listing is currently processing a refund. Please wait to cancel."}), 400

        # Check if listing has a balance greater than 0
        listing_balance = send_command("getaddressbalance", [{"addresses": [listing_data["listing_address"]]}, True])
        for asset in listing_balance:
            if asset['assetName'] == listing_data['asset_name']:
                balance = asset['balance']
                if balance > 0:
                    logger.warning(f"Cannot cancel listing {listing_id} because it has a balance greater than 0. User must refund first.")
                    return jsonify({"message": "Cannot cancel listing because it has a balance greater than 0. Please refund the balance before canceling."}), 400

        # Change the listing status to CANCELED if balance is 0
        listing_manager.update_listing_field(listing_id, 'listing_status', 'CANCELED')
        logger.debug(f"Listing {listing_id} canceled successfully.")
        return jsonify({"message": "Listing canceled successfully.", "listing_id": listing_id}), 200

    logger.warning("Invalid action specified.")
    return jsonify({"message": "Invalid action."}), 400

@app.route('/delete/<listing_id>', methods=['DELETE'])
def delete_listing(listing_id):
    """
    Delete a listing by its ID.
    """
    logger.debug(f"Deleting listing {listing_id}")

    listing_data = listing_manager.get_listing(listing_id)
    if not listing_data:
        logger.error(f"Listing not found: {listing_id}")
        return jsonify({"message": "Listing not found."}), 404

    # Remove the listing from Redis
    listing_manager.delete_listing(listing_id)
    logger.debug(f"Listing {listing_id} deleted successfully.")

    return jsonify({"message": f"Listing {listing_id} deleted successfully."}), 200
