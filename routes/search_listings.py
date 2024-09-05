# Manticore Technologies LLC
# (c) 2024 
# Manticore Asset Explorer
#   search_listings.py 

from startup import app, listing_manager
from rpc import send_command
from utils import create_logger, config, load_map
from flask import jsonify, request, send_file, abort
import re
import math
import os
import json
import uuid

@app.route('/listings/search', methods=['GET'])
def search_listings():
    query = request.args.get('query', '')
    tag = request.args.get('tag', '')
    sort_by = request.args.get('sort_by', 'created_at')
    descending = request.args.get('descending', 'false').lower() == 'true'
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 10))
    
    # Check if the query starts with '%' for special tag queries
    if query.startswith('%'):
        # Strip the '%' and treat the rest of the query as a tag search
        tag = query[1:]
        query = ''  # Clear the query as we're now searching by tag

    # Now pass the modified query and tag to the listing manager
    results = listing_manager.search_listings(query, tag, sort_by, descending, page, page_size)
    return jsonify(results)
