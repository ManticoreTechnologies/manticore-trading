"""Command line interface for running the API server and blockchain monitor."""
import asyncio
import logging
import signal
import uvicorn
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from database import init_db, close as db_close, get_pool
from monitor import monitor_transactions
from orders import PayoutManager
from workers.featured_payments import run_worker as run_featured_payments

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
monitor = None
payout_processor = None
server = None
should_exit = False

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    global should_exit
    logger.info("Shutdown signal received. Cleaning up...")
    should_exit = True

async def startup():
    """Initialize database and monitor."""
    global monitor, payout_processor
    
    try:
        logger.info("Initializing database...")
        await init_db()
        pool = await get_pool()
        
        # Create monitor
        logger.info("Creating blockchain monitor...")
        monitor = monitor_transactions(pool)
        
        # Create payout processor
        logger.info("Creating payout processor...")
        payout_processor = PayoutManager(pool)
        
        return monitor, payout_processor
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

class UvicornServer:
    """Wrapper for running uvicorn with proper lifecycle management."""
    
    def __init__(self, app_path: str = "api:app", host: str = "10.0.0.2", port: int = 8000):
        self.config = uvicorn.Config(
            app_path,
            host=host,
            port=port,
            reload=False,  # Disable reload to prevent connection pool issues
            log_level="info",
            workers=1
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
        if monitor:
            await monitor.start()
    except Exception as e:
        logger.error(f"Monitor error: {e}")
        # Don't raise here, just log the error
        # This allows the API to run even if monitoring fails

async def run_payout_processor(processor):
    """Run the payout processor."""
    try:
        if processor:
            logger.info("Starting payout processor task")
            await processor.process_payouts()
    except Exception as e:
        logger.error(f"Payout processor error: {e}")
        # Don't raise here, just log the error
        # This allows the API to run even if payout processing fails

async def run_featured_payments_worker():
    """Run the featured payments worker."""
    try:
        logger.info("Starting featured payments worker")
        await run_featured_payments()
    except Exception as e:
        logger.error(f"Featured payments worker error: {e}")
        # Don't raise here, just log the error

async def main():
    """Run the API server, blockchain monitor, and payout processor."""
    global monitor, payout_processor, server, should_exit
    
    try:
        # Register signal handlers in main thread
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
        
        # Initialize services
        try:
            monitor, payout_processor = await startup()
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            return
        
        # Create tasks for all services
        tasks = [
            asyncio.create_task(run_api(), name="api"),
            asyncio.create_task(run_monitor(monitor), name="monitor"),
            asyncio.create_task(run_payout_processor(payout_processor), name="payout"),
            asyncio.create_task(run_featured_payments_worker(), name="featured_payments")
        ]
        
        logger.info("All services started")
        
        # Wait for shutdown signal
        while not should_exit:
            await asyncio.sleep(1)
            
            # Check if any tasks failed
            for task in tasks:
                if task.done() and not task.cancelled():
                    try:
                        exc = task.exception()
                        if exc:
                            logger.error(f"Task {task.get_name()} failed with error: {exc}")
                            # Don't exit on monitor/payout/featured_payments failures
                            if task.get_name() == "api":
                                should_exit = True
                                break
                    except asyncio.CancelledError:
                        pass
            
        # Cleanup started
        logger.info("Starting cleanup...")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Cleanup
        if monitor:
            logger.info("Stopping blockchain monitor...")
            await monitor.stop()
        
        if payout_processor:
            logger.info("Stopping payout processor...")
            await payout_processor.stop()
        
        if server:
            logger.info("Stopping API server...")
            await server.stop()
        
        # Cancel all tasks
        for task in asyncio.all_tasks():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
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