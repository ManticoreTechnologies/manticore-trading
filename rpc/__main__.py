"""Command line interface for testing RPC functionality"""
from . import (
    getblockcount, getblock, getblockhash, invalidmethod, help,
    NodeConnectionError, NodeAuthError, EvrmoreError
)

def test_rpc():
    """Test various RPC scenarios"""
    try:
        print("\nTesting valid commands:")
        print("-" * 50)
        
        # Test getblockcount (no parameters)
        print("1. Testing getblockcount:")
        block_count = getblockcount()
        print(f"  Success! Current block height: {block_count}")
        
        # Test getblockhash (with valid parameter)
        print("\n2. Testing getblockhash with valid height:")
        block_hash = getblockhash(1)
        print(f"  Success! Block hash: {block_hash}")
        
        # Test getblock (with result from getblockhash)
        print("\n3. Testing getblock with hash:")
        block = getblock(block_hash)
        print(f"  Success! Block data retrieved")
        print(f"  Time: {block.get('time')}")
        print(f"  Nonce: {block.get('nonce')}")
        print(f"  Transactions: {len(block.get('tx', []))}")
        
        print("\nTesting error scenarios:")
        print("-" * 50)
        
        # Test invalid method
        print("\n4. Testing non-existent method:")
        try:
            invalidmethod()
            print("  Error: Should have raised an exception!")
        except EvrmoreError as e:
            print(f"  Success! Got expected error: {e}")
        
        # Test invalid parameters
        print("\n5. Testing getblockhash with invalid height:")
        try:
            getblockhash(-1)
            print("  Error: Should have raised an exception!")
        except EvrmoreError as e:
            print(f"  Success! Got expected error: {e}")
        
        # Test help command
        print("\n6. Testing help command:")
        help_text = help()
        print(f"  Success! Got {len(help_text)} characters of help text")
        
    except NodeConnectionError as e:
        print("\nFailed to connect to Evrmore node:")
        print(f"  {str(e)}")
        
    except NodeAuthError as e:
        print("\nAuthentication failed:")
        print(f"  {str(e)}")
        print("\nPlease check your rpcuser and rpcpassword settings in evrmore.conf")
        
    except EvrmoreError as e:
        print(f"\nEvrmore Error [{e.code}] in {e.method}:")
        print(f"  {str(e)}")
        
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")

if __name__ == "__main__":
    test_rpc()
