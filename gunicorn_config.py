# gunicorn_config.py

import logging
import logging.config
from helper import create_logger, settings
import colorlog


# Gunicorn configuration
loglevel = 'error'
errorlog = '-'
accesslog = '-'
capture_output = True

# Set default IP and worker numbers for Gunicorn
try:
    port = settings['Server']['dev_port']
except KeyError:
    port = settings['Server']['port']

bind = settings['Server']['ip'] + ':' + port
workers = settings['Server']['workers']
