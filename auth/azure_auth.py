"""
Azure AD OAuth2/JWT Authentication for FastAPI

This module handles:
1. JWT token validation from Azure AD
2. User extraction from tokens
3. FastAPI dependency injection for protected endpoints
"""
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError, jwk
from jose.exceptions import ExpiredSignatureError

from config.settings import settings

logger = logging.getLogger(__name__)

# OAuth2 scheme - extracts Bearer token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"https://login.microsoftonline.com/{settings.AZURE_AD_TENANT_ID}/oauth2/v2.0/token",
    auto_error=False  # Don't auto-raise on missing token (we handle it)
)


@dataclass
class AuthUser:
    """Authenticated user information extracted from JWT"""
    sub: str              # Subject (user ID)
    name: str             # Display name
    email: Optional[str]  # Email (may not always be present)
    roles: list[str]      # Roles assigned to user
    tenant_id: str        # Azure AD tenant ID
    raw_claims: Dict[str, Any]  # All claims from token


class JWKSCache:
    """Caches Azure AD public keys for JWT validation"""

    def __init__(self):
        self._keys: Dict[str, Any] = {}
        self._loaded = False

    async def get_key(self, kid: str) -> Optional[Dict[str, Any]]:
        """Get public key by key ID"""
        if not self._loaded:
            await self._load_keys()
        return self._keys.get(kid)

    async def _load_keys(self):
        """Load JWKS from Azure AD"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(settings.azure_ad_jwks_url)
                response.raise_for_status()
                jwks = response.json()

                for key_data in jwks.get("keys", []):
                    kid = key_data.get("kid")
                    if kid:
                        self._keys[kid] = key_data

                self._loaded = True
                logger.info(f"Loaded {len(self._keys)} public keys from Azure AD")
        except Exception as e:
            logger.error(f"Failed to load JWKS from Azure AD: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable"
            )

    def clear(self):
        """Clear cache to force reload"""
        self._keys = {}
        self._loaded = False


# Global JWKS cache
_jwks_cache = JWKSCache()


async def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token from Azure AD

    Args:
        token: The JWT token string

    Returns:
        Decoded token claims

    Raises:
        HTTPException: If token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            logger.warning("Token missing key ID (kid)")
            raise credentials_exception

        # Get public key from JWKS
        key_data = await _jwks_cache.get_key(kid)
        if not key_data:
            # Try refreshing cache once
            _jwks_cache.clear()
            key_data = await _jwks_cache.get_key(kid)

        if not key_data:
            logger.warning(f"Unknown key ID: {kid}")
            raise credentials_exception

        # Build the public key
        public_key = jwk.construct(key_data)

        # Verify and decode the token
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.AZURE_AD_AUDIENCE or settings.AZURE_AD_CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{settings.AZURE_AD_TENANT_ID}/v2.0"
        )

        return claims

    except ExpiredSignatureError:
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        logger.warning(f"JWT validation error: {e}")
        raise credentials_exception


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[AuthUser]:
    """
    FastAPI dependency to get current authenticated user

    If AUTH_ENABLED is False, returns None (allows unauthenticated access)
    If AUTH_ENABLED is True, validates token and returns user

    Args:
        token: Bearer token from Authorization header

    Returns:
        AuthUser if authenticated, None if auth disabled

    Raises:
        HTTPException: If auth enabled but token invalid/missing
    """
    # If auth is disabled, allow all requests
    if not settings.AUTH_ENABLED:
        return None

    # Auth is enabled - token is required
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token and extract claims
    claims = await verify_token(token)

    # Build user object from claims
    return AuthUser(
        sub=claims.get("sub", ""),
        name=claims.get("name", claims.get("preferred_username", "Unknown")),
        email=claims.get("email") or claims.get("preferred_username"),
        roles=claims.get("roles", []),
        tenant_id=claims.get("tid", ""),
        raw_claims=claims
    )


def require_auth(user: Optional[AuthUser] = Depends(get_current_user)) -> AuthUser:
    """
    FastAPI dependency that REQUIRES authentication

    Use this for endpoints that must always be protected,
    regardless of AUTH_ENABLED setting

    Args:
        user: Current user from get_current_user

    Returns:
        AuthUser (never None)

    Raises:
        HTTPException: If not authenticated
    """
    if user is None and settings.AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # If auth disabled, return a mock user for logging purposes
    if user is None:
        return AuthUser(
            sub="anonymous",
            name="Anonymous User",
            email=None,
            roles=["user"],
            tenant_id="",
            raw_claims={}
        )

    return user


def has_role(required_role: str):
    """
    Create a dependency that checks for a specific role

    Usage:
        @app.get("/admin", dependencies=[Depends(has_role("admin"))])
        def admin_endpoint():
            ...
    """
    async def role_checker(user: AuthUser = Depends(require_auth)):
        if required_role not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        return user
    return role_checker


# MSAL client for server-side token acquisition (optional)
_msal_app = None

def get_msal_app():
    """Get MSAL confidential client application"""
    global _msal_app
    if _msal_app is None:
        try:
            from msal import ConfidentialClientApplication
            _msal_app = ConfidentialClientApplication(
                client_id=settings.AZURE_AD_CLIENT_ID,
                client_credential=settings.AZURE_AD_CLIENT_SECRET,
                authority=settings.azure_ad_authority
            )
        except Exception as e:
            logger.error(f"Failed to create MSAL app: {e}")
            return None
    return _msal_app


async def get_access_token_for_client() -> Optional[str]:
    """
    Get access token using client credentials flow

    Useful for server-to-server authentication
    """
    app = get_msal_app()
    if not app:
        return None

    try:
        result = app.acquire_token_for_client(
            scopes=[f"{settings.AZURE_AD_AUDIENCE}/.default"]
        )
        return result.get("access_token")
    except Exception as e:
        logger.error(f"Failed to acquire token: {e}")
        return None
