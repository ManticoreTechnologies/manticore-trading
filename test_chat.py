import asyncio
import websockets
import json
import requests
from datetime import datetime
from uuid import uuid4
from rpc import getnewaddress, signmessage

async def get_auth_token():
    # Get new address
    address = getnewaddress()
    print(f"\nGenerated address: {address}")
    
    # Get challenge
    print("\nGetting challenge...")
    response = requests.post(
        "http://localhost:8000/auth/challenge",
        json={"address": address}
    )
    if not response.ok:
        raise Exception(f"Failed to get challenge: {response.text}")
    
    challenge_data = response.json()
    challenge_id = challenge_data["challenge_id"]
    message = challenge_data["message"]
    print(f"Challenge received: {message}")
    
    # Sign message
    print("\nSigning message...")
    signature = signmessage(address, message)
    print(f"Signature: {signature}")
    
    # Verify and get token
    print("\nGetting JWT token...")
    response = requests.post(
        "http://localhost:8000/auth/login",
        json={
            "challenge_id": challenge_id,
            "address": address,
            "signature": signature
        }
    )
    if not response.ok:
        raise Exception(f"Failed to get token: {response.text}")
    
    token = response.json()["token"]
    print("Successfully got JWT token")
    
    return address, token

async def test_chat():
    # Get authentication token
    address, token = await get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    base_url = "http://localhost:8000"

    # Test global chat messages
    print("\nTesting GET /chat/global")
    response = requests.get(f"{base_url}/chat/global", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json() if response.ok else response.text}")

    # Test sending a global message
    print("\nTesting POST /chat/global")
    message_data = {
        "text": "Test message from " + address[:8],
        "ipfs_hash": None
    }
    response = requests.post(f"{base_url}/chat/global", headers=headers, json=message_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json() if response.ok else response.text}")

    # Test WebSocket connection
    print("\nTesting WebSocket connection")
    uri = f"ws://localhost:8000/chat/ws"
    async with websockets.connect(uri) as websocket:
        # Send auth message
        await websocket.send(json.dumps({
            "token": token
        }))
        print("Sent auth message")

        # Wait for connection confirmation
        response = await websocket.recv()
        print(f"Received: {response}")

        # Send a test message
        await websocket.send(json.dumps({
            "type": "chat_message",
            "data": {
                "text": f"Test WebSocket message from {address[:8]}",
                "type": "global"
            }
        }))
        print("Sent test message")

        # Wait for response
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"Received: {response}")
        except asyncio.TimeoutError:
            print("No response received within timeout")

if __name__ == "__main__":
    asyncio.run(test_chat()) 