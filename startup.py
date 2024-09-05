# Import utilities
from utils import create_logger, welcome_message, config
import json
from flask import Flask
from flask_cors import CORS
from RedisListingManager import RedisListingManager
import redis
import time
from rpc import send_command


# Initialize logging
logger = create_logger()

# Print the welcome message
logger.info(welcome_message)

# Create Flask application
app = Flask("Manticore Asset Explorer")
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize the RedisListingManager
listing_manager = RedisListingManager(redis.Redis(host='localhost', port=6379, db=6))

# Redis client setup
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

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
    
    if order['status'] != 'PENDING':
        logger.warning(f"Order {order_id} is not in a pending state and cannot be expired.")
        return "Order is not in a pending state and cannot be expired."

    # Add the quantity back to the listing's remaining quantity
    listing_id = order['listing_id']
    quantity = order['quantity']

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

def process_listings():
    """
    Processes all listings by checking balances, updating their status, 
    and handling orders by checking for transactions and balance adequacy.
    """
    logger.debug("|-------- Processing All Listings --------|")

    # Expire any pending orders before processing listings
    expire_orders()

    # Retrieve all listings currently in the system
    listings = listing_manager.list_listings(sort_by='created_at')
    
    # Loop through all the listings
    for listing in listings:
        listing_id = listing["listing_id"]
        asset_name = listing["asset_name"]
        listing_status = listing["listing_status"]
        listing_address = listing["listing_address"]

        logger.debug(f"Processing Listing ID: {listing_id}, Asset: {asset_name}, Status: {listing_status}")

        # Check balances for the listing address
        try:
            balances = send_command('getaddressbalance', [{"addresses": [listing_address]}, True])
        except Exception as e:
            logger.error(e)
            return e

        balances_dict = {asset['assetName']: asset for asset in balances}

        if listing_status in ["INACTIVE", "CONFIRMING", "ACTIVE", "REFUNDING", "CANCELED"]:

            if listing_status == "INACTIVE":
                if asset_name in balances_dict:
                    asset_balance = balances_dict[asset_name]['balance'] * 100000000
                    on_hold = listing.get('on_hold', 0)
                    effective_balance = asset_balance - float(on_hold)
                    if effective_balance > 0:
                        listing_manager.update_listing_field(listing_id, "listing_status", "ACTIVE")
                        listing_manager.update_listing_field(listing_id, "remaining_quantity", effective_balance)
                        logger.debug(f"Listing {listing_id} is now ACTIVE with balance {effective_balance}")
                    else:
                        logger.debug(f"Listing {listing_id} remains INACTIVE with zero balance.")
                        listing_manager.update_listing_field(listing_id, "remaining_quantity", 0)
                else:
                    mempool_info = send_command('getaddressmempool', [{"addresses": [listing_address]}, True])
                    for tx in mempool_info:
                        if asset_name == tx["assetName"]:
                            listing_manager.update_listing_field(listing_id, "listing_status", "CONFIRMING")
                            logger.debug(f"Listing {listing_id} is now CONFIRMING.")
                        else:
                            logger.warning(f"Unexpected asset {tx['assetName']} found in mempool for listing {listing_id}.")

            elif listing_status == "CONFIRMING":
                if asset_name in balances_dict:
                    asset_balance = balances_dict[asset_name]['balance'] 
                    on_hold = listing.get('on_hold', 0)
                    effective_balance = asset_balance - float(on_hold)
                    if effective_balance > 0:
                        listing_manager.update_listing_field(listing_id, "listing_status", "ACTIVE")
                        listing_manager.update_listing_field(listing_id, "remaining_quantity", effective_balance)
                        logger.debug(f"Listing {listing_id} is now ACTIVE with balance {effective_balance}.")
                    else:
                        logger.debug(f"Listing {listing_id} remains CONFIRMING with zero balance.")

            elif listing_status == "ACTIVE":
                if asset_name in balances_dict:
                    asset_balance = balances_dict[asset_name]['balance'] 
                    on_hold = listing.get('on_hold', 0)
                    effective_balance = asset_balance - float(on_hold)
                    if effective_balance > 0:
                        listing_manager.update_listing_field(listing_id, "remaining_quantity", effective_balance)
                        logger.debug(f"Listing {listing_id} balance updated to {effective_balance}.")
                    else:
                        listing_manager.update_listing_field(listing_id, "listing_status", "INACTIVE")
                        logger.debug(f"Listing {listing_id} is now INACTIVE due to zero balance.")

            elif listing_status == "REFUNDING":
                refund_txid = listing['refund_txid']
                tx_info = send_command('gettransaction', [refund_txid])
                refund_confirmations = int(tx_info['confirmations'])
                if refund_confirmations > 0:
                    listing_manager.update_listing_field(listing_id, "listing_status", "INACTIVE")
                    logger.info(f"Listing {listing_id} refund processed successfully. Status set to INACTIVE.")
                else:
                    logger.debug(f"Listing {listing_id} refund still processing with {refund_confirmations} confirmations.")

            elif listing_status == "CANCELED":
                listing_manager.delete_listing(listing_id)
                logger.info(f"Listing {listing_id} canceled and deleted.")

        # Process orders for the listing
        process_orders_for_listing(listing_id, listing_address, listing["unit_price"])

    logger.debug("Finished processing listings.")

