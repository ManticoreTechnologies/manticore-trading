"""Script to serve the API documentation."""

import os
import sys
import signal
import socket
from pathlib import Path
import http.server
import socketserver
import threading
import time

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

# First generate the docs
from generate_docs import main as generate_docs

def is_port_in_use(port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_available_port(start_port=8081, max_attempts=10):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(port):
            return port
    raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Threaded HTTP server with proper cleanup."""
    allow_reuse_address = True
    daemon_threads = True

def serve_docs():
    """Serve the documentation on localhost:8080."""
    # Change to the docs directory
    os.chdir(Path(__file__).parent)
    
    # Find available port
    try:
        PORT = find_available_port()
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    Handler = http.server.SimpleHTTPRequestHandler
    
    print(f"Serving documentation at http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    
    # Create server with proper cleanup
    server = ThreadedHTTPServer(("", PORT), Handler)
    
    # Handle shutdown gracefully
    def signal_handler(signum, frame):
        print("\nShutting down server...")
        server.shutdown()
        server.server_close()
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Run server in a separate thread
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"\nError: {e}")
        server.shutdown()
        server.server_close()
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Generate docs first
        print("Generating documentation...")
        generate_docs()
        
        # Then serve them
        serve_docs()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1) 