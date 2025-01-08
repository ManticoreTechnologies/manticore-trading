from datetime import datetime
import json
import time
import uuid

import bcrypt
from start_server import server
from helper import check_password_strength, logger
from rpc import send_command
from flask import jsonify, request
import Database.Listings
import Database.Orders

if "ipfs_hash" not in Database.Listings.get_all_columns():
    logger.debug("Adding ipfs_hash column to the database")
    Database.Listings.add_ipfs_hash_column()



def calculate_payment_amount(listing_id, quantity):

    listing_data = Database.Listings.get_listing(listing_id)
    if not listing_data:
        logger.error(f"Listing not found: {listing_id}")
        return jsonify({"message": "Listing not found."}), 404

    # Check if listing is active
    if listing_data['listing_status'] != "ACTIVE":
        logger.warning(f"Listing {listing_id} is inactive.")
        return jsonify({"message": "Listing is not active."}), 400

    # Calculate available balance based only on remaining_quantity
    available_balance = float(listing_data['remaining_quantity'])

    # Ensure the requested quantity does not exceed the available balance
    if quantity > available_balance:
        logger.warning(f"Requested quantity exceeds available balance for listing {listing_id}.")
        return jsonify({"message": "Requested quantity exceeds available balance."}), 400

    # Calculate the payment amount
    unit_price = float(listing_data['unit_price'])
    return (unit_price * quantity) / 100000000

""" Get all the listings """
@server.route('/listings', methods=['GET'])
def listings():
    listings = Database.Listings.get_all_listings()
    for listing in listings:
            print(listing)
    return jsonify(listings), 200

""" Place an order """
@server.route('/place_order', methods=['POST'])
def place_order():
    """
    Place an order by creating a new bill/invoice with a unique address for payment.
    The order will have an expiration time to prevent over-committing the inventory.

    An order will have a dict of listing ids and quantities
    """
    logger.debug("Received request to place a new order.")

    """ Expire any pending order past their expiration time """
    Database.Orders.check_all_expired()

    data = request.json
    listing_id = data.get('listing_id')
    logger.debug(f"Listing ID: {listing_id}")
    # Enforce listing_id as a list
    if isinstance(listing_id, str):
        listing_id = [listing_id]
    logger.debug(f"Listing ID type: {type(listing_id)}")
    quantity = data.get('quantity')
    payout_address = data.get('payout_address')  # New parameter
    logger.debug(f"Listing ID: {listing_id}, Quantity: {quantity}, Payout Address: {payout_address}")
    
    # Validate inputs
    if not listing_id or not quantity or not payout_address:
        logger.warning("quantity, or payout address missing.")
        return jsonify({"message": "Listing ID, quantity, and payout address are required."}), 400

    # Validate the payout address
    try:
        validation_response = send_command('validateaddress', [payout_address])
        if not validation_response.get('isvalid'):
            logger.warning(f"Invalid payout address: {payout_address}")
            return jsonify({"message": "Invalid payout address."}), 400
        logger.debug(f"Payout address {payout_address} is valid.")
    except Exception as e:
        logger.error(f"Error validating payout address: {str(e)}")
        return jsonify({"message": "Error validating payout address."}), 500

    # Fetch listing data, this can be a string or a list of ids. 
    # Check if listing_id is a string or a list
    payment_amount = 0
    if isinstance(listing_id, str):
        # Make sure quantity is also a string
        if isinstance(quantity, str):
            payment_amount = calculate_payment_amount(listing_id, quantity)
        else:
            logger.error(f"Invalid quantity type: {type(quantity)}")
            return jsonify({"message": "Quantity type must match listing ID type."}), 400
    elif isinstance(listing_id, list):
        # Make sure quantity is also a list of same length
        if isinstance(quantity, list) and len(quantity) == len(listing_id): 
            for i in range(len(listing_id)):
                payment_amount += calculate_payment_amount(listing_id[i], quantity[i])
        else:
            logger.error(f"Invalid quantity type: {type(quantity)}")
            return jsonify({"message": "Quantity type must match listing ID type."}), 400
    else:
        logger.error(f"Invalid listing ID type: {type(listing_id)}")
        return jsonify({"message": "Invalid listing ID type."}), 400
    

    fee = payment_amount * 0.005  # Calculate the 0.5% fee
    total_payment_amount = payment_amount + fee  # Add the fee to the payment amount
    logger.debug(f"Calculated payment amount: {payment_amount}, Fee: {fee}, Total Payment Amount: {total_payment_amount}")

    order_id, payment_address, expiration_time = Database.Orders.add_order(listing_id, quantity, payout_address, total_payment_amount, fee)
    
    if not order_id:
        logger.error(f"Failed to add order to the database.")
        return jsonify({"message": "Failed to add order to the database."}), 500

    logger.debug(f"Added order to the database with ID: {order_id}")

    return jsonify({
        "message": "Order placed successfully.",
        "id": order_id,
        "listing_ids": listing_id,
        "quantities": quantity,
        "payment_address": payment_address,
        "payment_amount": total_payment_amount,  # Include the total payment amount in the response
        "payout_address": payout_address,  # Include the payout address in the response
        "fee": fee,  # Include the fee in the response if needed
        "expiration_time": expiration_time,
        "status": "PENDING"
    }), 201

