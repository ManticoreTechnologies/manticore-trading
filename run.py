
from flask import Flask
from flask_cors import CORS
from app.utils.logger import create_logger

logger = create_logger()

# Create Flask application
app = Flask("Manticore Asset Explorer")
CORS(app, resources={r"/*": {"origins": "*"}})


if __name__ == "__main__":

    logger.info("Starting order processing service")

    while True:
        process_listings()
        logger.debug("Sleeping for 60 seconds before next cycle.")
        time.sleep(3)

else:
    logger.info("Starting the Flask app under gunicorn")
    import routes