from startup import app, listing_manager
from flask import jsonify
from utils import create_logger
import redis
import json

# Set up logging
logger = create_logger()

# Redis client setup
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

@app.route('/list_invoices', methods=['GET'])
def list_invoices():
    """
    List all invoices stored in Redis.
    """
    logger.debug("Received request to list all invoices.")

    try:
        # Scan through the keys in Redis that match "order:*"
        order_keys = redis_client.keys("order:*")
        
        if not order_keys:
            logger.debug("No invoices found.")
            return jsonify({"message": "No invoices found."}), 404

        invoices = []
        for key in order_keys:
            invoice = redis_client.get(key)
            if invoice:
                invoices.append(json.loads(invoice))  # Deserialize JSON string

        logger.debug(f"Found {len(invoices)} invoices.")
        return jsonify({"invoices": invoices}), 200

    except Exception as e:
        logger.error(f"Error retrieving invoices: {str(e)}")
        return jsonify({"message": "Error retrieving invoices."}), 500
