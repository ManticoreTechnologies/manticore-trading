import json
from helper import logger, settings
import time
import Database.Listings
import Database.Orders
from rpc import check_evr_confirming, get_address_mempool, send_command, get_asset_balance, check_asset_confirming


""" Process listings and update the status of the listings 
    This is the main function that processes the listings
    It loops through all the listings and updates the status of the listings
    It follows a specific order to ensure that we are always updating the status of the listing correctly
"""
def process_listings():

    logger.debug("Processing listings...")

    """ Get all the listings """
    listings = Database.Listings.get_all_listings()

    """ Loop through all the listings """
    for listing in listings:

        """ Follow this order to ensure that we are always updating the status of the listing correctly 



        0. Get the confirmed listing balance and update the database
        1. Check if the listing status is valid ["INACTIVE", "CONFIRMING", "ACTIVE", "REFUNDING", "CANCELED"]
        2. Process the listing based on the status 
            a. INACTIVE
                i. If the balance is greater than 0, the listing is ACTIVE
                ii. If the balance is 0, the listing is INACTIVE
                    @. Check for mempool, if found then the listing is CONFIRMING
                iii. If the balance is less than 0, then the listing is ERROR (serious issue we must manually investigate)
            b. CONFIRMING
                i. If the balance is greater than 0, the listing is ACTIVE
                ii. If balance is 0 we check for mempool
                    @. If no mempool then the listing is INACTIVE
            c. ACTIVE
                i. If the balance is 0, the listing is INACTIVE
            d. REFUNDING
                i. If the refund tx has more than 0 confirmations, the listing is INACTIVE
                ii. If the refund tx has 0 confirmations, the listing is REFUNDING
            e. CANCELED
                i. The listing is canceled and archived (set listing status to ARCHIVED)

        1. Update the listings confirmed balances
            a. If the balance is 0, the listing is INACTIVE
                I. Then check for asset mempool, if found then the listing is CONFIRMING
            b. If the balance is greater than 0, the listing is ACTIVE

        This way we update confirming listings only if the confirmed balance is 0
        Then if the confirmed balance is greater than 0, we just update the status to ACTIVE
        A listing could also be in REFUNDING state, which we handle in the orders processing
        """

        """ Step 0. Update the confirmed balance of the listing"""
        balance = get_asset_balance(listing['listing_address'], listing['asset_name'])
        Database.Listings.update_listing_balance(listing['id'], balance)

        """ Step 1. Check if listing status is valid """
        if listing['listing_status'] not in ["INACTIVE", "CONFIRMING", "ACTIVE", "REFUNDING", "CANCELED", "ARCHIVED"]:
            logger.warning(f"Invalid listing status {listing['listing_status']} for listing {listing['id']}. Skipping...")
            continue # Just warn for now, the listing just ever be processed
        
        """ Step 2. Check which status the order is in """

        if listing['listing_status'] == "INACTIVE": 
            """ 2.a. INACTIVE """

            """ Calculate the available balance """
            available_balance = balance - listing['on_hold']
            if available_balance > 0:
                """ 2.a.i. If the available balance is greater than 0, the listing is ACTIVE """
                Database.Listings.update_listing_status(listing['id'], "ACTIVE")
                Database.Listings.update_listing_remaining_quantity(listing['id'], available_balance)
                logger.debug(f"Listing {listing['id']} is now ACTIVE with balance {available_balance}.")
            elif available_balance == 0:
                """ 2.a.ii. If the available balance is 0, the listing is INACTIVE """
                Database.Listings.update_listing_remaining_quantity(listing['id'], 0)
                if check_asset_confirming(listing['listing_address'], listing['asset_name']):
                    """ 2.a.ii.@. If the asset is in the mempool, then the listing is CONFIRMING """
                    Database.Listings.update_listing_status(listing['id'], "CONFIRMING")
                    logger.debug(f"Listing {listing['id']} is now CONFIRMING.")
            else:
                """ 2.a.iii. If the available balance is less than 0, then we have a serious issue that needs to be investigated """
                logger.error(f"Listing {listing['id']} has negative available balance {available_balance}. Setting to ERROR.")
                Database.Listings.update_listing_status(listing['id'], "ERROR")

        elif listing['listing_status'] == "CONFIRMING":
            """ 2.b. CONFIRMING """
            if balance > 0:
                Database.Listings.update_listing_status(listing['id'], "ACTIVE")
                Database.Listings.update_listing_remaining_quantity(listing['id'], balance)
                logger.debug(f"Listing {listing['id']} is now ACTIVE with balance {balance}.")
            elif balance == 0:
                if check_asset_confirming(listing['listing_address'], listing['asset_name']):
                    """ 2.b.@. If the asset is in the mempool, then the listing is CONFIRMING """
                    Database.Listings.update_listing_status(listing['id'], "CONFIRMING")
                    logger.debug(f"Listing {listing['id']} is now CONFIRMING.")
        elif listing['listing_status'] == "ACTIVE":
            """ 2.c. ACTIVE """
            if balance == 0:
                """ 2.c.i. If the balance is 0, the listing is INACTIVE """
                Database.Listings.update_listing_status(listing['id'], "INACTIVE")
                logger.debug(f"Listing {listing['id']} is now INACTIVE due to zero balance.")
        elif listing['listing_status'] == "REFUNDING":
            """ 2.d. REFUNDING """
            if check_asset_confirming(listing['listing_address'], listing['asset_name']):
                """ 2.d.i. If the refund tx has more than 0 confirmations, the listing is INACTIVE """
                Database.Listings.update_listing_status(listing['id'], "INACTIVE")
                logger.debug(f"Refund for listing {listing['id']} is now complete. Setting to INACTIVE.")

        elif listing['listing_status'] == "CANCELED":
            """ 2.e. CANCELED """
            Database.Listings.update_listing_status(listing['id'], "ARCHIVED")
            logger.info(f"Listing {listing['id']} canceled and archived.")

    logger.debug("Finished processing all listings.")

