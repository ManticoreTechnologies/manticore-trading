"""Test script to simulate frontend client interactions with the profile API endpoints."""

import asyncio
import logging
import json
import subprocess
import os
from config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProfileClientTest:
    """Test harness that simulates frontend client interactions with profile endpoints."""
    
    def __init__(self):
        self.api_url = "http://localhost:8000"
        
        # Test data storage
        self.test_address = None
        self.auth_token = None
        
        # Load config
        self.config = load_config()

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
        
        # Generate test address
        self.test_address = self.run_cmd("evrmore-cli getnewaddress")["output"]
        logger.info(f"Generated test address: {self.test_address}")

    async def authenticate(self) -> str:
        """Simulate frontend authentication flow using curl."""
        logger.info("Starting authentication flow...")
        
        # 1. Get challenge message
        challenge_resp = self.run_cmd(f'''
            curl -s -X POST {self.api_url}/auth/challenge \\
                -H "Content-Type: application/json" \\
                -d '{{"address": "{self.test_address}"}}'
        ''')
        
        if 'challenge_id' not in challenge_resp or 'message' not in challenge_resp:
            raise ValueError(f"Invalid challenge response: {challenge_resp}")
        
        challenge_id = challenge_resp["challenge_id"]
        message = challenge_resp["message"]
        
        # 2. Sign message with evrmore-cli
        signature = self.run_cmd(f'evrmore-cli signmessage "{self.test_address}" "{message}"')["output"]
        
        # 3. Submit signature to get JWT token
        auth_resp = self.run_cmd(f'''
            curl -s -X POST {self.api_url}/auth/login \\
                -H "Content-Type: application/json" \\
                -d '{{
                    "challenge_id": "{challenge_id}",
                    "address": "{self.test_address}",
                    "signature": "{signature}"
                }}'
        ''')
        
        if 'token' not in auth_resp:
            raise ValueError(f"Invalid auth response: {auth_resp}")
        
        self.auth_token = auth_resp["token"]
        logger.info("Authentication successful")
        return self.auth_token

    async def get_profile(self):
        """Test getting the user's profile."""
        logger.info("Getting user profile...")
        
        profile_resp = self.run_cmd(f'''
            curl -s -X GET {self.api_url}/profile/ \\
                -H "Authorization: Bearer {self.auth_token}"
        ''')
        
        logger.info(f"Initial profile: {json.dumps(profile_resp, indent=2)}")
        return profile_resp

    async def update_profile(self):
        """Test updating the user's profile."""
        logger.info("Updating user profile...")
        
        update_resp = self.run_cmd(f'''
            curl -s -X PATCH {self.api_url}/profile/ \\
                -H "Content-Type: application/json" \\
                -H "Authorization: Bearer {self.auth_token}" \\
                -d '{{
                    "friendly_name": "Test User",
                    "bio": "This is a test profile for automated testing"
                }}'
        ''')
        
        logger.info(f"Profile update response: {update_resp}")
        
        # Verify update
        updated_profile = await self.get_profile()
        if updated_profile.get("friendly_name") != "Test User":
            raise ValueError("Failed to update profile")
        
        logger.info("Profile updated successfully")

    async def upload_profile_image(self):
        """Test uploading a profile image."""
        logger.info("Testing profile image upload...")
        
        # Create a test image file
        test_image = "test_profile.png"
        try:
            # Create a small test PNG file
            with open(test_image, 'wb') as f:
                # Simple 1x1 black PNG
                f.write(bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63640000000006000557bfabc6000000049454e44ae426082'))
            
            # Upload image
            upload_resp = self.run_cmd(f'''
                curl -s -X POST {self.api_url}/profile/image \\
                    -H "Authorization: Bearer {self.auth_token}" \\
                    -F "file=@{test_image};type=image/png"
            ''')
            
            logger.info(f"Image upload response: {upload_resp}")
            
            if 'ipfs_hash' not in upload_resp:
                raise ValueError("Failed to upload profile image")
                
            # Verify profile was updated with new image hash
            updated_profile = await self.get_profile()
            if not updated_profile.get("profile_ipfs"):
                raise ValueError("Profile image hash not updated")
                
            logger.info("Profile image uploaded successfully")
            
        finally:
            # Clean up test image
            if os.path.exists(test_image):
                os.remove(test_image)

    async def manage_favorite_assets(self):
        """Test adding and removing favorite assets."""
        logger.info("Testing favorite assets management...")
        
        # Add favorite asset
        add_resp = self.run_cmd(f'''
            curl -s -X POST {self.api_url}/profile/favorites \\
                -H "Content-Type: application/json" \\
                -H "Authorization: Bearer {self.auth_token}" \\
                -d '{{"asset_name": "TEST_ASSET"}}'
        ''')
        
        logger.info(f"Add favorite response: {add_resp}")
        
        # Verify asset was added
        profile = await self.get_profile()
        if "TEST_ASSET" not in profile.get("favorite_assets", []):
            raise ValueError("Failed to add favorite asset")
        
        logger.info("Favorite asset added successfully")
        
        # Remove favorite asset
        remove_resp = self.run_cmd(f'''
            curl -s -X DELETE {self.api_url}/profile/favorites/TEST_ASSET \\
                -H "Authorization: Bearer {self.auth_token}"
        ''')
        
        logger.info(f"Remove favorite response: {remove_resp}")
        
        # Verify asset was removed
        profile = await self.get_profile()
        if "TEST_ASSET" in profile.get("favorite_assets", []):
            raise ValueError("Failed to remove favorite asset")
        
        logger.info("Favorite asset removed successfully")

    async def run_test(self):
        """Run the comprehensive profile test flow."""
        try:
            # Setup test environment
            await self.setup()
            
            # Run test flow
            await self.authenticate()
            await self.get_profile()
            await self.update_profile()
            await self.upload_profile_image()
            await self.manage_favorite_assets()
            
            logger.info("Profile test completed successfully!")
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            raise

if __name__ == "__main__":
    # Run the test
    test = ProfileClientTest()
    try:
        asyncio.run(test.run_test())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise