"""Command line interface for running the API server and blockchain monitor."""
import asyncio
import logging
import signal
import uvicorn
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from database import init_db, close as db_close, get_pool
from monitor import monitor_transactions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
monitor = None
server = None
should_exit = False

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    global should_exit
    logger.info("Shutdown signal received. Cleaning up...")
    should_exit = True

async def startup():
    """Initialize database and monitor."""
    global monitor
    
    logger.info("Initializing database...")
    await init_db()
    pool = await get_pool()
    
    # Create monitor
    logger.info("Creating blockchain monitor...")
    monitor = monitor_transactions(pool)
    
    return monitor

class UvicornServer:
    """Wrapper for running uvicorn with proper lifecycle management."""
    
    def __init__(self, app_path: str = "api:app", host: str = "0.0.0.0", port: int = 8000):
        self.config = uvicorn.Config(
            app_path,
            host=host,
            port=port,
            reload=True,
            log_level="info"
        )
        self.server = uvicorn.Server(self.config)
    
    async def run(self):
        """Run the server in a way that can be stopped."""
        self.server.config.setup_event_loop()
        await self.server.serve()
    
    async def stop(self):
        """Stop the server."""
        self.server.should_exit = True
        if hasattr(self.server, 'force_exit'):
            self.server.force_exit = True

async def run_api():
    """Run the API server."""
    global server
    server = UvicornServer()
    await server.run()

async def run_monitor(monitor):
    """Run the blockchain monitor."""
    try:
        await monitor.start()
    except Exception as e:
        logger.error(f"Monitor error: {e}")
        raise

async def main():
    """Run both the API server and blockchain monitor."""
    global monitor, server, should_exit
    
    try:
        # Register signal handlers in main thread
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
        
        # Initialize services
        monitor = await startup()
        
        # Create tasks for both services
        api_task = asyncio.create_task(run_api())
        monitor_task = asyncio.create_task(run_monitor(monitor))
        
        # Wait for shutdown signal
        while not should_exit:
            await asyncio.sleep(1)
            
        # Cleanup started
        logger.info("Starting cleanup...")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Cleanup
        if monitor:
            logger.info("Stopping blockchain monitor...")
            monitor.stop()
        
        if server:
            logger.info("Stopping API server...")
            await server.stop()
        
        logger.info("Closing database connections...")
        await db_close()
        
        logger.info("Cleanup complete.")

if __name__ == "__main__":
    # Use uvloop if available for better performance
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    
    # Run everything in the same event loop
    asyncio.run(main()) 