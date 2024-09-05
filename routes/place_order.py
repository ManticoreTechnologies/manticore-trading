from startup import app, listing_manager
from rpc import send_command
from flask import jsonify, request
from utils import create_logger, config
import redis
import uuid
import time
import json

# Set up logging
logger = create_logger()

# Redis client setup
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

order_expiry = int(config['General']['order_expiry'])
@app.route('/expire_order/<order_id>', methods=['POST'])
def expire_order_route(order_id):
    """
    Manually expire a specific order by its order_id for testing purposes (API route).
    """
    response = expire_order(order_id)
    return jsonify({"message": response}), 200

def expire_orders():
    """
    Expire orders that haven't been paid within the reservation window.
    """
    logger.debug("Checking for expired orders.")
    
    current_time = time.time()
    order_keys = redis_client.keys("order:*")

    for key in order_keys:
        order = json.loads(redis_client.get(key))
        if order['status'] == 'PENDING' and order['expiration_time'] < current_time:
            expire_order(order['order_id'])


def expire_order(order_id):
    """
    Manually expire a specific order by its order_id. Can be called by the API or internally.
    """
    logger.debug(f"Received request to manually expire order {order_id}.")

    # Fetch the order from Redis
    order_key = f"order:{order_id}"
    order = redis_client.get(order_key)
    
    if not order:
        logger.warning(f"Order {order_id} not found.")
        return "Order not found."

    order = json.loads(order)
    
    if order['status'] != 'PENDING' and order['status'] != 'FULFILLMENT_FAILED':
        logger.warning(f"Order {order_id} is not in a pending or FULFILLMENT_FAILED state and cannot be expired.")
        return "Order is not in a pending or FULFILLMENT_FAILED state and cannot be expired."

    # Add the quantity back to the listing's remaining quantity
    listing_id = order['listing_id']
    quantity = float(order['quantity'])

    listing_data = listing_manager.get_listing(listing_id)
    if listing_data:
        # Convert the remaining_quantity to a float to ensure numeric operation
        new_quantity = float(listing_data['remaining_quantity']) + quantity
        new_on_hold = float(listing_data.get('on_hold', 0)) - quantity
        listing_manager.update_listing_field(listing_id, "remaining_quantity", new_quantity)
        listing_manager.update_listing_field(listing_id, "on_hold", max(new_on_hold, 0))
        logger.debug(f"Manually expired order {order_id}. Added {quantity} back to listing {listing_id}. New remaining quantity: {new_quantity}. On hold: {max(new_on_hold, 0)}")
    
    redis_client.delete(order_key)  # Expire the order
    logger.debug(f"Order {order_id} manually expired and removed from Redis.")
    
    return f"Order {order_id} manually expired."
@app.route('/place_order', methods=['POST'])
def place_order():
    """
    Place an order by creating a new bill/invoice with a unique address for payment.
    The order will have an expiration time to prevent over-committing the inventory.
    """
    logger.debug("Received request to place a new order.")

    # Expire any pending orders that have passed their expiration time
    expire_orders()

    data = request.json
    print(data)
    listing_id = data.get('listing_id')
    quantity = data.get('quantity')
    payout_address = data.get('payout_address')  # New parameter
    logger.debug(f"Listing ID: {listing_id}, Quantity: {quantity}, Payout Address: {payout_address}")
    
    # Validate inputs
    if not listing_id or not quantity or not payout_address:
        logger.warning("Listing ID, quantity, or payout address missing.")
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

    # Fetch listing data
    listing_data = listing_manager.get_listing(listing_id)
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

    # Reduce the remaining quantity of the listing and increase the on_hold quantity
    new_remaining_quantity = available_balance - quantity
    listing_manager.update_listing_field(listing_id, "remaining_quantity", new_remaining_quantity)
    new_on_hold = float(listing_data.get('on_hold', 0)) + quantity
    listing_manager.update_listing_field(listing_id, "on_hold", new_on_hold)
    logger.debug(f"Reduced remaining quantity of listing {listing_id} by {quantity}. New remaining quantity: {new_remaining_quantity}. On hold: {new_on_hold}")

    # Calculate the payment amount
    unit_price = float(listing_data['unit_price'])
    payment_amount = (unit_price * quantity) / 100000000
    fee = payment_amount * 0.05  # Calculate the 5% fee
    total_payment_amount = payment_amount + fee  # Add the fee to the payment amount
    logger.debug(f"Calculated payment amount: {payment_amount}, Fee: {fee}, Total Payment Amount: {total_payment_amount}")

    # Generate a new order ID
    order_id = str(uuid.uuid4())
    logger.debug(f"Generated Order ID: {order_id}")

    # Generate a new address for payment
    try:
        payment_address = send_command("getnewaddress")
        logger.debug(f"Generated Payment Address: {payment_address}")
    except Exception as e:
        logger.error(f"Error generating payment address: {str(e)}")
        return jsonify({"message": "Error generating payment address."}), 500

    # Set expiration time (e.g., 15 minutes from now)
    expiration_time = time.time() + order_expiry  # 15 minutes in seconds

    # Create the order bill
    order_bill = {
        "order_id": order_id,
        "listing_id": listing_id,
        "quantity": quantity,
        "payout_address": payout_address,  # Include payout address in order
        "payment_address": payment_address,
        "status": "PENDING",
        "expiration_time": expiration_time,  # Store expiration time
        "payment_amount": total_payment_amount,  # Store the total payment amount including the fee
        "fee": fee  # Store the fee separately if needed
    }

    # Save the order bill in Redis
    try:
        redis_client.set(f"order:{order_id}", json.dumps(order_bill))
        logger.debug(f"Order {order_id} saved to Redis.")
    except Exception as e:
        logger.error(f"Error saving order to Redis: {str(e)}")
        return jsonify({"message": "Error saving order to the database."}), 500

    return jsonify({
        "message": "Order placed successfully.",
        "order_id": order_id,
        "payment_address": payment_address,
        "payment_amount": total_payment_amount,  # Include the total payment amount in the response
        "payout_address": payout_address,  # Include the payout address in the response
        "fee": fee,  # Include the fee in the response if needed
        "expiration_time": expiration_time,
        "status": "PENDING"
    }), 201