""" Get an invoice """
@server.route('/get_invoice/<order_id>', methods=['GET'])
def get_invoice(order_id):
    """
    Retrieve an invoice by its order_id.
    """
    logger.debug(f"Received request to retrieve invoice with order_id: {order_id}")

    order = Database.Orders.get_order(order_id)
    if order is None:
        return jsonify({"message": "Order not found.", "status": "FAILED"}), 404
    logger.debug(f"Retrieved order from the database with ID: {order}")
    return jsonify(order), 200

""" Create a listing """
@server.route('/list', methods=['POST'])
def create_listing():

    # The listee shall provide:
    #   A. Full Asset Name
    #   B. Short Asset Description (optional)
    #   C. Price in satoshis per unit
    #   D. A payout address for refunds and payments
    #   E. Tags for filtering the asset (optional)
    #   F. A password to secure the listing

    # ---------------------------------------------------- #
    
    # A. Asset Name
    # Get the asset name provided
    try:
        asset_name = request.json.get('name')
    except Exception as e:
        return jsonify("Provided JSON body is invalid. Please check the body for syntax errors.", 400)

    # Validate the asset name
    if not asset_name: 
        return jsonify("Parameter `name` was not provided in the body. Please provide a valid `name` of an asset.", 400)
    
    # Convert the asset name into uppercase
    asset_name = asset_name.upper()
    
    # B. Asset Description
    # Get the listing description (defaults to '')
    description = request.json.get('description', '')
    
    # C. Asset Price
    # Get the asset's unit price in satoshis
    try:
        unit_price = int(request.json.get('price'))
    except ValueError:
        return jsonify({"error": "Parameter `price` must be an integer representing satoshis."}), 400
    
    # Validate the unit_price (max is 10 billion satoshis)
    if not unit_price or unit_price <= 0 or unit_price >= 10000000000000000:
        return jsonify({"error": "Parameter `price` was not provided or is out of range. Please specify a price between 0 and 10,000,000,000 satoshis."}), 400

    # D. Payout Address
    # Get the provided payout address
    payout_address = request.json.get('payout_address')

    # Validate the payout address
    try:
        is_valid = send_command("validateaddress", [payout_address])
    except Exception as e:
        logger.error(e)
        return jsonify({"error": f'{e}'})

    if not is_valid['isvalid']:
        logger.warning(f"{payout_address} is not a valid Evrmore address.")
        return jsonify({"error": "Invalid payout address"}), 400
    
    # E. Asset Tags
    # Get the asset's tags (defaults to [])
    tags = request.json.get('tags', [])

    # F. Listing password
    password = request.json.get('password')
    
    # Validate password existence
    if not password:
        return jsonify({"error": "Parameter `password` was not provided. Please provide a secure password for managing the listing."}), 400

    # Validate password strength
    strength, message = check_password_strength(password)
    if strength == "Weak":
        return jsonify({"error": f"{strength} password. {message}"}), 400

    # ---------------------------------------------------- #

    # Servicer shall provide:
    #   A. Asset Data
    #   B. A Unique Listing ID
    #   C. A unique evrmore address (to hold assets for sale)
    #   D. Hashed Password
    #   E. Timestamp of listing creation

    # A. Asset Data
    # Retrieve asset data
    try:
        asset_data = send_command("getassetdata", [asset_name])
    except Exception as e:
        logger.error(e)
        return jsonify({"error": f'{e}'})

    # Validate asset exists
    if asset_data is None:
        return jsonify({"error": "Invalid asset name"}), 400

    # B. Listing ID
    # Generate a unique listing ID
    listing_id = str(uuid.uuid4())

    # C. Listing address
    # Generate a new address for the listing
    listing_address = send_command("getnewaddress", [])

    # D. Hashed Password
    # Hash the password using bcrypt
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # E. Created at timestamp
    created_at_human_readable = datetime.utcnow().isoformat() + 'Z'
    created_at_timestamp = datetime.utcnow().timestamp()
    # ---------------------------------------------------- #

    # Create a new dictionary for the listing
    listing_data = {

        # Listee provided data    
        'asset_name': asset_name,
        'description': description,
        'unit_price': unit_price,  # Stored in satoshis
        'tags': json.dumps(tags),
        'payout_address': payout_address,

        # Servicer provided data
        'asset_data': json.dumps(asset_data),
        'listing_id': listing_id,
        'listing_address': listing_address,
        'password_hash': hashed_password.decode('utf-8'),  # Store the hashed password
        'created_at': created_at_human_readable,

        # Initialize default data
        'remaining_quantity': 0,
        'listing_status': 'INACTIVE', 

        # Listings shall be INACTIVE while asset balance is below 0
        # Listings shall switch to ACTIVE when the balance is above 0
        # These shall be the only two states for a listing
        # The status of the listing shall be checked using zmq or 30second interval then updated
        
    }

    # Save the listing using the RedisListingManager
    Database.Listings.add_listing(listing_data)

    # Return the listing data to the front end
    return jsonify(listing_data), 200

