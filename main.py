"""Main application entry point."""
import asyncio
import signal
import logging

from database import init_db, get_pool, close as db_close
from monitor import monitor_transactions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global monitor instance
monitor = None

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    global monitor
    logger.info("Shutdown signal received. Cleaning up...")
    if monitor:
        monitor.stop()  # Stop monitoring
    asyncio.create_task(db_close())  # Close database connections

async def main():
    """Main application entry point."""
    global monitor
    try:
        # Initialize database
        logger.info("Initializing database...")
        await init_db()
        pool = await get_pool()
        
        # Register shutdown handlers
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
        
        # Create and start monitor
        logger.info("Starting blockchain monitoring...")
        monitor = monitor_transactions(pool)
        await monitor.start()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if monitor:
            monitor.stop()  # Stop monitoring
        await db_close()  # Close database connections
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
