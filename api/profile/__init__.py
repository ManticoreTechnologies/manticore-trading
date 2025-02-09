"""Profile management endpoints."""

from fastapi import APIRouter, HTTPException, Security, UploadFile, File, status, Form
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import aiofiles
import hashlib
import os

from auth import get_current_user
from database import get_pool

router = APIRouter(
    prefix="/profile",
    tags=["Profile"]
)

class Profile(BaseModel):
    """Model for user profile data."""
    address: str
    friendly_name: str
    bio: str
    profile_ipfs: str
    status: str
    favorite_assets: List[str]

class ProfileUpdate(BaseModel):
    """Model for profile updates."""
    friendly_name: Optional[str] = None
    bio: Optional[str] = None
    profile_ipfs: Optional[str] = None

class AssetFavoriteRequest(BaseModel):
    """Request model for adding a favorite asset."""
    asset_name: str

@router.get("/", response_model=Profile)
async def get_profile(address: str = Security(get_current_user)):
    """Get the authenticated user's profile."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Get profile data
            profile = await conn.fetchrow(
                '''
                SELECT 
                    address,
                    friendly_name,
                    bio,
                    profile_ipfs,
                    status
                FROM user_profiles
                WHERE address = $1
                ''',
                address
            )
            
            if not profile:
                # Return default profile
                return {
                    "address": address,
                    "friendly_name": address[:8],
                    "bio": "",
                    "profile_ipfs": "",
                    "status": "active",
                    "favorite_assets": []
                }
            
            # Get favorite assets
            favorites = await conn.fetch(
                '''
                SELECT asset_name
                FROM user_favorite_assets
                WHERE address = $1
                ORDER BY created_at DESC
                ''',
                address
            )
            
            return {
                **dict(profile),
                "favorite_assets": [f["asset_name"] for f in favorites]
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch("/")
async def update_profile(
    update: ProfileUpdate,
    address: str = Security(get_current_user)
):
    """Update the authenticated user's profile."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Build update query dynamically based on provided fields
            update_fields = []
            params = [address]
            param_idx = 2
            
            if update.friendly_name is not None:
                update_fields.append(f"friendly_name = ${param_idx}")
                params.append(update.friendly_name)
                param_idx += 1
                
            if update.bio is not None:
                update_fields.append(f"bio = ${param_idx}")
                params.append(update.bio)
                param_idx += 1
                
            if update.profile_ipfs is not None:
                update_fields.append(f"profile_ipfs = ${param_idx}")
                params.append(update.profile_ipfs)
                param_idx += 1
            
            if update_fields:
                query = f'''
                    INSERT INTO user_profiles (
                        address, friendly_name, bio, profile_ipfs, status
                    ) VALUES ($1, '', '', '', 'active')
                    ON CONFLICT (address) DO UPDATE
                    SET {", ".join(update_fields)},
                        updated_at = now()
                    WHERE user_profiles.address = $1
                '''
                
                await conn.execute(query, *params)
            
            return {"success": True}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/image")
async def upload_profile_image(
    file: UploadFile = File(...),
    address: str = Security(get_current_user)
):
    """Upload a profile image and return its IPFS hash."""
    try:
        # Validate file type
        content_type = file.content_type
        if not content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        # Create uploads directory if it doesn't exist
        os.makedirs("uploads", exist_ok=True)
        
        # Generate unique filename using address and timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"profile_{address}_{timestamp}"
        
        # Save uploaded file
        file_path = f"uploads/{filename}"
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # TODO: Upload to IPFS and get hash
        # For now, generate a mock IPFS hash
        mock_ipfs_hash = hashlib.sha256(content).hexdigest()
        
        # Update profile with new image hash
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO user_profiles (
                    address, friendly_name, bio, profile_ipfs, status
                ) VALUES ($1, '', '', $2, 'active')
                ON CONFLICT (address) DO UPDATE
                SET profile_ipfs = $2,
                    updated_at = now()
                WHERE user_profiles.address = $1
                ''',
                address,
                mock_ipfs_hash
            )
        
        return {"ipfs_hash": mock_ipfs_hash}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        # Clean up uploaded file
        if 'file_path' in locals():
            try:
                os.remove(file_path)
            except:
                pass

@router.post("/favorites")
async def add_favorite_asset(
    request: AssetFavoriteRequest,
    address: str = Security(get_current_user)
):
    """Add an asset to user's favorites."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO user_favorite_assets (
                    address, asset_name
                ) VALUES ($1, $2)
                ON CONFLICT (address, asset_name) DO NOTHING
                ''',
                address,
                request.asset_name
            )
            
            return {"success": True}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/favorites/{asset_name}")
async def remove_favorite_asset(
    asset_name: str,
    address: str = Security(get_current_user)
):
    """Remove an asset from user's favorites."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                '''
                DELETE FROM user_favorite_assets
                WHERE address = $1 AND asset_name = $2
                ''',
                address,
                asset_name
            )
            
            return {"success": True}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Export the router
__all__ = ['router']