def process_orders_for_listing(listing_id, listing_address, unit_price):
    """
    Processes all orders related to a specific listing by checking mempool transactions,
    verifying balance sufficiency, and handling fulfillment once confirmed.
    """
    logger.debug(f"Processing orders for Listing ID: {listing_id}")

    order_keys = redis_client.keys(f"order:*")
    for order_key in order_keys:
        order = json.loads(redis_client.get(order_key))
        if order['listing_id'] == listing_id:
            if order['status'] == 'PENDING':
                mempool_info = send_command('getaddressmempool', [{"addresses": [order['payment_address']]}, True])
                if mempool_info:
                    order['status'] = 'CONFIRMING'
                    order['mempool'] = json.dumps(mempool_info)
                    redis_client.set(order_key, json.dumps(order))
                    logger.debug(f"Order {order['order_id']} is now CONFIRMING.")

            if order['status'] == 'CONFIRMING':
                balances = send_command('getaddressbalance', [{"addresses": [order['payment_address']]}, True])

                # Find the EVR balance in the returned balances
                evr_balance = 0
                for balance in balances:
                    if balance['assetName'] == 'EVR':
                        evr_balance = balance['balance'] * 100000000   # Convert to proper EVR amount
                        break

                required_amount = float(order['payment_amount'])
                
                # Check if the EVR balance is sufficient
                if evr_balance >= required_amount:
                    order['status'] = 'CONFIRMED'
                    redis_client.set(order_key, json.dumps(order))
                    logger.debug(f"Order {order['order_id']} has sufficient EVR balance and is now CONFIRMED.")
                    fulfill_order(order, listing_address, listing_id, order_key)
                else:
                    logger.debug(f"Order {order['order_id']} is still confirming. EVR balance: {evr_balance}, Required: {required_amount}")
            if order['status'] == 'PROCESSING_FULFILLMENT':
                    """
                    Monitors the fulfillment transaction until it has the required confirmations.
                    """
                    logger.info(f"Monitoring fulfillment for order {order['order_id']}. TXID: {order['fulfillment_txid']}")

                    # Retrieve the fulfillment_txid as a string
                    fulfillment_txid = order['fulfillment_txid']

                    logger.info(fulfillment_txid)
                    if isinstance(fulfillment_txid, list):
                        fulfillment_txid = fulfillment_txid[0]  # Extract the first element if it's a list

                    try:
                        listing_data = listing_manager.get_listing(listing_id)
                        tx_info = send_command('gettransaction', [fulfillment_txid])
                        confirmations = tx_info.get('confirmations', 0)

                        if confirmations > 0:
                            # Update the listing's sold and on_hold quantities
                            new_on_hold = float(listing_data.get('on_hold', 0)) - order['quantity']
                            new_sold = float(listing_data.get('sold', 0)) + order['quantity']
                            listing_manager.update_listing_field(listing_id, "on_hold", max(new_on_hold, 0))
                            listing_manager.update_listing_field(listing_id, "sold", new_sold)
                            logger.debug(f"Updated listing {listing_id}: on_hold={max(new_on_hold, 0)}, sold={new_sold}")

                            # Mark the order as COMPLETE
                            order['status'] = 'COMPLETE'
                            redis_client.set(order_key, json.dumps(order))
                            logger.info(f"Order {order['order_id']} is now COMPLETE.")
                            break

                        logger.debug(f"Order {order['order_id']} still processing. Confirmations: {confirmations}")

                    except Exception as e:
                        logger.error(f"Error monitoring fulfillment for order {order['order_id']}: {str(e)}")
                        break

