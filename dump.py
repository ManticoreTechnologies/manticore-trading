import redis
import json
import os

# Set up Redis connection
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0)

def dump_redis_database(output_file='redis_dump.json'):
    """
    Dump the entire Redis database to a JSON file.
    """
    try:
        # Retrieve all keys from the Redis database
        keys = redis_client.keys('*')
        
        # Dictionary to store all key-value pairs
        redis_data = {}
        
        for key in keys:
            # Get the value for each key
            value = redis_client.get(key)
            # Decode the key and value from bytes to string
            redis_data[key.decode('utf-8')] = json.loads(value.decode('utf-8'))
        
        # Write the data to a JSON file
        with open(output_file, 'w') as f:
            json.dump(redis_data, f, indent=4)
        
        print(f"Redis database dumped successfully to {output_file}.")
    
    except Exception as e:
        print(f"Error dumping Redis database: {str(e)}")

if __name__ == "__main__":
    dump_redis_database()