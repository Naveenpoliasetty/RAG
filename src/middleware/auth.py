import os
import httpx
import jwt
from typing import Optional
from pathlib import Path
from fastapi import Request, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from src.utils.logger import get_logger

# Load environment variables from .env file
# Try to find .env in project root
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
elif (project_root / ".env.example").exists():
    load_dotenv(project_root / ".env.example")
else:
    # Fallback: load from current directory
    load_dotenv()

logger = get_logger(__name__)

# Clerk configuration
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY", "")
CLERK_PUBLISHABLE_KEY = os.getenv("CLERK_PUBLISHABLE_KEY", "")

security = HTTPBearer(auto_error=False)  # Don't auto-raise error, handle manually


class ClerkAuthMiddleware:
    """Middleware to authenticate requests using Clerk bearer tokens"""
    
    def __init__(self):
        self.clerk_secret_key = CLERK_SECRET_KEY
        self.clerk_publishable_key = CLERK_PUBLISHABLE_KEY
        
        if not self.clerk_secret_key:
            logger.warning("CLERK_SECRET_KEY not set - authentication will fail")
    
    async def verify_token(self, token: str) -> Optional[dict]:
        """
        Verify Clerk JWT token and return user information.
        
        Clerk tokens are JWTs that contain user information in the claims.
        We decode the token to extract the user ID (sub claim).
        
        Args:
            token: Bearer token string (JWT)
            
        Returns:
            dict with user info including 'id' (clerk_id), or None if invalid
        """
        # Clerk tokens are JWTs - decode them directly
        # This is faster and doesn't require API calls
        jwt_result = self._decode_jwt_token(token)
        if jwt_result:
            logger.debug("Successfully decoded JWT token")
            return jwt_result
        
        # If JWT decode fails, the token might be invalid or malformed
        logger.warning("Failed to decode JWT token - token may be invalid or malformed")
        return None
    
    def _decode_jwt_token(self, token: str) -> Optional[dict]:
        """
        Decode Clerk JWT token to extract user information.
        
        Clerk tokens contain user ID in the 'sub' (subject) claim.
        For production, you should verify the signature using Clerk's public key.
        
        Args:
            token: JWT token string
            
        Returns:
            dict with user info including 'id' (clerk_id), or None if invalid
        """
        try:
            # Decode JWT token (without signature verification for now)
            # In production, verify signature using Clerk's JWKS endpoint
            decoded = jwt.decode(
                token,
                options={"verify_signature": False}  # Skip signature verification for development
            )
            
            # Clerk JWT tokens have user ID in the 'sub' (subject) claim
            # Format: "user_xxxxxxxxxxxxx"
            user_id = decoded.get("sub")
            
            # Fallback to other possible claim names
            if not user_id:
                user_id = decoded.get("userId") or decoded.get("user_id") or decoded.get("id")
            
            if user_id:
                logger.debug(f"Extracted user ID from token: {user_id}")
                return {"id": user_id, "data": decoded}
            
            logger.warning(f"No user ID found in token claims. Available claims: {list(decoded.keys())}")
            return None
            
        except jwt.ExpiredSignatureError:
            logger.error("JWT token has expired")
            return None
        except jwt.DecodeError as e:
            logger.error(f"Failed to decode JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error decoding JWT token: {e}")
            return None
    
    async def get_user_from_db(self, request: Request, clerk_id: str) -> Optional[dict]:
        """
        Fetch user from MongoDB using clerk_id.
        
        Args:
            request: FastAPI request object
            clerk_id: Clerk user ID
            
        Returns:
            User document from MongoDB or None
        """
        try:
            mongodb_manager = request.app.state.mongodb
            users_collection = mongodb_manager.db["users"]
            user = users_collection.find_one({"clerk_id": clerk_id})
            return user
        except Exception as e:
            logger.error(f"Error fetching user from DB: {e}")
            return None


# Global instance
clerk_auth = ClerkAuthMiddleware()


async def get_current_user(request: Request) -> dict:
    """
    Dependency function to get current authenticated user.
    Extracts bearer token from Authorization header, verifies with Clerk, fetches user from DB.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User document from MongoDB
        
    Raises:
        HTTPException: If authentication fails
    """
    # Extract token from Authorization header directly from request
    authorization = request.headers.get("Authorization") or request.headers.get("authorization")
    
    if not authorization:
        logger.warning("Missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Parse Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning("Invalid Authorization header format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = parts[1]
    
    # Verify token with Clerk
    token_data = await clerk_auth.verify_token(token)
    if not token_data:
        logger.warning("Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    clerk_id = token_data["id"]
    
    # Fetch user from MongoDB
    user = await clerk_auth.get_user_from_db(request, clerk_id)
    if not user:
        logger.warning(f"User not found in database: clerk_id={clerk_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please ensure your account is properly set up.",
        )
    
    return user