import sys

def estimate_network_fee(utxos, vouts):
    
    transaction = send_command("createrawtransaction", [utxos, vouts])

    transaction_bytes = transaction if isinstance(transaction, bytes) else bytes(transaction, 'utf-8')   
    transaction_size_bytes = sys.getsizeof(transaction_bytes)
    transaction_size_kilobytes = transaction_size_bytes / 1024


    # min fee is 0.01 evr, we use 0.0101 to avoid failures
    return round(0.0101*transaction_size_kilobytes*100000000)

def fulfill_order(order, listing_address, listing_id, order_key):

    # Retrieve the listing 
    listing = listing_manager.get_listing(listing_id)
    if not listing:
        logger.error(f"Listing not found for ID: {listing_id}")
        return

    # Get the name of the listed asset
    asset_name = listing['asset_name']

    # Define all required addresses
    fee_address = config["General"]["fee_collection_address"]
    seller_address = listing["payout_address"]
    buyer_address = order["payout_address"]

    # Get the mempool data for the order address
    order_mempool = json.loads(order['mempool'])
    order_utxos = [{"txid": mempool['txid'], "vout": mempool['index']} for mempool in order_mempool]
    
    # Define the total evrmore available
    total_satoshis = sum(mempool['satoshis'] for mempool in order_mempool)

    # Define the invoice amount (total buyer paid including the 5% fee)
    invoice_satoshis = order['payment_amount']

    # Calcualte the 5% fee 
    fee_satoshis = round(invoice_satoshis * 0.05)

    # Calculate payouts 
    seller_payout = invoice_satoshis - fee_satoshis - fee_satoshis
    
    # Calculate the buyer refund
    buyer_refund = total_satoshis - invoice_satoshis

    # Define buyer asset payout 
    buyer_payout = order['quantity']

    logger.critical(  "-------- Fees --------")
    logger.critical(f"Buyer fee = {fee_satoshis}")
    logger.critical(f"Seller fee = {fee_satoshis}")
    logger.critical(f"Total fee = {fee_satoshis+fee_satoshis}")
    logger.critical(f"Payed to = {fee_address}")
    logger.critical(  "----------------------")

    logger.info(  "-------- Buyer --------")
    logger.info(f"Refund amount = {buyer_refund}")
    logger.info(f"Asset amount = {buyer_payout}")
    logger.info(f"Payed to = {buyer_address}")
    logger.info(  "----------------------")

    logger.warning(  "-------- Seller --------")
    logger.warning(f"Payment amount = {seller_payout}")
    logger.warning(f"Payed to = {seller_address}")
    logger.warning(  "----------------------")

    logger.critical(f"Total sent by buyer: {total_satoshis}")
    logger.critical(f"Total refunded to buyer: {buyer_refund}")
    logger.critical(f"Total fee collected: {fee_satoshis + fee_satoshis}")
    logger.critical(f"Total payed to seller: {seller_payout}")

    logger.warning(listing['listing_address'])

    # Not actually spending the order_utxos, 
    buyer_txid = send_command('transferfromaddress', [asset_name, listing_address, buyer_payout / 100000000, buyer_address, "", 0, listing_address, listing_address])

    network_fee = estimate_network_fee(order_utxos, {
        fee_address: fee_satoshis+fee_satoshis,
        listing['payout_address']: seller_payout / 100000000
    })

    transaction = send_command("createrawtransaction", [order_utxos, {
        fee_address: (fee_satoshis+fee_satoshis-network_fee) / 100000000,
        listing['payout_address']: seller_payout / 100000000
    }])
    signed_transaction = send_command("signrawtransaction", [transaction])
    seller_txid = send_command("sendrawtransaction", [signed_transaction['hex']])

    

    try:

        # Update order status to PROCESSING_FULFILLMENT
        order['status'] = 'PROCESSING_FULFILLMENT'
        order['fulfillment_txid'] = buyer_txid
        redis_client.set(order_key, json.dumps(order))

    except Exception as e:
        logger.error(f"Error during fulfillment for order {order['order_id']}: {str(e)}")
        order['status'] = 'FULFILLMENT_FAILED'
        redis_client.set(order_key, json.dumps(order))


if __name__ == "__main__":
    logger.info("Starting order processing service")

    while True:
        process_listings()
        logger.debug("Sleeping for 60 seconds before next cycle.")
        time.sleep(3)

else:
    logger.info("Starting the Flask app under gunicorn")
    import routes
