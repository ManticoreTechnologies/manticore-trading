
# Manticore Trading Service


#### Data for ai to rewrite readme ####
Entrypoint: run.py
Start command: python run.py 

This entry runs gunicorn with the config file gunicorn_config.py
settings.conf is the configuration file for the application

Node username and password are required to be set in .env


#######################################



## Overview

**Manticore Trading Service** is a Python-based application that serves as a dual-service system. The primary function is to mirror assets from IPFS for quick access, while the secondary service continuously monitors for new assets and automatically downloads associated images.

### Features

- **Flask API Service:**  
  A Flask-based API that loads and serves asset maps, making them quickly accessible via HTTP routes.
  
- **Asset Download Service:**  
  A background service that checks for new assets and downloads images as they become available, ensuring the latest assets are always mirrored.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/manticore-asset-explorer.git
   cd manticore-asset-explorer
   ```

2. Create a virtual environment and activate it:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up the necessary configuration in `settings.conf`.

## Configuration

Ensure that your `raven.conf` (or equivalent) is configured with the appropriate ZMQ settings:

```ini
zmqpubrawblock=tcp://127.0.0.1:29332
zmqpubrawtx=tcp://127.0.0.1:29333
```