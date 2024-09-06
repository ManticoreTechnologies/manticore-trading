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

@app.route('/list', methods=['POST'])
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
    if not unit_price or unit_price <= 0 or unit_price >= 10000000000:
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
    listing_manager.save_listing(listing_data)

    # Return the listing data to the front end
    return jsonify(listing_data), 200

# DISABLE BEFORE PRODUCTION
#@app.route('/flush')
#def flush_redis_db():
#    listing_manager.flush_db()
#    return "Flushed successfully"
