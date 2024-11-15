import json
from helper import logger
import sqlite3

def create_listings_table():
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS listings (
        id TEXT PRIMARY KEY,
        unit_price REAL,
        description TEXT,
        listing_address TEXT,
        created_at TEXT,
        sold REAL,
        password_hash TEXT,
        payout_address TEXT,
        tags TEXT,
        asset_data TEXT,
        asset_name TEXT,
        on_hold REAL,
        remaining_quantity REAL,
        listing_status TEXT,
        refund_txid TEXT
    )
    ''')

    conn.commit()
    conn.close()

""" Add refund txid column to the database """
def add_refund_txid_column():
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE listings ADD COLUMN refund_txid TEXT")
    conn.commit()
    conn.close()

def preload_listings():
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    listings = json.loads(open('listings.json').read())
    listings = list(listings.values())
    
    for listing in listings:
        try:
            sold = float(listing["sold"])
        except:
            sold = 0
        try:
            on_hold = float(listing["on_hold"])
        except:
            on_hold = 0

        cursor.execute("INSERT INTO listings (id, unit_price, description, listing_address, created_at, sold, password_hash, payout_address, tags, asset_data, asset_name, on_hold, remaining_quantity, listing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (listing['listing_id'], listing['unit_price'], listing['description'], listing['listing_address'], listing['created_at'], sold, listing['password_hash'], listing['payout_address'], listing['tags'], listing['asset_data'], listing['asset_name'], on_hold, listing['remaining_quantity'], listing['listing_status']))
    conn.commit()
    conn.close()

""" Add a listing to the database """
def add_listing(listing):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO listings (id, unit_price, description, listing_address, created_at, sold, password_hash, payout_address, tags, asset_data, asset_name, on_hold, remaining_quantity, listing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (listing['listing_id'], listing['unit_price'], listing['description'], listing['listing_address'], listing['created_at'], 0, listing['password_hash'], listing['payout_address'], listing['tags'], listing['asset_data'], listing['asset_name'], 0, listing['remaining_quantity'], listing['listing_status']))
    conn.commit()
    conn.close()


""" Convert a listing to a dictionary """
def listing_to_dict(listing):
    columns = ["id", "unit_price", "description", "listing_address", "created_at", "sold", "password_hash", "payout_address", "tags", "asset_data", "asset_name", "on_hold", "remaining_quantity", "listing_status"]
    return {columns[i]: listing[i] for i in range(len(columns))}

""" Retrieves a listing from the database by listing_id """
def get_listing(listing_id):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    return listing_to_dict(cursor.fetchone())

""" Retrieves multiple listings from the database by listing_ids """
def get_listings(listing_ids):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE id IN ({})".format(','.join(['?'] * len(listing_ids))), listing_ids)
    return [listing_to_dict(listing) for listing in cursor.fetchall()]

""" Get all listings """
def get_all_listings():
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings")
    return [listing_to_dict(listing) for listing in cursor.fetchall()]

""" Add satoshis to on_hold """
def place_hold(listing_id, satoshis):
    """ Place satoshis on hold for a listing 
        Returns True if successful, False otherwise
        Inactive listings cannot have satoshis placed on hold
        Listings cannot have more on hold than the remaining quantity        
    """
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT listing_status FROM listings WHERE id = ?", (listing_id,))
    
    """ Check if the listing is inactive """
    listing_status = cursor.fetchone()[0]
    if listing_status == "inactive":
        return False
    
    """ Check that on_hold + satoshis is less than or equal to remaining_quantity """
    cursor.execute("SELECT on_hold, remaining_quantity FROM listings WHERE id = ?", (listing_id,))
    on_hold, remaining_quantity = cursor.fetchone()
    if on_hold + satoshis > remaining_quantity:
        return False

    cursor.execute("UPDATE listings SET on_hold = on_hold + ? WHERE id = ?", (satoshis, listing_id))
    conn.commit()
    conn.close()
    return True

""" Place holds on multiple listings """
def place_holds(listing_ids, satoshis):
    success = True
    for i in range(len(listing_ids)):
        success = place_hold(listing_ids[i], satoshis[i])
        if not success:
            return False
    return True

""" Remove holds on multiple listings """
def remove_holds(listing_ids, satoshis):
    success = True
    for i in range(len(listing_ids)):
        success = remove_hold(listing_ids[i], satoshis[i])
        if not success:
            return False
    return True

""" Remove satoshis from on_hold """
def remove_hold(listing_id, satoshis):
    """ Remove satoshis from on_hold """
    logger.debug(f"Removing {satoshis} from on_hold for listing {listing_id}")
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    """ A listing cannot have negative on_hold """
    cursor.execute("SELECT on_hold FROM listings WHERE id = ?", (listing_id,))
    on_hold = cursor.fetchone()[0]
    if on_hold - satoshis < 0:
        logger.error(f"Listing {listing_id} would have negative on_hold")
        return False
    cursor.execute("UPDATE listings SET on_hold = on_hold - ? WHERE id = ?", (satoshis, listing_id))
    conn.commit()
    conn.close()
    return True


""" Update the balance of a listing """
def update_listing_balance(listing_id, balance):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET remaining_quantity = ? WHERE id = ?", (balance, listing_id))
    conn.commit()
    conn.close()

""" Update the status of a listing """
def update_listing_status(listing_id, status):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET listing_status = ? WHERE id = ?", (status, listing_id))
    conn.commit()
    conn.close()

""" Update the unit price of a listing """
def update_listing_unit_price(listing_id, unit_price):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET unit_price = ? WHERE id = ?", (unit_price, listing_id))
    conn.commit()
    conn.close()

""" Update the description of a listing """
def update_listing_description(listing_id, description):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET description = ? WHERE id = ?", (description, listing_id))
    conn.commit()
    conn.close()

""" Update the status of a listing """
def update_listing_status(listing_id, status):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET listing_status = ? WHERE id = ?", (status, listing_id))
    conn.commit()
    conn.close()

""" Update the refund txid of a listing """
def update_listing_refund_txid(listing_id, refund_txid):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET refund_txid = ? WHERE id = ?", (refund_txid, listing_id))
    conn.commit()
    conn.close()    

""" Update the remaining quantity of a listing """
def update_listing_remaining_quantity(listing_id, remaining_quantity):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET remaining_quantity = ? WHERE id = ?", (remaining_quantity, listing_id))
    conn.commit()
    conn.close()

def set_listing_hold(listing_id, on_hold):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET on_hold = ? WHERE id = ?", (on_hold, listing_id))
    conn.commit()
    conn.close()
""" get listing status """
def get_listing_status(listing_id):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT listing_status FROM listings WHERE id = ?", (listing_id,))
    return cursor.fetchone()[0]



""" Increment the sold amount of a listing """
def increment_listing_sold(listing_id, amount):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET sold = sold + ? WHERE id = ?", (amount, listing_id))
    conn.commit()
    conn.close()

""" Decrement the sold amount of a listing """
def decrement_listing_sold(listing_id, amount):
    conn = sqlite3.connect('listings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE listings SET sold = sold - ? WHERE id = ?", (amount, listing_id))
    conn.commit()
    conn.close()

""" Add more methods for filtering listings by tags, price, etc. """


if __name__ == "__main__":
    #add_refund_txid_column()
    print(get_all_listings())