""" Manage a listing 
    Change the description, request a refund, or cancel the listing
    The listing must be in ACTIVE state to be managed
"""
@server.route('/manage', methods=['POST'])
def manage_listing():
    """
    Manage a listing by providing the listing ID, password, and action.
    Possible actions include canceling the listing, updating the price, description, or quantity,
    and refunding the surplus.
    """     

    """ TODO: Add support for updating the IPFS hash """

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
    listing_data = Database.Listings.get_listing(listing_id)

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
            Database.Listings.update_listing_unit_price(listing_id, new_price)
            logger.debug(f"Updated unit price: {new_price}")

        if 'description' in data:
            new_description = data['description']
            Database.Listings.update_listing_description(listing_id, new_description)
            logger.debug(f"Updated description: {new_description}")

        if 'listing_status' in data:
            new_status = data['listing_status']
            Database.Listings.update_listing_status(listing_id, new_status)
            logger.debug(f"Updated listing status: {new_status}")

        if 'ipfs_hash' in data:
            new_ipfs_hash = data['ipfs_hash']
            Database.Listings.update_listing_ipfs_hash(listing_id, new_ipfs_hash)
            logger.debug(f"Updated IPFS hash: {new_ipfs_hash}")

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
                    Database.Listings.update_listing_status(listing_id, 'REFUNDING')
                    Database.Listings.update_listing_refund_txid(listing_id, f"{refund_txid[0]}")
                    Database.Listings.update_listing_remaining_quantity(listing_id, 0)
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
        Database.Listings.update_listing_status(listing_id, 'CANCELED')
        logger.debug(f"Listing {listing_id} canceled successfully.")
        return jsonify({"message": "Listing canceled successfully.", "listing_id": listing_id}), 200

    logger.warning("Invalid action specified.")
    return jsonify({"message": "Invalid action."}), 400

@server.route('/listing/<listing_id>', methods=['GET'])
def get_listing(listing_id):
    logger.debug(f"Received request to retrieve listing {listing_id}")
    # Use the RedisListingManager to retrieve the listing data
    listing_data = Database.Listings.get_listing(listing_id)
    print(listing_data)
    # If the listing doesn't exist, return a 404 error
    if not listing_data:
        return jsonify({"error": "Listing not found"}, 404)
    
    # Return the listing data with a success status
    return jsonify(listing_data), 200