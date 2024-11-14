# Manticore Technologies LLC
# (c) 2024 
# Manticore Asset Explorer
#    get_listing.py 

from startup import app, listing_manager
from flask import jsonify

@app.route('/listing/<listing_id>', methods=['GET'])
def get_listing(listing_id):
    # Use the RedisListingManager to retrieve the listing data
    listing_data = listing_manager.get_listing(listing_id)
    
    # If the listing doesn't exist, return a 404 error
    if not listing_data:
        return jsonify({"error": "Listing not found"}, 404)
    
    # Return the listing data with a success status
    return jsonify(listing_data), 200

