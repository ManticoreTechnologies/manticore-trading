# Manticore Technologies LLC
# (c) 2024 
# Manticore Asset Explorer
#    start_flask.py
# 
#  Start the Flask service
#  This is the main entry point for the Flask service
#  It will start the Flask service and load the routes
#  The routes are defined in the routes directory    
#  Primary purpose is to manage legacy trading routes
#  To run the Flask service, use the following command:
#  gunicorn -c gunicorn_config.py start_flask:app



# Import the configuration settings
from helper import settings, create_logger

# Create the logger
logger = create_logger(settings['Logging']['log_level'])

# Import Flask
from flask import Flask, jsonify
from flask_cors import CORS
# Create the Flask app
server = Flask(__name__)

CORS(server) # Set CORS policy



# Replace Flask's default logger with your custom logger
server.logger.handlers = logger.handlers
server.logger.setLevel(logger.level)

""" Import the routes """
from routes import *

# Run the Flask app (if this is the main module, this is for development)
if __name__ == "__main__":
    logger.info("Server listening on %s:%s", settings['Server']['ip'], settings['Server']['port'])
    server.run(host=settings['Server']['ip'], port=settings['Server']['port'])
else:
    import os
    logger.info("Worker listening on %s:%s | PID %s", settings['Server']['ip'], settings['Server']['port'], str(os.getpid()))