""" Generate the listing fullfillment transaction """
def generate_listing_fullfillment_tx(order_id, listing_id, quantity):
    """ Create one raw transaction which will send the purchased assets to the buyer for this specific listing
        We do not handle refunds or fees here, actually nothing involving evrmore is done here
        We just create the raw transactions for sending the assets from the listing address to the buyer address
        and we make sure the change address for the assets is the listing address so the listing address keeps its assets
        quantity is the quantity of assets to send to the buyer
    """
    # 1. Get the listing from the database
    # 2. Get the name of the listed asset
    # 3. Define all required addresses

    # 1. Retrieve the listing 
    listing = Database.Listings.get_listing(listing_id)
    if not listing:
        logger.error(f"Listing not found for ID: {listing_id}")
        return False
    
    # 1.2 Get the order
    order = Database.Orders.get_order(order_id)
    if not order:
        logger.error(f"Order not found for ID: {order_id}")
        return False
    
    # 2. Get the name of the listed asset
    asset_name = listing['asset_name']

    # 3. Define all required addresses
    fee_address = "ENqA3JdabkyMKHcMeMoEjWb6nSUANrsGpC"#settings["General"]["fee_collection_address"]
    seller_address = listing["payout_address"]
    buyer_address = order["payout_address"]

    # 4. Get the utxos for the listing address
    listing_utxos = send_command("getaddressutxos", [listing["listing_address"]])

    logger.debug(f"Listing UTXOs: {listing_utxos}")


    logger.debug(f"Generating fullfillment transaction for listing {listing_id} | name: {asset_name}...")
    return False

def fullfill_order(order_id, listing_ids, quantities):
    """ listing_id is a LIST of ids of the listings that are being fulfilled
        quantity is a LIST of quantities of assets to send to the buyer for each listing
        we should return the txid or None once this is working
    """

    # Get all the listing addresses
    listing_addresses = [Database.Listings.get_listing(listing_id)['listing_address'] for listing_id in listing_ids]
    listing_names = [Database.Listings.get_listing(listing_id)['asset_name'] for listing_id in listing_ids]
    
    logger.debug(f"Listing addresses: {listing_addresses}")
    logger.debug(f"Listing names: {listing_names}")

    # Get all the listing utxos :)
    listing_utxos = [send_command("getaddressutxos", [listing_address]) for listing_address in listing_addresses]

    logger.debug(f"Listing UTXOs: {listing_utxos}")

