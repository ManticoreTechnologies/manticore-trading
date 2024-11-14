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
bind = settings['Server']['ip'] + ':' + settings['Server']['port']
workers = settings['Server']['workers']

