"""RPC module for interacting with Evrmore node"""
import requests
from typing import Any, Dict, Optional
from config import evrmore_conf

class RPCError(Exception):
    """Base exception for RPC errors"""
    def __init__(self, message: str, code: Optional[int] = None, method: Optional[str] = None):
        self.code = code
        self.method = method
        super().__init__(f"RPC Error [{code}] in {method}: {message}" if code else message)

class NodeConnectionError(RPCError):
    """Raised when connection to node fails"""
    pass

class NodeAuthError(RPCError):
    """Raised when authentication failed"""
    pass

class EvrmoreError(RPCError):
    """Evrmore-specific error codes and messages
    
    Common error codes:
    -1  - General error during processing
    -3  - Asset not found
    -4  - Out of memory
    -5  - Invalid parameter
    -8  - Invalid parameter combination
    -20 - Invalid address or key
    -22 - Error parsing JSON
    -25 - Error processing transaction
    -26 - Transaction already in chain
    -27 - Transaction already in mempool
    """
    # Map of known Evrmore error codes to human-readable messages
    ERROR_MESSAGES = {
        -1: "General error during processing",
        -3: "Asset not found",
        -4: "Out of memory",
        -5: "Invalid parameter",
        -8: "Invalid parameter combination",
        -20: "Invalid address or key",
        -22: "Error parsing JSON",
        -25: "Error processing transaction",
        -26: "Transaction already in chain",
        -27: "Transaction already in mempool",
    }
    
    def __init__(self, message: str, code: int, method: str):
        self.code = code
        self.method = method
        # Get standard message for known error codes
        standard_msg = self.ERROR_MESSAGES.get(code, "Unknown error")
        # Combine standard message with specific message if different
        full_msg = f"{standard_msg} - {message}" if message != standard_msg else message
        super().__init__(full_msg, code, method)

class RPCMethod:
    """Descriptor class for RPC methods"""
    def __init__(self, method_name: str):
        self.method_name = method_name
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        
        def caller(*args, **kwargs) -> Any:
            return obj._call_method(self.method_name, *args, **kwargs)
        
        return caller