def start_daemon():
    """ Start the daemon """
    logger.info("Daemon started")

    while True:

        """ Process orders """

        """ The overview for order processing is as follows:
            1. Check and purge all expired orders (ONLY pending orders)
            2. Loop through all the orders and process them
                a. Get the balance of the payment address
                b. Check the status of the order
                    i. PENDING
                        @. Check if the mempool has anything in it for the payment address
                            @. If yes, the order is CONFIRMING
                            @. If no, the order remains PENDING
                    ii. CONFIRMING
                        @. Check the balance of the payment address
                            @. If balance is greater than the payment amount, the order is CONFIRMED
                            @. If balance is equal to the payment amount, the order is CONFIRMED
                            @. If balance is less than the payment amount, the order remains CONFIRMING
                    iii. CONFIRMED
                        @. The order is already PAID
                    
        """
        
        """ 1. Check and purge all expired, pending orders"""
        Database.Orders.check_all_expired()
        
        """ 2. Loop through all the orders and process them """
        orders = Database.Orders.get_all_orders()
        for order in orders:

            logger.debug(f"--- Processing order {order['id']} ---")
            
            """ 2.a. Get the balance (of evrmore) of the payment address """
            payment_address = order['payment_address']
            balance = send_command("getaddressbalance", [{"addresses": [payment_address]}])['balance']
            logger.debug(f"Balance: {balance}")

            """ Check the status of the order """
            if order['status'] == "PENDING":
                """ 2.a.i. PENDING """

                """ Check if there is any mempool activity for the payment address """
                if check_evr_confirming(payment_address):
                    """ The order is CONFIRMING """
                    Database.Orders.update_order_status(order['id'], "CONFIRMING")
                    mempool_info = get_address_mempool(payment_address, assets=False)
                    Database.Orders.update_order_mempool(order['id'], json.dumps(mempool_info))
                    logger.debug(f"Order {order['id']} is now CONFIRMING. Saved mempool info to database.")
                    
                else:
                    """ The order remains PENDING """
                    logger.debug(f"Order {order['id']} is still PENDING. Waiting for payment.")
            elif order['status'] == "CONFIRMING":
                """ 2.a.ii. CONFIRMING """
                logger.debug(f"Order {order['id']} is CONFIRMING. Checking balance...")
                if balance > order['payment_amount']:
                    """ User user over paid, set to CONFIRMED but we need to refund the excess """
                    Database.Orders.update_order_status(order['id'], "CONFIRMED")
                    refund_amount = balance - order['payment_amount']
                    logger.debug(f"Order {order['id']} is now CONFIRMED. We should refund {refund_amount} to {payment_address}.")

                    """ Fullfill the order right away """
                    success = fullfill_order(order['id'], order['listing_id'], order['quantity'])
                    if not success:
                        """ Failed to fulfill the order, we should refund the user """
                        logger.error(f"Failed to fulfill order {order['id']}. Please investigate manually.")

                elif balance == order['payment_amount']:
                    """ The user paid exactly the right amount, set to CONFIRMED and refund set to 0 """
                    Database.Orders.update_order_status(order['id'], "CONFIRMED")
                    refund_amount = 0
                    logger.debug(f"Order {order['id']} is now CONFIRMED. No refund needed.")

                    """ Fullfill the order right away """
                    success = fullfill_order(order['id'], order['listing_id'], order['quantity'])
                    if not success:
                        """ Failed to fulfill the order, we should refund the user """
                        logger.error(f"Failed to fulfill order {order['id']}. Please investigate manually.")
                else:
                    """ The user did not pay enough, leave as CONFIRMING append any mempool info """
                    logger.debug(f"Order {order['id']} is still CONFIRMING. Waiting for full payment.")
                    current_mempool = Database.Orders.get_order_mempool(order['id'])
                    mempool_info = get_address_mempool(payment_address, assets=False)
                    Database.Orders.update_order_mempool(order['id'], json.dumps(current_mempool + mempool_info))
            elif order['status'] == "CONFIRMED":
                """ 2.a.iii. CONFIRMED """
                """ We should never get here, but just in case we do, we should go back to confirming """
                Database.Orders.update_order_status(order['id'], "CONFIRMING")
                logger.debug(f"Order {order['id']} is CONFIRMED. Setting back to CONFIRMING.")
        
        
        """ Process listings """
        process_listings()



        logger.debug("Sleeping for 10 seconds before next cycle.")
        time.sleep(10)