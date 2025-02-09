"""Authentication API endpoints."""

from fastapi import APIRouter, HTTPException, Request, status, Depends, Security
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from auth import (
    manager, get_current_user, AuthError, ChallengeExpiredError,
    ChallengeUsedError, InvalidSignatureError, SessionExpiredError
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

class ChallengeRequest(BaseModel):
    """Request model for creating a challenge."""
    address: str

class ChallengeResponse(BaseModel):
    """Response model for challenge creation."""
    challenge_id: str
    message: str

class VerifyRequest(BaseModel):
    """Request model for verifying a challenge."""
    challenge_id: str
    address: str
    signature: str

class LoginResponse(BaseModel):
    """Response model for login."""
    token: str

@router.post("/challenge", response_model=ChallengeResponse)
async def create_challenge(request: ChallengeRequest):
    """Create a new authentication challenge."""
    try:
        result = await manager.create_challenge(request.address)
        return {
            "challenge_id": result["challenge_id"],
            "message": result["message"]
        }
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/login", response_model=LoginResponse)
async def login(request: VerifyRequest, fastapi_request: Request):
    """Verify a challenge signature and create session."""
    try:
        result = await manager.verify_challenge(
            request.challenge_id,
            request.address,
            request.signature,
            fastapi_request
        )
        return {"token": result["token"]}
    except ChallengeExpiredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Challenge has expired"
        )
    except ChallengeUsedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Challenge has already been used"
        )
    except InvalidSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/logout")
async def logout(address: str = Security(get_current_user)):
    """Log out the current user by revoking their session."""
    try:
        await manager.logout(address)
        return {"success": True}
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/verify")
async def verify_token(address: str = Security(get_current_user)):
    """Verify the current session token."""
    return {
        "valid": True,
        "address": address
    }

# Export the router
__all__ = ['router'] 