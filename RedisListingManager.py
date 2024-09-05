import redis
import json
from datetime import datetime
from utils import create_logger

logger = create_logger()

class RedisListingManager:
    def __init__(self, redis_client):
        self.r = redis_client

    def save_listing(self, listing_data):
        listing_id = listing_data['listing_id']
        
        # Save the listing data to the Redis hash
        self.r.hmset(f'listing:{listing_id}', listing_data)

        # Add the listing ID to the set of all listing IDs
        self.r.sadd("listing_ids", listing_id)

        # Add the listing ID to each tag set
        for tag in json.loads(listing_data['tags']):
            self.r.sadd(f'tag:{tag.lower()}', listing_id)

        # Add the listing ID to sorted sets for sorting by any field
        for key, value in listing_data.items():
            if key in ['unit_price', 'created_at']:
                if key == 'created_at':
                    value = datetime.fromisoformat(value.replace('Z', '')).timestamp()
                self.r.zadd(f'listings:{key}', {listing_id: value})

    def get_listing(self, listing_id):
        # Retrieve the listing data from Redis
        listing_data = self.r.hgetall(f'listing:{listing_id}')
        return {key.decode('utf-8'): value.decode('utf-8') for key, value in listing_data.items()}

    def list_listings(self, sort_by='created_at', descending=False, page=1, page_size=10):
        # Calculate the start and end index for pagination
        start = (page - 1) * page_size
        end = start + page_size - 1

        # Retrieve listing IDs sorted by the specified field
        if descending:
            listing_ids = self.r.zrevrange(f'listings:{sort_by}', start, end)
        else:
            listing_ids = self.r.zrange(f'listings:{sort_by}', start, end)

        listings = []
        for listing_id in listing_ids:
            listings.append(self.get_listing(listing_id.decode('utf-8')))
        return listings

    def search_listings(self, query='', tag='', sort_by='created_at', descending=False, page=1, page_size=10):
        matching_ids = set()

        if tag:
            tag_listing_ids = self.r.smembers(f'tag:{tag.lower()}')
            matching_ids.update(tag_listing_ids)
        else:
            all_listing_ids = self.r.zrange('listings:created_at', 0, -1)
            matching_ids.update(all_listing_ids)

        filtered_ids = []
        for listing_id in matching_ids:
            listing_id_str = listing_id.decode('utf-8')
            listing_data = self.get_listing(listing_id_str)
            if query.lower() in listing_data['asset_name'].lower() or query.lower() in listing_data['description'].lower():
                filtered_ids.append(listing_id_str)

        # Sort the filtered IDs by the specified field
        if sort_by:
            filtered_ids.sort(
                key=lambda x: self.r.hget(f'listing:{x}', sort_by) or '',
                reverse=descending
            )

        # Paginate the results
        start = (page - 1) * page_size
        end = start + page_size
        paginated_ids = filtered_ids[start:end]

        results = [self.get_listing(listing_id) for listing_id in paginated_ids]

        return results

    def update_listing_field(self, listing_id, field, value):
        self.r.hset(f'listing:{listing_id}', field, value)
        if field in ['unit_price', 'created_at']:
            self.r.zadd(f'listings:{field}', {listing_id: value})

    def delete_listing(self, listing_id):
        # Retrieve all the listing data before deletion
        listing_data = self.get_listing(listing_id)
        
        if not listing_data:
            return  # If the listing doesn't exist, just return

        # Delete the listing itself
        self.r.delete(f'listing:{listing_id}')

        # Remove the listing ID from the set of all listing IDs
        self.r.srem("listing_ids", listing_id)

        # Remove the listing ID from all the associated tag sets
        for tag in json.loads(listing_data.get('tags', '[]')):
            self.r.srem(f'tag:{tag.lower()}', listing_id)

        # Remove the listing ID from sorted sets for sorting by any field
        for key in ['unit_price', 'created_at']:
            self.r.zrem(f'listings:{key}', listing_id)

        logger.info(f"Listing {listing_id} and all associated data have been deleted.")


    def flush_db(self):
        self.r.flushdb()
