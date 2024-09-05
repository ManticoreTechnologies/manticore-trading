from startup import app, listing_manager
from flask import jsonify, request
from utils import create_logger
import redis
import json

# Set up logging
logger = create_logger()

# Redis client setup
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
@app.route('/get_invoice/<order_id>', methods=['GET'])
def get_invoice(order_id):
    """
    Retrieve a specific invoice by its order_id.
    """
    logger.debug(f"Received request to retrieve invoice with order_id: {order_id}")

    try:
        # Fetch the order from Redis using the order_id
        order_key = f"order:{order_id}"
        invoice = redis_client.get(order_key)
        
        if not invoice:
            logger.debug(f"Invoice with order_id {order_id} not found.")
            return jsonify({"message": "Invoice not found."}), 404

        # Deserialize JSON string
        invoice_data = json.loads(invoice)
        logger.debug(f"Invoice data retrieved for order_id {order_id}.")
        return jsonify({"invoice": invoice_data}), 200

    except Exception as e:
        logger.error(f"Error retrieving invoice with order_id {order_id}: {str(e)}")
        return jsonify({"message": "Error retrieving invoice."}), 500