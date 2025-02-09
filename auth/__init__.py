"""Authentication module using cryptographic challenges and RPC verification.

This module provides:
1. Challenge creation and verification using Evrmore's message signing
2. Single active session per address
3. Middleware for protecting routes
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from database import get_pool
from rpc import verifymessage, RPCError

# Configure logging
logger = logging.getLogger(__name__)

# Constants
CHALLENGE_EXPIRY_MINUTES = 5
SESSION_EXPIRY_DAYS = 30
JWT_SECRET = secrets.token_urlsafe(32)  # Generate random secret on startup
JWT_ALGORITHM = "HS256"

class AuthError(Exception):
    """Base exception for authentication errors."""
    pass

class ChallengeExpiredError(AuthError):
    """Raised when a challenge has expired."""
    pass

class ChallengeUsedError(AuthError):
    """Raised when a challenge has already been used."""
    pass

class InvalidSignatureError(AuthError):
    """Raised when message signature verification fails."""
    pass

class SessionExpiredError(AuthError):
    """Raised when a session has expired."""
    pass

class AuthManager:
    """Manages authentication challenges and sessions."""
    
    def __init__(self, pool=None):
        """Initialize auth manager.
        
        Args:
            pool: Optional database pool. If not provided, will get from database module.
        """
        self.pool = pool
    
    async def ensure_pool(self):
        """Ensure database pool is available."""
        if not self.pool:
            self.pool = await get_pool()
    
    async def create_challenge(self, address: str) -> Dict[str, Any]:
        """Create a new authentication challenge.
        
        Args:
            address: The Evrmore address to authenticate
            
        Returns:
            Dict containing:
                - challenge_id: UUID of challenge
                - message: Message to sign
                - expires_at: Challenge expiration timestamp
        """
        await self.ensure_pool()
        
        try:
            # Generate random challenge message
            challenge = f"Sign this message to authenticate: {secrets.token_hex(16)}"
            expires_at = datetime.utcnow() + timedelta(minutes=CHALLENGE_EXPIRY_MINUTES)
            
            async with self.pool.acquire() as conn:
                challenge_id = await conn.fetchval(
                    '''
                    INSERT INTO auth_challenges (
                        address, challenge, expires_at
                    ) VALUES ($1, $2, $3)
                    RETURNING id
                    ''',
                    address,
                    challenge,
                    expires_at
                )
                
                return {
                    'challenge_id': str(challenge_id),
                    'message': challenge,
                    'expires_at': expires_at.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            raise AuthError(f"Failed to create challenge: {str(e)}")
    
    async def verify_challenge(
        self,
        challenge_id: str,
        address: str,
        signature: str,
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """Verify a challenge signature and create session.
        
        Args:
            challenge_id: UUID of the challenge
            address: The Evrmore address that signed
            signature: The signature to verify
            request: Optional request object for session metadata
            
        Returns:
            Dict containing:
                - token: Session token for future requests
                - expires_at: Session expiration timestamp
                
        Raises:
            ChallengeExpiredError: If challenge has expired
            ChallengeUsedError: If challenge was already used
            InvalidSignatureError: If signature verification fails
        """
        await self.ensure_pool()
        
        try:
            async with self.pool.acquire() as conn:
                # Get challenge
                challenge = await conn.fetchrow(
                    '''
                    SELECT 
                        challenge,
                        expires_at,
                        used
                    FROM auth_challenges
                    WHERE id = $1 AND address = $2
                    ''',
                    challenge_id,
                    address
                )
                
                if not challenge:
                    raise AuthError("Challenge not found")
                    
                # Check expiry
                if challenge['expires_at'] < datetime.utcnow():
                    raise ChallengeExpiredError("Challenge has expired")
                    
                # Check if already used
                if challenge['used']:
                    raise ChallengeUsedError("Challenge has already been used")
                
                # Verify signature using RPC
                try:
                    valid = verifymessage(address, signature, challenge['challenge'])
                    if not valid:
                        raise InvalidSignatureError("Invalid signature")
                except RPCError as e:
                    raise InvalidSignatureError(f"RPC error: {str(e)}")
                
                # Mark challenge as used
                await conn.execute(
                    '''
                    UPDATE auth_challenges
                    SET used = true
                    WHERE id = $1
                    ''',
                    challenge_id
                )
                
                # Create session
                expires_at = datetime.utcnow() + timedelta(days=SESSION_EXPIRY_DAYS)
                
                # Generate session token using JWT
                token = jwt.encode(
                    {
                        'sub': address,
                        'exp': expires_at.timestamp()
                    },
                    JWT_SECRET,
                    algorithm=JWT_ALGORITHM
                )
                
                # Revoke any existing sessions for this address
                await conn.execute(
                    '''
                    UPDATE auth_sessions
                    SET revoked = true
                    WHERE address = $1
                    ''',
                    address
                )
                
                # Store new session
                await conn.execute(
                    '''
                    INSERT INTO auth_sessions (
                        address, token, expires_at,
                        user_agent, ip_address
                    ) VALUES ($1, $2, $3, $4, $5)
                    ''',
                    address,
                    token,
                    expires_at,
                    request.headers.get('user-agent') if request else None,
                    request.client.host if request else None
                )
                
                return {
                    'token': token,
                    'expires_at': expires_at.isoformat()
                }
                
        except (ChallengeExpiredError, ChallengeUsedError, InvalidSignatureError):
            raise
        except Exception as e:
            logger.error(f"Error verifying challenge: {e}")
            raise AuthError(f"Failed to verify challenge: {str(e)}")
    
    async def verify_session(
        self,
        token: str,
        request: Optional[Request] = None,
        required_address: Optional[str] = None
    ) -> str:
        """Verify a session token.
        
        Args:
            token: The session token to verify
            request: Optional request object for updating session metadata
            required_address: Optional address that must match the token's address
            
        Returns:
            The authenticated address
            
        Raises:
            SessionExpiredError: If session has expired
            AuthError: For other verification errors
        """
        await self.ensure_pool()
        
        try:
            # Decode JWT
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                address = payload['sub']
                
                # If a specific address is required, verify it matches
                if required_address and address.lower() != required_address.lower():
                    raise AuthError("Token does not match required address")
                    
            except jwt.ExpiredSignatureError:
                raise SessionExpiredError("Session has expired")
            except jwt.JWTError as e:
                raise AuthError(f"Invalid token: {str(e)}")
            
            async with self.pool.acquire() as conn:
                # Verify session exists and is valid
                session = await conn.fetchrow(
                    '''
                    SELECT 
                        expires_at,
                        revoked
                    FROM auth_sessions
                    WHERE address = $1 AND token = $2
                    AND NOT revoked
                    ''',
                    address,
                    token
                )
                
                if not session:
                    raise AuthError("Session not found or revoked")
                    
                # Check expiry
                if session['expires_at'] < datetime.utcnow():
                    raise SessionExpiredError("Session has expired")
                
                # Update last used timestamp and metadata if request provided
                if request:
                    await conn.execute(
                        '''
                        UPDATE auth_sessions
                        SET 
                            last_used_at = now(),
                            user_agent = $2,
                            ip_address = $3
                        WHERE address = $1
                        AND NOT revoked
                        ''',
                        address,
                        request.headers.get('user-agent'),
                        request.client.host
                    )
                
                return address
                
        except SessionExpiredError:
            raise
        except Exception as e:
            logger.error(f"Error verifying session: {e}")
            raise AuthError(f"Failed to verify session: {str(e)}")
    
    async def logout(self, address: str):
        """Log out by revoking the active session.
        
        Args:
            address: Address to log out
        """
        await self.ensure_pool()
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    '''
                    UPDATE auth_sessions
                    SET revoked = true
                    WHERE address = $1
                    AND NOT revoked
                    ''',
                    address
                )
        except Exception as e:
            logger.error(f"Error logging out: {e}")
            raise AuthError(f"Failed to log out: {str(e)}")

    async def clear_all_sessions(self, address: str):
        """Clear all sessions for an address.
        
        Args:
            address: Address to clear sessions for
        """
        await self.ensure_pool()
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    '''
                    UPDATE auth_sessions
                    SET 
                        revoked = true,
                        revoked_at = now()
                    WHERE address = $1
                    AND NOT revoked
                    ''',
                    address
                )
        except Exception as e:
            logger.error(f"Error clearing sessions: {e}")
            raise AuthError(f"Failed to clear sessions: {str(e)}")

# Create global instance
manager = AuthManager()

# FastAPI security scheme
auth_scheme = HTTPBearer(
    auto_error=True,  # Return 401 automatically if token is missing
    description="JWT Bearer token required"
)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    request: Request = None
) -> str:
    """FastAPI dependency for getting authenticated user.
    
    Args:
        credentials: Bearer token credentials
        request: The FastAPI request
        
    Returns:
        The authenticated address
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        return await manager.verify_session(credentials.credentials, request)
    except SessionExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired"
        )
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

# Export public interface
__all__ = [
    'manager',
    'get_current_user',
    'AuthError',
    'ChallengeExpiredError',
    'ChallengeUsedError',
    'InvalidSignatureError',
    'SessionExpiredError'
] 