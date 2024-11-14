from helper import settings, logger

if __name__ == "__main__":
    import rpc
    
    """ Tests the connection to the Evrmore node """
    if not rpc.test_connection():
        logger.critical("Unable to connect to Evrmore node. Exiting.")
        """ If we fail to connect, exit because we can't do anything else """
        exit(1)
    
    """ If we connected, log it and start the daemon """
    logger.info("Connected to Evrmore node. Starting daemon...")

    """ Start the daemon """
    from daemon import start_daemon
    start_daemon()