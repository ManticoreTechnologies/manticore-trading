import json
import sqlite3

from flask import jsonify
from helper import logger
import time
import Database.Listings
import rpc

def create_orders_table():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id TEXT,
        quantity REAL,
        payout_address TEXT,
        payment_address TEXT,
        status TEXT,
        expiration_time REAL, 
        payment_amount REAL,
        fee REAL,
        mempool TEXT,
        fulfillment_txid TEXT
    )
    ''')

    conn.commit()
    conn.close()


""" Add an order to the database 
    Returns the id of the order if successful, None otherwise
"""
def add_order(listing_id, quantity, payout_address, payment_amount, fee):
    logger.debug(f"Adding order to the database with listing ID: {listing_id}, quantity: {quantity}, payout address: {payout_address}, payment amount: {payment_amount}, fee: {fee}")
    """ Set the initial status of the order """
    status = "PENDING"
    
    """ Set the expiration time of the order 
        Move this offset to a config file later
    """
    expiration_time = time.time() + 900

    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    """ Place the quantity on hold for the listing """

    # Ensure listing_id is a list
    if isinstance(listing_id, str):
        listing_id = [listing_id]

    success = Database.Listings.place_holds(listing_id, quantity)
    if not success:
        logger.error(f"Error placing holds on the database with listing ID: {listing_id}, quantity: {quantity}")
        Database.Listings.remove_holds(listing_id, quantity)
        return None

    logger.debug(f"Placed holds on the database with listing ID: {listing_id}, quantity: {quantity}")

    """ Create a new address for the order """
    try:
        payment_address = rpc.send_command("getnewaddress")
    except Exception as e:
        logger.error(f"Error generating payment address: {str(e)}")
        return None

    cursor.execute("INSERT INTO orders (listing_id, quantity, payout_address, payment_address, status, expiration_time, payment_amount, fee) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (json.dumps(listing_id), json.dumps(quantity), payout_address, payment_address, status, expiration_time, payment_amount, fee))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.debug(f"Added order to the database with ID: {order_id}")
    return order_id, payment_address, expiration_time
""" Convert a order to a dictionary """
def order_to_dict(order):
    if order is None:
        logger.error("Order is None")
        return None
    columns = ["id", "listing_id", "quantity", "payout_address", "payment_address", "status", "expiration_time", "payment_amount", "fee", "mempool", "fulfillment_txid"]
    order_dict = {columns[i]: order[i] for i in range(len(columns))}
    
    # Ensure listing_id is converted to a list
    if isinstance(order_dict["listing_id"], str):
        order_dict["listing_id"] = json.loads(order_dict["listing_id"])
    
    # Ensure quantity is converted to a list
    if isinstance(order_dict["quantity"], str):
        order_dict["quantity"] = json.loads(order_dict["quantity"])
    
    return order_dict

""" Retrieve an order from the database """
def get_order(order_id):
    logger.debug(f"Retrieving order from the database with ID: {order_id}")
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    return order_to_dict(cursor.fetchone())

""" Get all orders from the database """
def get_all_orders():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders")
    return [order_to_dict(order) for order in cursor.fetchall()]


""" Get all orders for a listing """
def get_all_orders_for_listing(listing_id):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE listing_id = ?", (listing_id,))
    return [order_to_dict(order) for order in cursor.fetchall()]

""" Deletes an order from the database """
def delete_order(order_id):
    """ When deleting an order, we need to reconcile a few things:
    1. Remove the hold on the satoshis from the listing
    2. Delete the order from the database
    """

    order = get_order(order_id)
    if not order:
        return False


    """ 1. Remove the hold on the satoshis from the listing """
    success = Database.Listings.remove_holds(order['listing_id'], order['quantity'])
    if not success:
        logger.error(f"Error removing hold on satoshis from listing {order['listing_id']}")
        logger.error(f"Listing Status: {Database.Listings.get_listing_status(order['listing_id'])}")
        return False

    """ 2. Delete the order from the database """
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    return True

""" Expire an order """
def check_expired(order_id):
    """ Orders must be in pending status to be expired """
    order = get_order(order_id)
    if not order:
        return False
    if order['status'] != "PENDING":
        return False
    # Check if the order is at least 15 minutes old and expired
    if order['expiration_time'] < time.time() and (time.time() - (order['payment_amount'] - 900)) >= 900:
        if delete_order(order['id']):
            return True
    return False

""" Delete all expired orders """
def check_all_expired():
    # Get all orders
    orders = get_all_orders()
    num_expired = 0
    for order in orders:
        if check_expired(order['id']):
            num_expired += 1

    print(f"{num_expired} expired orders deleted")

""" Update the status of an order """
def update_order_status(order_id, status):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()

""" Update the mempool of an order """
def update_order_mempool(order_id, mempool):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET mempool = ? WHERE id = ?", (mempool, order_id))
    conn.commit()
    conn.close()

""" Get the mempool of an order """
def get_order_mempool(order_id):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("SELECT mempool FROM orders WHERE id = ?", (order_id,))
    return json.loads(cursor.fetchone()[0])

if __name__ == "__main__":
    #create_orders_table()
    id = add_order("e2cdfcfd-3d30-433d-99e7-2d54aad9d09b", 1, "bc1q234567890abcdef1234567890abcdef1234567890", "bc1q234567890abcdef1234567890abcdef1234567890", 10000, 100)
    #check_all_expired()
    #success = delete_order(38)
    print(id) 