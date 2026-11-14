"""
API Dependencies

Dependency injection functions for FastAPI routes.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.models.integration_client import IntegrationClient
from backend.core.security import hash_api_key
from backend.core.logging import get_logger

logger = get_logger(__name__)

LAST_USED_WRITE_INTERVAL = timedelta(seconds=60)


def get_current_client(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[IntegrationClient]:
    """
    Get current authenticated integration client.
    
    Optional authentication - returns None if no credentials provided.
    Use require_authentication for endpoints that must be authenticated.
    """
    if not authorization:
        return None
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )
    
    api_key = authorization[len("Bearer "):].strip()
    
    # hashed_api_key is unique and indexed: one lookup, no scan over all clients.
    client = db.query(IntegrationClient).filter(
        IntegrationClient.hashed_api_key == hash_api_key(api_key),
        IntegrationClient.active == True,
    ).first()
    
    if client is not None:
        now = datetime.utcnow()
        # Throttle the write: at most one last_used_at update per minute per client.
        if client.last_used_at is None or now - client.last_used_at > LAST_USED_WRITE_INTERVAL:
            client.last_used_at = now
            db.commit()
        return client
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


async def require_authentication(
    client: Optional[IntegrationClient] = Depends(get_current_client),
) -> IntegrationClient:
    """
    Require authentication for endpoint.
    
    Raises 401 if client not authenticated.
    """
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    
    return client


def require_scope(required_scope: str):
    """
    Require specific scope for endpoint.
    
    Returns a dependency function that checks for the required scope.
    """
    async def check_scope(
        client: IntegrationClient = Depends(require_authentication),
    ) -> IntegrationClient:
        if required_scope not in client.scopes:
            logger.warning(
                f"Insufficient scope for client {client.client_name}",
                required=required_scope,
                has=client.scopes,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required scope: {required_scope}",
            )
        
        return client
    
    return check_scope


def check_hospital_access(
    client: IntegrationClient,
    hospital_reference: Optional[str],
) -> bool:
    """
    Check if client has access to specific hospital.
    
    Args:
        client: Authenticated client
        hospital_reference: Hospital reference to check
    
    Returns:
        True if access allowed
    """
    # If no hospital restriction, allow all
    if not client.allowed_hospitals or len(client.allowed_hospitals) == 0:
        return True
    
    # If no hospital reference provided, allow (for general queries)
    if not hospital_reference:
        return True
    
    # Check if hospital is in allowed list
    return hospital_reference in client.allowed_hospitals


def check_analysis_access(
    db: Session,
    client: IntegrationClient,
    analysis_id: str,
) -> bool:
    """
    Check if client has access to specific analysis.
    
    Args:
        db: Database session
        client: Authenticated client
        analysis_id: Analysis ID to check
    
    Returns:
        True if access allowed
    """
    from backend.models.analysis import MedicalAnalysis
    from uuid import UUID
    
    try:
        analysis_uuid = UUID(analysis_id)
    except ValueError:
        return False
    
    analysis = db.query(MedicalAnalysis).filter(
        MedicalAnalysis.id == analysis_uuid
    ).first()
    
    if not analysis:
        return False
    
    # Check if analysis was created by this client
    if analysis.requesting_client_id == client.id:
        return True
    
    # Check hospital-level access
    if analysis.external_hospital_reference:
        return check_hospital_access(client, analysis.external_hospital_reference)
    
    # Default deny
    return False
