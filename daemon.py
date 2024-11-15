import json
from helper import settings, create_logger
import time
import Database.Listings
import Database.Orders
from rpc import check_evr_confirming, get_address_mempool, send_command, get_asset_balance, check_asset_confirming

logger = create_logger(settings['Logging']['log_level'])

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
    listing_utxos = send_command("getaddressutxos", [{"addresses": [listing["listing_address"]], "assetName": listing["asset_name"]}])

    logger.debug(f"Listing UTXOs: {listing_utxos}")


    logger.debug(f"Generating fullfillment transaction for listing {listing_id} | name: {asset_name}...")
    return False


import sys
def estimate_network_fee(raw_tx):
    transaction_bytes = raw_tx if isinstance(raw_tx, bytes) else bytes(raw_tx, 'utf-8')     
    transaction_size_bytes = sys.getsizeof(transaction_bytes)
    transaction_size_kilobytes = transaction_size_bytes / 1024


    # min fee is 0.01 evr, we use 0.0101 to avoid failures
    return round(0.0101*transaction_size_kilobytes*100000000)

""" Generate the evrmore payments for the order 
    Each order has a list of listings, each listing has a payout address and a quantity
    
    First we must loop through all the listings and prepare the data necessary to calculate the evrmore payments
    Then we must create the raw transaction for the evrmore payments
"""
def create_payout_transactions(order_id, listing_ids, quantities, fee_percentage=settings["Fee"]["fee_percentage"], fee_address=settings["Fee"]["fee_address"]):


    """ Get the order """
    order = Database.Orders.get_order(order_id)
    if not order:
        logger.error(f"Order not found for ID: {order_id}")
        return False
    """ Get the listings """
    listings = Database.Listings.get_listings(listing_ids)
    if not listings:
        logger.error(f"Listings not found for IDs: {listing_ids}")
        return False
    """ Get the order UTXOs! :) """
    order_utxos = send_command("getaddressutxos", [{"addresses": [order["payment_address"]]}])
    """ Convert the order UTXOs to the format we need """
    order_utxos = [{"txid": utxo['txid'], "vout": utxo['outputIndex'], "satoshis": utxo['satoshis']} for utxo in order_utxos]

    logger.debug(f"Order UTXOs: {order_utxos}")


    
    """ Sum up the 'satoshis' from the order UTXOs """
    total_satoshis = sum(utxo['satoshis'] for utxo in order_utxos)

    """ Get the invoice amount in satoshis """
    invoice_satoshis = order['payment_amount']
    
 


    """ Calculate the buyer refund, this is the amount of funds that will be refunded to the buyer """
    buyer_refund = total_satoshis - invoice_satoshis



    """ Buyer asset payout is now handled in the generate_listing_fullfillment_tx function 
        The raw transaction from this function should be combined with the raw transaction from generate_listing_fullfillment_tx
    """

    """ Handle all the seller payouts and fees """
    """ Total up the seller fees to send to the fee address """
    seller_fees = 0
    total_seller_payouts = 0
    buyer_asset_payouts = {
        order["payout_address"]: {
            "transfer": {

            }
        }
    }
    seller_payouts = []

    seller_outputs = []

    for listing in listings:
        """ Get the name of the asset """
        asset_name = listing['asset_name']

        """ Get the quantity for this listing """
        quantity = quantities[listing_ids.index(listing['id'])]

        """ Calculate the payout for this seller """
        listing_sale_amount = round(((quantity * listing['unit_price']) / 100000000))

        """ Calculate the fee, x% of the invoice amount, we take this from the sellers' payouts """
        fee_satoshis = round(invoice_satoshis * float(fee_percentage))
        seller_fees += fee_satoshis

        """ Calculate the seller payout """
        seller_payout = listing_sale_amount - fee_satoshis
        total_seller_payouts += seller_payout
        seller_payouts.append(seller_payout)

        """ Generate the output to pay the seller """
        seller_payout_output = {
            listing["payout_address"]: seller_payout/100000000  
        }
        seller_outputs.append(seller_payout_output)

        """ Generate the buyer listing payout output """
        logger.debug(f"Generating buyer listing payout output for {listing['asset_name']} with quantity {quantity}")
        buyer_asset_payouts[order["payout_address"]]["transfer"][listing["asset_name"]] = quantity/100000000
        logger.debug(f"Buyer asset payouts: {buyer_asset_payouts}")


    """ Create the buyer refund output """
    buyer_refund_output = {
        order["payout_address"]: buyer_refund/100000000
    }

    """ Calculate the buyer fee """
    buyer_fee = invoice_satoshis * float(fee_percentage)

    """ Add the buyer fee to the total fee """
    total_fee = seller_fees + buyer_fee


    """ Create the fee output """
    fee_output = {
        fee_address: total_fee/100000000
    }


    """ Summary """
    logger.error(  "-------- Fees --------")
    logger.error(f"Buyer fee = {buyer_fee}")
    logger.error(f"Seller fees = {seller_fees}")
    logger.error(f"Total fee = {total_fee}")
    logger.error(f"Payed to = {fee_address}")
    logger.error(f"Fee output = {fee_output}")
    logger.error(  "----------------------")

    logger.info(  "-------- Buyer --------")
    logger.info(f"Buyer refund = {buyer_refund}")
    logger.info(f"Buyer fee = {buyer_fee}")
    logger.info(f"{buyer_refund_output} REFUND")
    for i in buyer_asset_payouts[order["payout_address"]]["transfer"]:
        logger.info(f"{buyer_asset_payouts[order['payout_address']]['transfer'][i]} PURCHASED")

    logger.warning(  "-------- Seller --------")
    for i in range(len(listing_ids)):
        logger.warning(f"Payment amount for {quantities[i]} of {listings[i]['asset_name']} is {seller_payouts[i]}.")
        logger.warning(f"{seller_outputs[i]}.")
    logger.warning(  "----------------------")

    """ When we get here we should have all the following raw tx data 
        seller_raw_txs - a list of raw transactions for each seller
        buyer_raw_tx - a raw transaction for the buyer, should include refund if any
        fee_raw_tx - a raw transaction for the fee, the exchange fee
         
        On the Evrmore blockchain, combining different types of transactions is not allowed
        The order UTXOs are used for the seller payouts, buyer refund, and fee
        The listing UTXOs are used for the buyer asset payouts

        We must create an evrmore raw transaction that contains all evrmore payments
        Then we create another raw transaction that contains all the asset payouts
        
        """

    """ Handle creating the evrmore payout transaction first """

    """ Reduce seller payouts to a single dict """
    combined_seller_outputs = {k: v for d in seller_outputs for k, v in d.items()}
    logger.debug(f"Combined seller outputs: {combined_seller_outputs}")


    """ Combine the seller payouts, buyer refund and fee into a single dict 
        We combine the fee, refund, and seller payouts into a single dict
        these will be the outputs of the evrmore transaction
    """    
    combined_evrmore_outputs = {**fee_output, **combined_seller_outputs}
    if buyer_refund != 0:
        combined_evrmore_outputs = {**combined_evrmore_outputs, **buyer_refund_output}

    """ Create the evrmore raw transaction """
    evrmore_raw_tx = send_command("createrawtransaction", [order_utxos, combined_evrmore_outputs])
    logger.debug(f"Evrmore raw transaction: {evrmore_raw_tx}")



    """ Handle creating the asset payout transaction next 
        For this we just use the listing UTXOs and the buyer asset payouts
        We combine the buyer asset payouts into a single dict

        We also need outputs for the change that will be sent back to the listings
        each listing will have a utxo 
    """


    """ Now we go through each listing and sum the utxo satoshis for the asset name """
    listing_outputs = []
    all_listing_utxos = []
    for listing in listings:

        """ Get the listing UTXOs! :) """
        listing_utxos = send_command("getaddressutxos", [{"addresses": [listing["listing_address"]], "assetName": listing["asset_name"]}])

        """ Convert the listing UTXOs to the format we need """
        listing_utxos = [{"txid": utxo['txid'], "vout": utxo['outputIndex'], "satoshis": utxo['satoshis'], "assetName": utxo['assetName'], "address": utxo['address']} for utxo in listing_utxos]
        all_listing_utxos.extend(listing_utxos)
        """ Sum the utxo satoshis for the asset name """
        listing_satoshis = sum(utxo['satoshis'] for utxo in listing_utxos if utxo['assetName'] == listing['asset_name'])
        logger.debug(f"Sum of {listing['asset_name']} satoshis for {listing['listing_address']}: {listing_satoshis}")
        """ Get the quantity sent to the buyer for this listing """
        quantity = quantities[listing_ids.index(listing['id'])]
        """ Calculate the change that will be sent back to the listing address """
        change = listing_satoshis - quantity
        logger.debug(f"Change for {listing['asset_name']} sent back to {listing['listing_address']}: {change}")

        """ Create the change output for the listing """
        change_output = {
            listing["listing_address"]: {
                "transfer": {
                    listing["asset_name"]: change/100000000
                }
            }
        }
        logger.debug(f"Change output for {listing['asset_name']} sent back to {listing['listing_address']}: {change_output}")
        listing_outputs.append(change_output)


    """ Combine the listing change outputs into a single dict """
    combined_listing_outputs = {k: v for d in listing_outputs for k, v in d.items()}
    logger.debug(f"Combined listing change outputs: {combined_listing_outputs}")

    """ Combine the buyer asset payouts and the listing change outputs into a single dict """
    combined_asset_outputs = {**buyer_asset_payouts, **combined_listing_outputs}
    logger.debug(f"Combined asset outputs: {combined_asset_outputs}")

    """ Create the asset raw transaction """
    asset_raw_tx = send_command("createrawtransaction", [all_listing_utxos, combined_asset_outputs])
    logger.debug(f"Asset raw transaction: {asset_raw_tx}")

    """ We now have two raw transaction, one for the evrmore payments and one for the asset payouts
        The CANNOT be combined, they must be broadcasted separately
    """




    return evrmore_raw_tx, asset_raw_tx

