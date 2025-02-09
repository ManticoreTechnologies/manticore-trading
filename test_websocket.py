import asyncio
import websockets
import json

async def test_ping():
    uri = "ws://localhost:8000/ws/ping"
    async with websockets.connect(uri) as websocket:
        # Send ping message
        await websocket.send("ping")
        print("Sent: ping")
        
        # Receive pong response
        response = await websocket.recv()
        print(f"Received: {response}")

asyncio.run(test_ping()) 