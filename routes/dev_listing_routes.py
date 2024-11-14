# Manticore Technologies LLC
# (c) 2024 
# Manticore Asset Explorer
#    create_listing.py 


from utils import create_logger, config, load_map, check_password_strength
from flask import jsonify, request, send_file, abort
from startup import app, listing_manager
from datetime import datetime
from rpc import send_command
import bcrypt
import json
import uuid

logger = create_logger()

@app.route('/update_address', methods=['GET'])
def update_listing_address():
    # Get the listing ID and new address from the URL parameters
    listing_id = request.args.get('listing_id')
    new_address = request.args.get('new_address')

    # Validate inputs
    if not listing_id or not new_address:
        return jsonify({"error": "Both `listing_id` and `new_address` must be provided."}), 400

    # Validate the new address
    try:
        is_valid = send_command("validateaddress", [new_address])
    except Exception as e:
        logger.error(e)
        return jsonify({"error": f'{e}'})

    if not is_valid['isvalid']:
        logger.warning(f"{new_address} is not a valid Evrmore address.")
        return jsonify({"error": "Invalid new address"}), 400

    # Retrieve the existing listing
    listing_data = listing_manager.get_listing(listing_id)
    if not listing_data:
        return jsonify({"error": "Listing not found."}), 404

    # Update the listing address
    listing_data['listing_address'] = new_address

    # Save the updated listing
    listing_manager.save_listing(listing_data)

    # Return the updated listing data
    return jsonify(listing_data), 200

