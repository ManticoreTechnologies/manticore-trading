# Manticore Technologies LLC
# (c) 2024 
# Manticore Asset Explorer
#    list_listings.py 

from startup import app, listing_manager
from flask import jsonify, request

@app.route('/listings', methods=['GET'])
def list_listings():
    sort_by = request.args.get('sort_by', 'created_at')
    descending = request.args.get('descending', 'false').lower() == 'true'
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 10))
    
    listings = listing_manager.list_listings(sort_by, descending, page, page_size)
    return jsonify(listings), 200