class EvrmoreRPC:
    """Evrmore RPC client"""
    
    def __init__(self):
        """Initialize RPC client with configuration from evrmore.conf"""
        self.rpc_user = evrmore_conf['rpcuser']
        self.rpc_password = evrmore_conf['rpcpassword']
        self.rpc_port = evrmore_conf['rpcport']
        
        # Use rpcbind from config, fallback to localhost if not specified
        self.rpc_host = evrmore_conf.get('rpcbind', '127.0.0.1')
        
        # Build RPC URL
        self.url = f"http://{self.rpc_host}:{self.rpc_port}"
        
        # Initialize session with auth
        self.session = requests.Session()
        self.session.auth = (self.rpc_user, self.rpc_password)
        self.session.headers['content-type'] = 'application/json'
        
        # Request ID counter
        self._request_id = 0
    
    def _get_request_id(self) -> int:
        """Get unique request ID"""
        self._request_id += 1
        return self._request_id
    
    def _call_method(self, method: str, *args) -> Any:
        """Make RPC call to Evrmore node
        
        Args:
            method: RPC method name
            *args: Method arguments
            
        Returns:
            Response from node
            
        Raises:
            NodeConnectionError: Connection to node failed
            NodeAuthError: Authentication failed
            EvrmoreError: Node returned an Evrmore-specific error
        """
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": args,
            "id": self._get_request_id()
        }
        
        try:
            response = self.session.post(self.url, json=payload, timeout=10)  # 10 second timeout
            
            # Check for auth error
            if response.status_code == 401:
                raise NodeAuthError("Authentication failed - check rpcuser/rpcpassword")
            
            # Try to parse response even if status code is error
            result = response.json()
            
            # Check for RPC error
            if 'error' in result and result['error'] is not None:
                error = result['error']
                raise EvrmoreError(
                    error.get('message', 'Unknown error'),
                    error.get('code', -1),
                    method
                )
            
            # Now check for HTTP errors after we've tried to parse potential error response
            response.raise_for_status()
                
            return result['result']
            
        except requests.exceptions.Timeout as e:
            raise NodeConnectionError(
                f"Request timed out after 10 seconds"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise NodeConnectionError(
                f"Failed to connect to Evrmore node at {self.url}"
            ) from e
        except requests.exceptions.HTTPError as e:
            # If we have a parsed error response, raise EvrmoreError
            if 'result' in locals() and isinstance(result, dict) and 'error' in result and result['error']:
                error = result['error']
                raise EvrmoreError(
                    error.get('message', 'Unknown error'),
                    error.get('code', -1),
                    method
                ) from e
            raise NodeConnectionError(
                f"HTTP error occurred: {str(e)}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise NodeConnectionError(
                f"Request failed: {str(e)}"
            ) from e
        except (KeyError, ValueError) as e:
            raise NodeConnectionError(
                f"Invalid response format: {str(e)}"
            ) from e
    
    # Define RPC methods as descriptors
    # Blockchain methods
    getbestblockhash = RPCMethod('getbestblockhash')
    getblock = RPCMethod('getblock')
    getblockchaininfo = RPCMethod('getblockchaininfo')
    getblockcount = RPCMethod('getblockcount')
    getblockhash = RPCMethod('getblockhash')
    getblockheader = RPCMethod('getblockheader')
    getchaintips = RPCMethod('getchaintips')
    getdifficulty = RPCMethod('getdifficulty')
    getmempoolinfo = RPCMethod('getmempoolinfo')
    getrawmempool = RPCMethod('getrawmempool')
    gettxout = RPCMethod('gettxout')
    gettxoutsetinfo = RPCMethod('gettxoutsetinfo')
    verifychain = RPCMethod('verifychain')
    
    # Network methods
    getnetworkinfo = RPCMethod('getnetworkinfo')
    getpeerinfo = RPCMethod('getpeerinfo')
    getconnectioncount = RPCMethod('getconnectioncount')
    ping = RPCMethod('ping')
    
    # Asset methods
    getassetdata = RPCMethod('getassetdata')
    getcacheinfo = RPCMethod('getcacheinfo')
    getsnapshot = RPCMethod('getsnapshot')
    issue = RPCMethod('issue')
    issueunique = RPCMethod('issueunique')
    listaddressesbyasset = RPCMethod('listaddressesbyasset')
    listassetbalancesbyaddress = RPCMethod('listassetbalancesbyaddress')
    listassets = RPCMethod('listassets')
    listmyassets = RPCMethod('listmyassets')
    reissue = RPCMethod('reissue')
    transfer = RPCMethod('transfer')
    transferfromaddress = RPCMethod('transferfromaddress')
    transferfromaddresses = RPCMethod('transferfromaddresses')
    
    # Wallet methods
    abandontransaction = RPCMethod('abandontransaction')
    addmultisigaddress = RPCMethod('addmultisigaddress')
    addwitnessaddress = RPCMethod('addwitnessaddress')
    backupwallet = RPCMethod('backupwallet')
    dumpprivkey = RPCMethod('dumpprivkey')
    dumpwallet = RPCMethod('dumpwallet')
    encryptwallet = RPCMethod('encryptwallet')
    getaccount = RPCMethod('getaccount')
    getaccountaddress = RPCMethod('getaccountaddress')
    getaddressesbyaccount = RPCMethod('getaddressesbyaccount')
    getaddressutxos = RPCMethod('getaddressutxos')
    getaddressdeltas = RPCMethod('getaddressdeltas')
    getbalance = RPCMethod('getbalance')
    getnewaddress = RPCMethod('getnewaddress')
    getrawchangeaddress = RPCMethod('getrawchangeaddress')
    getreceivedbyaccount = RPCMethod('getreceivedbyaccount')
    getreceivedbyaddress = RPCMethod('getreceivedbyaddress')
    gettransaction = RPCMethod('gettransaction')
    getunconfirmedbalance = RPCMethod('getunconfirmedbalance')
    getwalletinfo = RPCMethod('getwalletinfo')
    importaddress = RPCMethod('importaddress')
    importprivkey = RPCMethod('importprivkey')
    importprunedfunds = RPCMethod('importprunedfunds')
    importpubkey = RPCMethod('importpubkey')
    importwallet = RPCMethod('importwallet')
    keypoolrefill = RPCMethod('keypoolrefill')
    listaccounts = RPCMethod('listaccounts')
    listaddressgroupings = RPCMethod('listaddressgroupings')
    listlockunspent = RPCMethod('listlockunspent')
    listreceivedbyaccount = RPCMethod('listreceivedbyaccount')
    listreceivedbyaddress = RPCMethod('listreceivedbyaddress')
    listsinceblock = RPCMethod('listsinceblock')
    listtransactions = RPCMethod('listtransactions')
    listunspent = RPCMethod('listunspent')
    lockunspent = RPCMethod('lockunspent')
    move = RPCMethod('move')
    removeprunedfunds = RPCMethod('removeprunedfunds')
    sendfrom = RPCMethod('sendfrom')
    sendmany = RPCMethod('sendmany')
    sendtoaddress = RPCMethod('sendtoaddress')
    setaccount = RPCMethod('setaccount')
    settxfee = RPCMethod('settxfee')
    signmessage = RPCMethod('signmessage')
    walletlock = RPCMethod('walletlock')
    walletpassphrase = RPCMethod('walletpassphrase')
    walletpassphrasechange = RPCMethod('walletpassphrasechange')
    
    # Raw transaction methods
    createrawtransaction = RPCMethod('createrawtransaction')
    decoderawtransaction = RPCMethod('decoderawtransaction')
    decodescript = RPCMethod('decodescript')
    fundrawtransaction = RPCMethod('fundrawtransaction')
    getrawtransaction = RPCMethod('getrawtransaction')
    sendrawtransaction = RPCMethod('sendrawtransaction')
    signrawtransaction = RPCMethod('signrawtransaction')
    
    # Mining methods
    getmininginfo = RPCMethod('getmininginfo')
    getnetworkhashps = RPCMethod('getnetworkhashps')
    prioritisetransaction = RPCMethod('prioritisetransaction')
    submitblock = RPCMethod('submitblock')
    
    # Utility methods
    createmultisig = RPCMethod('createmultisig')
    estimatefee = RPCMethod('estimatefee')
    estimatepriority = RPCMethod('estimatepriority')
    validateaddress = RPCMethod('validateaddress')
    verifymessage = RPCMethod('verifymessage')
    help = RPCMethod('help')
    uptime = RPCMethod('uptime')

# Create global instance
client = EvrmoreRPC()

# Export methods at module level
# Blockchain methods
getbestblockhash = client.getbestblockhash
getblock = client.getblock
getblockchaininfo = client.getblockchaininfo
getblockcount = client.getblockcount
getblockhash = client.getblockhash
getblockheader = client.getblockheader
getchaintips = client.getchaintips
getdifficulty = client.getdifficulty
getmempoolinfo = client.getmempoolinfo
getrawmempool = client.getrawmempool
gettxout = client.gettxout
gettxoutsetinfo = client.gettxoutsetinfo
verifychain = client.verifychain

# Network methods
getnetworkinfo = client.getnetworkinfo
getpeerinfo = client.getpeerinfo
getconnectioncount = client.getconnectioncount
ping = client.ping

# Asset methods
getassetdata = client.getassetdata
getcacheinfo = client.getcacheinfo
getsnapshot = client.getsnapshot
issue = client.issue
issueunique = client.issueunique
listaddressesbyasset = client.listaddressesbyasset
listassetbalancesbyaddress = client.listassetbalancesbyaddress
listassets = client.listassets
listmyassets = client.listmyassets
reissue = client.reissue
transfer = client.transfer
transferfromaddress = client.transferfromaddress
transferfromaddresses = client.transferfromaddresses

# Wallet methods
abandontransaction = client.abandontransaction
addmultisigaddress = client.addmultisigaddress
addwitnessaddress = client.addwitnessaddress
backupwallet = client.backupwallet
dumpprivkey = client.dumpprivkey
dumpwallet = client.dumpwallet
encryptwallet = client.encryptwallet
getaccount = client.getaccount
getaccountaddress = client.getaccountaddress
getaddressesbyaccount = client.getaddressesbyaccount
getaddressutxos = client.getaddressutxos
getaddressdeltas = client.getaddressdeltas
getbalance = client.getbalance
getnewaddress = client.getnewaddress
getrawchangeaddress = client.getrawchangeaddress
getreceivedbyaccount = client.getreceivedbyaccount
getreceivedbyaddress = client.getreceivedbyaddress
gettransaction = client.gettransaction
getunconfirmedbalance = client.getunconfirmedbalance
getwalletinfo = client.getwalletinfo
importaddress = client.importaddress
importprivkey = client.importprivkey
importprunedfunds = client.importprunedfunds
importpubkey = client.importpubkey
importwallet = client.importwallet
keypoolrefill = client.keypoolrefill
listaccounts = client.listaccounts
listaddressgroupings = client.listaddressgroupings
listlockunspent = client.listlockunspent
listreceivedbyaccount = client.listreceivedbyaccount
listreceivedbyaddress = client.listreceivedbyaddress
listsinceblock = client.listsinceblock
listtransactions = client.listtransactions
listunspent = client.listunspent
lockunspent = client.lockunspent
move = client.move
removeprunedfunds = client.removeprunedfunds
sendfrom = client.sendfrom
sendmany = client.sendmany
sendtoaddress = client.sendtoaddress
setaccount = client.setaccount
settxfee = client.settxfee
signmessage = client.signmessage
walletlock = client.walletlock
walletpassphrase = client.walletpassphrase
walletpassphrasechange = client.walletpassphrasechange

# Raw transaction methods
createrawtransaction = client.createrawtransaction
decoderawtransaction = client.decoderawtransaction
decodescript = client.decodescript
fundrawtransaction = client.fundrawtransaction
getrawtransaction = client.getrawtransaction
sendrawtransaction = client.sendrawtransaction
signrawtransaction = client.signrawtransaction

# Mining methods
getmininginfo = client.getmininginfo
getnetworkhashps = client.getnetworkhashps
prioritisetransaction = client.prioritisetransaction
submitblock = client.submitblock

# Utility methods
createmultisig = client.createmultisig
estimatefee = client.estimatefee
estimatepriority = client.estimatepriority
validateaddress = client.validateaddress
verifymessage = client.verifymessage
help = client.help
uptime = client.uptime

# Export all methods and error types
__all__ = [
    # Error types
    'RPCError',
    'NodeConnectionError',
    'NodeAuthError',
    'EvrmoreError',
    
    # Blockchain methods
    'getbestblockhash',
    'getblock',
    'getblockchaininfo',
    'getblockcount',
    'getblockhash',
    'getblockheader',
    'getchaintips',
    'getdifficulty',
    'getmempoolinfo',
    'getrawmempool',
    'gettxout',
    'gettxoutsetinfo',
    'verifychain',
    
    # Network methods
    'getnetworkinfo',
    'getpeerinfo',
    'getconnectioncount',
    'ping',
    
    # Asset methods
    'getassetdata',
    'getcacheinfo',
    'getsnapshot',
    'issue',
    'issueunique',
    'listaddressesbyasset',
    'listassetbalancesbyaddress',
    'listassets',
    'listmyassets',
    'reissue',
    'transfer',
    'transferfromaddress',
    'transferfromaddresses',
    
    # Wallet methods
    'abandontransaction',
    'addmultisigaddress',
    'addwitnessaddress',
    'backupwallet',
    'dumpprivkey',
    'dumpwallet',
    'encryptwallet',
    'getaccount',
    'getaccountaddress',
    'getaddressesbyaccount',
    'getaddressutxos',
    'getaddressdeltas',
    'getbalance',
    'getnewaddress',
    'getrawchangeaddress',
    'getreceivedbyaccount',
    'getreceivedbyaddress',
    'gettransaction',
    'getunconfirmedbalance',
    'getwalletinfo',
    'importaddress',
    'importprivkey',
    'importprunedfunds',
    'importpubkey',
    'importwallet',
    'keypoolrefill',
    'listaccounts',
    'listaddressgroupings',
    'listlockunspent',
    'listreceivedbyaccount',
    'listreceivedbyaddress',
    'listsinceblock',
    'listtransactions',
    'listunspent',
    'lockunspent',
    'move',
    'removeprunedfunds',
    'sendfrom',
    'sendmany',
    'sendtoaddress',
    'setaccount',
    'settxfee',
    'signmessage',
    'walletlock',
    'walletpassphrase',
    'walletpassphrasechange',
    
    # Raw transaction methods
    'createrawtransaction',
    'decoderawtransaction',
    'decodescript',
    'fundrawtransaction',
    'getrawtransaction',
    'sendrawtransaction',
    'signrawtransaction',
    
    # Mining methods
    'getmininginfo',
    'getnetworkhashps',
    'prioritisetransaction',
    'submitblock',
    
    # Utility methods
    'createmultisig',
    'estimatefee',
    'estimatepriority',
    'validateaddress',
    'verifymessage',
    'help',
    'uptime'
]