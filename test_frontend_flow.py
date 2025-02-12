"""Test script to simulate frontend client interactions with the API."""

import asyncio
import logging
import json
import subprocess
from decimal import Decimal
import time
import os
from config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FrontendClientTest:
    """Test harness that simulates frontend client interactions."""
    
    def __init__(self):
        self.api_url = "http://10.0.0.2:8000"
        
        # Test data storage
        self.seller_address = None
        self.buyer_address = None
        self.listing_id = None
        self.auth_token = None
        self.order_id = None
        self.listing_file = "test_listing_id.txt"
        self.deposit_address = None
        
        # Load config
        config = load_config()
        self.min_confirmations = int(config.get('DEFAULT', 'min_confirmations', fallback=6))
        logger.info(f"Using minimum confirmations: {self.min_confirmations}")

    def run_cmd(self, cmd: str) -> dict:
        """Run a shell command and return parsed JSON output."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                try:
                    # Try to find JSON in the output
                    output = result.stdout
                    json_start = output.find('{')
                    json_end = output.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = output[json_start:json_end]
                        return json.loads(json_str)
                    else:
                        # If no JSON found, return as plain text
                        return {"output": result.stdout.strip()}
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.stdout}")
                    if result.stderr:
                        logger.error(f"stderr: {result.stderr}")
                    return {"output": result.stdout.strip()}
            return {}
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed with exit code {e.returncode}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            raise

    async def setup(self):
        """Initialize test environment."""
        logger.info("Setting up test environment...")
        
        # Generate buyer address - we always need a new one
        self.buyer_address = self.run_cmd("evrmore-cli getnewaddress")["output"]
        logger.info(f"Generated new buyer address: {self.buyer_address}")
        
        # Try to load existing listing data
        try:
            if os.path.exists(self.listing_file):
                with open(self.listing_file, 'r') as f:
                    data = json.load(f)
                    self.listing_id = data.get('listing_id')
                    self.seller_address = data.get('seller_address')
                    self.deposit_address = data.get('deposit_address')
                    
                    if all([self.listing_id, self.seller_address, self.deposit_address]):
                        logger.info(f"Loaded existing listing data:")
                        logger.info(f"  Listing ID: {self.listing_id}")
                        logger.info(f"  Seller Address: {self.seller_address}")
                        logger.info(f"  Deposit Address: {self.deposit_address}")
                        
                        # Verify the listing exists and has sufficient balance
                        try:
                            listing_data = self.run_cmd(f'''
                                curl -s -X GET {self.api_url}/listings/by-id/{self.listing_id}
                            ''')
                            
                            if listing_data.get("id") == self.listing_id:
                                # Check if listing has sufficient balance
                                for balance in listing_data.get("balances", []):
                                    if balance["asset_name"] == "CREDITS":
                                        confirmed = float(balance["confirmed_balance"])
                                        pending = float(balance["pending_balance"])
                                        if confirmed >= 2.0:
                                            logger.info("Found existing listing with sufficient balance")
                                            return
                                        else:
                                            logger.info(f"Existing listing found but insufficient balance (confirmed: {confirmed}, pending: {pending})")
                                            self.listing_id = None  # Reset so we create new listing
                                            break
                            else:
                                logger.info("Saved listing ID not found in API")
                                self.listing_id = None
                        except Exception as e:
                            logger.info(f"Could not verify existing listing: {e}")
                            self.listing_id = None
        except Exception as e:
            logger.info(f"No valid listing data found: {e}")
            self.listing_id = None
        
        # If we get here, we need to create a new listing
        logger.info("Will create new listing with fresh addresses...")
        
        # Generate seller address for new listing
        self.seller_address = self.run_cmd("evrmore-cli getnewaddress")["output"]
        logger.info(f"Generated seller address: {self.seller_address}")
        
        # Remove old listing file if it exists
        if os.path.exists(self.listing_file):
            os.remove(self.listing_file)

    async def authenticate(self) -> str:
        """Simulate frontend authentication flow using curl."""
        logger.info("Starting authentication flow...")
        
        # 1. Get challenge message
        challenge_resp = self.run_cmd(f'''
            curl -s -X POST {self.api_url}/auth/challenge \\
                -H "Content-Type: application/json" \\
                -d '{{"address": "{self.seller_address}"}}'
        ''')
        
        if 'challenge_id' not in challenge_resp or 'message' not in challenge_resp:
            raise ValueError(f"Invalid challenge response: {challenge_resp}")
        
        challenge_id = challenge_resp["challenge_id"]
        message = challenge_resp["message"]
        
        # 2. Sign message with evrmore-cli
        signature = self.run_cmd(f'evrmore-cli signmessage "{self.seller_address}" "{message}"')["output"]
        
        # 3. Submit signature to get JWT token
        auth_resp = self.run_cmd(f'''
            curl -s -X POST {self.api_url}/auth/login \\
                -H "Content-Type: application/json" \\
                -d '{{
                    "challenge_id": "{challenge_id}",
                    "address": "{self.seller_address}",
                    "signature": "{signature}"
                }}'
        ''')
        
        if 'token' not in auth_resp:
            raise ValueError(f"Invalid auth response: {auth_resp}")
        
        self.auth_token = auth_resp["token"]
        logger.info("Authentication successful")
        return self.auth_token

    async def create_listing(self) -> str:
        """Create a test listing using curl."""
        logger.info("Creating new test listing...")
        
        listing_resp = self.run_cmd(f'''
            curl -s -L -X POST {self.api_url}/listings/ \\
                -H "Content-Type: application/json" \\
                -H "Authorization: Bearer {self.auth_token}" \\
                -d '{{
                    "seller_address": "{self.seller_address}",
                    "name": "Test CREDITS Listing",
                    "description": "A test listing selling CREDITS",
                    "prices": [{{
                        "asset_name": "CREDITS",
                        "price_evr": 75,
                        "units": 6
                    }}],
                    "tags": ["test", "CREDITS"]
                }}'
        ''')
        
        # Debug output
        logger.info(f"Listing creation response: {listing_resp}")
        
        if 'id' not in listing_resp:
            raise ValueError(f"Failed to create listing: {listing_resp}")
        
        self.listing_id = listing_resp["id"]
        
        # Get full listing details to get deposit address
        listing_details = self.run_cmd(f'''
            curl -s -X GET {self.api_url}/listings/by-id/{self.listing_id} \\
                -H "Authorization: Bearer {self.auth_token}"
        ''')
        
        if 'deposit_address' not in listing_details:
            raise ValueError(f"Listing details missing deposit address: {listing_details}")
        
        self.deposit_address = listing_details["deposit_address"]
            
        # Save all the data to file
        listing_data = {
            'listing_id': self.listing_id,
            'seller_address': self.seller_address,
            'deposit_address': self.deposit_address
        }
        with open(self.listing_file, 'w') as f:
            json.dump(listing_data, f, indent=2)
            
        logger.info(f"Created and saved listing data:")
        logger.info(f"  Listing ID: {self.listing_id}")
        logger.info(f"  Seller Address: {self.seller_address}")
        logger.info(f"  Deposit Address: {self.deposit_address}")
        
        return self.listing_id

    async def fund_listing(self):
        """Fund the listing with test assets using evrmore-cli."""
        logger.info("Funding test listing...")
        
        if not self.deposit_address:
            raise ValueError("No deposit address available")
        
        # Send CREDITS to listing using evrmore-cli
        tx_hash = self.run_cmd(f'''
            evrmore-cli transfer CREDITS 2.0 {self.deposit_address}
        ''')["output"]
        logger.info(f"Sent 2.0 CREDITS to listing (tx: {tx_hash})")
        
        # Monitor balance until confirmed
        logger.info("Waiting for transaction to be confirmed...")
        max_wait = 600  # Maximum wait time in seconds (10 minutes)
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait:
                raise TimeoutError("Transaction confirmation timed out")
            
            listing_data = self.run_cmd(f'''
                curl -s -X GET {self.api_url}/listings/by-id/{self.listing_id} \\
                    -H "Authorization: Bearer {self.auth_token}"
            ''')
            
            # Find CREDITS balance
            CREDITS_balance = None
            for balance in listing_data.get("balances", []):
                if balance["asset_name"] == "CREDITS":
                    CREDITS_balance = balance
                    break
            
            if CREDITS_balance:
                confirmed = float(CREDITS_balance["confirmed_balance"])
                pending = float(CREDITS_balance["pending_balance"])
                logger.info(f"CREDITS Balance - Confirmed: {confirmed}, Pending: {pending}")
                
                if confirmed >= 2.0:
                    logger.info(f"Transaction confirmed with {self.min_confirmations} confirmations")
                    break
                elif pending >= 2.0:
                    logger.info("Transaction detected in mempool, waiting for confirmation...")
                    logger.info(f"This may take approximately {self.min_confirmations} minutes...")
                else:
                    logger.info("Waiting for transaction to be detected...")
            
            await asyncio.sleep(10)  # Check every 10 seconds

        logger.info("Funding completed and confirmed")

    async def update_listing(self):
        """Update the test listing."""
        logger.info("Updating test listing...")
        
        update_resp = self.run_cmd(f'''
            curl -s -L -X PATCH {self.api_url}/listings/{self.listing_id} \\
                -H "Content-Type: application/json" \\
                -H "Authorization: Bearer {self.auth_token}" \\
                -d '{{
                    "name": "Updated CREDITS Listing",
                    "description": "An updated test listing",
                    "tags": ["test", "CREDITS", "updated"],
                    "prices": [{{
                        "asset_name": "CREDITS",
                        "price_evr": 80,
                        "units": 6
                    }}]
                }}'
        ''')
        
        logger.info(f"Listing update response: {update_resp}")
        
        # Verify update
        updated_listing = self.run_cmd(f'''
            curl -s -X GET {self.api_url}/listings/by-id/{self.listing_id} \\
                -H "Authorization: Bearer {self.auth_token}"
        ''')
        
        if updated_listing.get("name") != "Updated CREDITS Listing":
            raise ValueError("Failed to update listing")
        
        logger.info("Listing updated successfully")

    async def manage_listing_status(self):
        """Test pausing and resuming the listing."""
        logger.info("Testing listing status management...")
        
        # Pause listing
        pause_resp = self.run_cmd(f'''
            curl -s -L -X POST {self.api_url}/listings/{self.listing_id}/pause \\
                -H "Content-Type: application/json" \\
                -H "Authorization: Bearer {self.auth_token}"
        ''')
        
        logger.info(f"Pause response: {pause_resp}")
        
        # Verify paused status
        paused_listing = self.run_cmd(f'''
            curl -s -X GET {self.api_url}/listings/by-id/{self.listing_id} \\
                -H "Authorization: Bearer {self.auth_token}"
        ''')
        
        if paused_listing.get("status") != "paused":
            raise ValueError("Failed to pause listing")
        
        logger.info("Listing paused successfully")
        
        await asyncio.sleep(2)  # Wait a bit before resuming
        
        # Resume listing
        resume_resp = self.run_cmd(f'''
            curl -s -L -X POST {self.api_url}/listings/{self.listing_id}/resume \\
                -H "Content-Type: application/json" \\
                -H "Authorization: Bearer {self.auth_token}"
        ''')
        
        logger.info(f"Resume response: {resume_resp}")
        
        # Verify resumed status
        resumed_listing = self.run_cmd(f'''
            curl -s -X GET {self.api_url}/listings/by-id/{self.listing_id} \\
                -H "Authorization: Bearer {self.auth_token}"
        ''')
        
        if resumed_listing.get("status") != "active":
            raise ValueError("Failed to resume listing")
        
        logger.info("Listing resumed successfully")

    async def create_order(self):
        """Create and process a test order."""
        logger.info("Creating test order...")
        
        try:
            # Get current listing data
            listing_data = self.run_cmd(f'''
                curl -s -X GET {self.api_url}/listings/by-id/{self.listing_id}
            ''')
            
            logger.info(f"Current listing status: {listing_data.get('status', 'unknown')}")
            
            if listing_data.get('status') != 'active':
                raise ValueError(f"Listing is not active (status: {listing_data.get('status')})")

            # Authenticate as buyer
            logger.info("Authenticating as buyer...")
            
            # 1. Get challenge message
            challenge_resp = self.run_cmd(f'''
                curl -s -X POST {self.api_url}/auth/challenge \\
                    -H "Content-Type: application/json" \\
                    -d '{{"address": "{self.buyer_address}"}}'
            ''')
            
            challenge_id = challenge_resp["challenge_id"]
            message = challenge_resp["message"]
            
            # 2. Sign message with evrmore-cli
            signature = self.run_cmd(f'evrmore-cli signmessage "{self.buyer_address}" "{message}"')["output"]
            
            # 3. Submit signature to get JWT token
            auth_resp = self.run_cmd(f'''
                curl -s -X POST {self.api_url}/auth/login \\
                    -H "Content-Type: application/json" \\
                    -d '{{
                        "challenge_id": "{challenge_id}",
                        "address": "{self.buyer_address}",
                        "signature": "{signature}"
                    }}'
            ''')
            
            buyer_token = auth_resp["token"]
            logger.info("Buyer authentication successful")
            
            # Create order
            logger.info("Creating cart order with items:")
            logger.info(f"- CREDITS: 1.0 from listing {self.listing_id}")
            
            order_resp = self.run_cmd(f'''
                curl -s -X POST "{self.api_url}/orders/cart" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer {buyer_token}" \\
                    -d '{{"buyer_address": "{self.buyer_address}", "items": [{{"listing_id": "{self.listing_id}", "asset_name": "CREDITS", "amount": 1.0}}]}}'
            ''')
            
            if "id" not in order_resp:
                logger.error(f"Failed to create order. Response: {order_resp}")
                raise ValueError(f"Invalid order response: {order_resp}")
                
            self.order_id = order_resp["id"]
            logger.info(f"Order created successfully with ID: {self.order_id}")
            logger.info(f"Order details: {json.dumps(order_resp, indent=2)}")
            
            # Send payment
            payment_amount = Decimal(str(order_resp["total_payment_evr"]))
            payment_address = order_resp["payment_address"]
            
            logger.info(f"Payment required: {payment_amount} EVR")
            logger.info(f"Payment address: {payment_address}")
            
            # Send EVR payment
            tx_hash = self.run_cmd(f'''
                evrmore-cli sendtoaddress "{payment_address}" {float(payment_amount)}
            ''')["output"]
            
            logger.info(f"Payment sent: {tx_hash}")
            logger.info(f"Waiting for payment to be confirmed (approximately {self.min_confirmations} minutes)...")
            
            # Wait for order to be processed
            max_wait = 600  # Maximum wait time in seconds (10 minutes)
            start_time = time.time()
            
            while True:
                if time.time() - start_time > max_wait:
                    raise TimeoutError("Order processing timed out")
                    
                # Get order status
                order_status = self.run_cmd(f'''
                    curl -s -X GET "{self.api_url}/orders/cart/{self.order_id}"
                ''')
                
                status = order_status.get("status")
                required_payment = order_status.get("required_payment", "unknown")
                logger.info(f"Order status: {status}")
                logger.info(f"Required payment: {required_payment} EVR")
                
                # Get payment balances
                balances = self.run_cmd(f'''
                    curl -s -X GET "{self.api_url}/orders/cart/{self.order_id}/balances"
                ''')
                
                if balances:
                    logger.info("Payment balances:")
                    for asset, balance in balances.items():
                        logger.info(f"  {asset}:")
                        logger.info(f"    Confirmed: {balance.get('confirmed_balance', '0')}")
                        logger.info(f"    Pending: {balance.get('pending_balance', '0')}")
                        if 'required_amount' in balance:
                            logger.info(f"    Required: {balance.get('required_amount')}")
                
                if status == "completed":
                    logger.info("Order completed successfully")
                    logger.info(f"Final order details: {json.dumps(order_status, indent=2)}")
                    
                    # Verify balances after order
                    logger.info("Verifying final listing balances...")
                    
                    # Monitor balances for several rounds
                    monitoring_rounds = 5
                    monitoring_interval = 10  # seconds
                    
                    for round_num in range(monitoring_rounds):
                        logger.info(f"\nBalance monitoring round {round_num + 1}/{monitoring_rounds}")
                        
                        listing_data = self.run_cmd(f'''
                            curl -s -X GET {self.api_url}/listings/by-id/{self.listing_id} \\
                                -H "Authorization: Bearer {self.auth_token}"
                        ''')
                        
                        # Show all balances
                        logger.info("Current listing balances:")
                        for balance in listing_data.get("balances", []):
                            asset_name = balance["asset_name"]
                            confirmed = Decimal(balance["confirmed_balance"])
                            pending = Decimal(balance["pending_balance"])
                            logger.info(f"  {asset_name}:")
                            logger.info(f"    Confirmed: {confirmed}")
                            logger.info(f"    Pending: {pending}")
                            
                            # Specific check for CREDITS balance
                            if asset_name == "CREDITS":
                                if confirmed != Decimal("1.0"):  # Should be 2.0 - 1.0 from order
                                    logger.warning(f"Unexpected CREDITS balance: {confirmed} (expected 1.0)")
                        
                        if round_num < monitoring_rounds - 1:  # Don't sleep on last round
                            logger.info(f"Waiting {monitoring_interval} seconds before next balance check...")
                            await asyncio.sleep(monitoring_interval)
                        
                    break
                elif status == "failed":
                    logger.error(f"Order failed. Details: {json.dumps(order_status, indent=2)}")
                    raise ValueError("Order processing failed")
                    
                await asyncio.sleep(10)  # Check every 10 seconds
            
        except Exception as e:
            logger.error(f"Error in order creation/processing: {e}")
            
            # Even if order failed, monitor balances
            logger.info("\nMonitoring balances after error...")
            try:
                for round_num in range(monitoring_rounds):
                    logger.info(f"\nBalance monitoring round {round_num + 1}/{monitoring_rounds}")
                    
                    listing_data = self.run_cmd(f'''
                        curl -s -X GET {self.api_url}/listings/by-id/{self.listing_id} \\
                            -H "Authorization: Bearer {self.auth_token}"
                    ''')
                    
                    logger.info("Current listing balances:")
                    for balance in listing_data.get("balances", []):
                        asset_name = balance["asset_name"]
                        confirmed = Decimal(balance["confirmed_balance"])
                        pending = Decimal(balance["pending_balance"])
                        logger.info(f"  {asset_name}:")
                        logger.info(f"    Confirmed: {confirmed}")
                        logger.info(f"    Pending: {pending}")
                    
                    if round_num < monitoring_rounds - 1:
                        logger.info(f"Waiting {monitoring_interval} seconds before next balance check...")
                        await asyncio.sleep(monitoring_interval)
                        
            except Exception as monitor_error:
                logger.error(f"Error monitoring balances after failure: {monitor_error}")
            
            raise

    async def create_featured_listing(self):
        """Test creating a featured listing."""
        logger.info("Testing featured listing creation...")
        
        # Get available plans
        plans_resp = self.run_cmd(f'''
            curl -s -X GET {self.api_url}/listings/featured/plans \\
                -H "Authorization: Bearer {self.auth_token}"
        ''')
        
        logger.info(f"Available featured plans: {plans_resp}")
        
        # Create featured payment for basic plan
        payment_resp = self.run_cmd(f'''
            curl -s -L -X POST {self.api_url}/listings/featured/payments \\
                -H "Content-Type: application/json" \\
                -H "Authorization: Bearer {self.auth_token}" \\
                -d '{{
                    "listing_id": "{self.listing_id}",
                    "plan_name": "basic"
                }}'
        ''')
        
        logger.info(f"Featured payment response: {payment_resp}")
        
        payment_id = payment_resp.get("id")
        payment_address = payment_resp.get("payment_address")
        amount_evr = payment_resp.get("amount_evr")
        
        if not all([payment_id, payment_address, amount_evr]):
            raise ValueError("Featured payment creation failed")
            
        logger.info(f"Created featured payment: {payment_id}")
        logger.info(f"Payment address: {payment_address}")
        logger.info(f"Amount required: {amount_evr} EVR")

    async def run_test(self):
        """Run the comprehensive frontend client test."""
        try:
            # Setup test environment
            await self.setup()
            
            # Run test flow
            await self.authenticate()
            
            # Only create and fund listing if we don't have a valid saved one
            if not self.listing_id:
                logger.info("No valid saved listing found, creating new one...")
                await self.create_listing()
                await self.fund_listing()
            else:
                logger.info(f"Using existing listing {self.listing_id}")
            
            await self.update_listing()
            await self.manage_listing_status()
            await self.create_order()
            await self.create_featured_listing()
            
            logger.info("Test completed successfully!")
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            raise

if __name__ == "__main__":
    # Run the test
    test = FrontendClientTest()
    try:
        asyncio.run(test.run_test())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 