def fund_raw_transaction(raw_tx):
    return send_command("fundrawtransaction", [raw_tx, {"feeRate": 0.01}])['hex']

def sign_raw_transaction(raw_tx):
    return send_command("signrawtransaction", [raw_tx])['hex']

def broadcast_raw_transaction(raw_tx):
    return send_command("sendrawtransaction", [raw_tx])

""" Fullfill an order """
def fullfill_order(order_id, listing_ids, quantities):

    """ listing_id is a LIST of ids of the listings that are being fulfilled
        quantity is a LIST of quantities of assets to send to the buyer for each listing
        we should return the txid or None once this is working
    """

    """ Get the order """
    order = Database.Orders.get_order(order_id)
    if not order:
        logger.error(f"Order not found for ID: {order_id}")
        return False
    
    """ Get the order UTXOs! :) """
    order_utxos = send_command("getaddressutxos", [{"addresses": [order["payment_address"]]}])
    logger.debug(f"Order UTXOs: {order_utxos}")

    """ Calculate the raw transaction handling evrmore fee, refunds, and seller payout """
    evr_raw_tx, asset_raw_tx = create_payout_transactions(order_id, listing_ids, quantities)

    

    """ Attempt to fund the evrmore transaction """
    try:
        funded_evr_tx = fund_raw_transaction(evr_raw_tx)
    except Exception as e:
        logger.error(f"Failed to fund evrmore raw transaction: {e}")
        return False
    
    """ Attempt to sign the evrmore transaction """
    try:
        signed_evr_tx = sign_raw_transaction(funded_evr_tx)
    except Exception as e:
        logger.error(f"Failed to sign evrmore raw transaction: {e}")
        return False
    
    """ Attempt to broadcast the transactions """
    evr_txid = None
    try:
        evr_txid = broadcast_raw_transaction(signed_evr_tx)
    except Exception as e:
        logger.error(f"Failed to broadcast evrmore raw transaction: {e}")
        return False

    """ Check if the evrmore transaction was broadcasted """
    if not evr_txid:
        logger.error(f"Failed to broadcast evrmore transaction, no txid received.")
        return False
    
    """ Update the order with the evrmore txid """
    Database.Orders.update_order_refund_txid(order_id, evr_txid)

    """ Try to fund the asset transaction """
    try:
        funded_asset_tx = fund_raw_transaction(asset_raw_tx)
    except Exception as e:
        logger.error(f"Failed to fund asset raw transaction: {e}")
        return False
    
    """ Try to sign the asset transaction """
    try:
        signed_asset_tx = sign_raw_transaction(funded_asset_tx)
    except Exception as e:
        logger.error(f"Failed to sign asset raw transaction: {e}")
        return False
    
    """ Try to broadcast the asset transaction """
    asset_txid = None
    try:
        asset_txid = broadcast_raw_transaction(signed_asset_tx)
    except Exception as e:
        logger.error(f"Failed to broadcast asset raw transaction: {e}")
        return False

    """ Update the order with the asset txid """
    Database.Orders.update_order_fulfillment_txid(order_id, asset_txid)

    """ Return true if we successfully broadcasted the transactions 
    """

    """ Update the listings with the sold amount """
    for i in range(len(listing_ids)):
        Database.Listings.increment_listing_sold(listing_ids[i], quantities[i])

    return True

def start_daemon():
    """ Start the daemon """
    logger.info("Daemon started")

    while True:
        process_listings()
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

            logger.debug(f"--- Processing order {order['id']} {order['payment_address']} ---")
            
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
                    elif success:
                        """ Successfully fulfilled the order, we should update the order with the txids """
                        """ Update the status to COMPLETED """
                        Database.Orders.update_order_status(order['id'], "COMPLETED")

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
                    elif success:
                        """ Successfully fulfilled the order, we should update the order with the txids """
                        """ Update the status to COMPLETED """
                        Database.Orders.update_order_status(order['id'], "COMPLETED")
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
            else:
                """ We just skip these, allows us to add statuses for manual intervention """
                logger.debug(f"Order {order['id']} has an {order['status']} status. Skipping.")
        
        """ Process listings """
        process_listings()



        logger.debug("Sleeping for 10 seconds before next cycle.")
        time.sleep(10)