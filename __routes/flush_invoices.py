from startup import app, listing_manager
from flask import jsonify
from utils import create_logger
import redis
import json
import os
logger = create_logger()
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0)

@app.route('/flush_invoices', methods=['GET'])
def flush_invoices():
    """
    Remove all invoices from Redis.
    """
    logger.debug("Received request to flush all invoices.")

    try:
        # Scan through the keys in Redis that match "order:*"
        invoice_keys = redis_client.keys("order:*")
        
        if not invoice_keys:
            logger.debug("No invoices found to delete.")
            return jsonify({"message": "No invoices found."}), 404

        # Delete each invoice key
        for key in invoice_keys:
            redis_client.delete(key)
        
        logger.debug(f"Flushed {len(invoice_keys)} invoices.")
        return jsonify({"message": f"Successfully flushed {len(invoice_keys)} invoices."}), 200

    except Exception as e:
        logger.error(f"Error flushing invoices: {str(e)}")
        return jsonify({"message": "Error flushing invoices."}), 500
