"""
API v1 endpoints package initialization.

This module provides the initialization and configuration for all API v1 endpoints,
including health checks, user management, and other resource endpoints.
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import logging
from datetime import datetime, timezone

# Configure module logger
logger = logging.getLogger(__name__)

# Create main API router for v1 endpoints
api_router = APIRouter(prefix="/api/v1", tags=["v1"])

# Health check response model
class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current UTC timestamp")
    uptime: Optional[float] = Field(None, description="Service uptime in seconds")
    database_status: Optional[str] = Field(None, description="Database connection status")
    cache_status: Optional[str] = Field(None, description="Cache service status")

# Service metadata
SERVICE_VERSION: str = "1.0.0"
SERVICE_START_TIME: datetime = datetime.now(timezone.utc)

# Endpoint registry
ENDPOINT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "health": {
        "path": "/health",
        "methods": ["GET"],
        "description": "Health check endpoint",
        "tags": ["system"]
    },
    "users": {
        "path": "/users",
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "description": "User management endpoints",
        "tags": ["users"]
    },
    "items": {
        "path": "/items",
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "description": "Item management endpoints",
        "tags": ["items"]
    }
}

def get_service_uptime() -> float:
    """
    Calculate service uptime in seconds.
    
    Returns:
        float: Number of seconds since service started
    """
    try:
        current_time: datetime = datetime.now(timezone.utc)
        uptime_delta = current_time - SERVICE_START_TIME
        return uptime_delta.total_seconds()
    except Exception as e:
        logger.error(f"Failed to calculate uptime: {str(e)}")
        return 0.0

def get_health_status() -> Dict[str, Any]:
    """
    Get current health status of the service.
    
    Returns:
        Dict[str, Any]: Health status information including version, uptime, and component status
    """
    try:
        health_data: Dict[str, Any] = {
            "status": "healthy",
            "version": SERVICE_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime": get_service_uptime(),
            "database_status": "connected",
            "cache_status": "connected"
        }
        return health_data
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "version": SERVICE_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }

def register_endpoints(app: FastAPI) -> None:
    """
    Register all API v1 endpoints with the FastAPI application.
    
    Args:
        app: FastAPI application instance
        
    Raises:
        ValueError: If app is None or invalid
        RuntimeError: If endpoint registration fails
    """
    if app is None:
        raise ValueError("Application instance cannot be None")
    
    try:
        # Register health check endpoint
        @api_router.get(
            "/health",
            response_model=HealthCheckResponse,
            summary="Health Check",
            description="Check the health status of the API service",
            response_description="Health status information"
        )
        async def health_check() -> HealthCheckResponse:
            """
            Perform health check on the service.
            
            Returns:
                HealthCheckResponse: Health status information
            """
            try:
                health_data: Dict[str, Any] = get_health_status()
                return HealthCheckResponse(**health_data)
            except Exception as e:
                logger.error(f"Health check endpoint error: {str(e)}")
                return HealthCheckResponse(
                    status="error",
                    version=SERVICE_VERSION,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    database_status="disconnected",
                    cache_status="disconnected"
                )

        # Register error handler for 404
        @api_router.get("/{path:path}", include_in_schema=False)
        async def catch_all(path: str) -> JSONResponse:
            """
            Catch-all handler for undefined routes.
            
            Args:
                path: The requested path
                
            Returns:
                JSONResponse: 404 error response
            """
            logger.warning(f"Undefined route accessed: /api/v1/{path}")
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Not Found",
                    "message": f"Endpoint /api/v1/{path} not found",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )

        # Include the router in the application
        app.include_router(api_router)
        logger.info("API v1 endpoints registered successfully")
        
    except Exception as e:
        error_msg: str = f"Failed to register endpoints: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

def get_endpoint_info() -> List[Dict[str, Any]]:
    """
    Get information about all registered endpoints.
    
    Returns:
        List[Dict[str, Any]]: List of endpoint information dictionaries
    """
    try:
        endpoint_info: List[Dict[str, Any]] = []
        for name, config in ENDPOINT_REGISTRY.items():
            endpoint_info.append({
                "name": name,
                "path": config["path"],
                "methods": config["methods"],
                "description": config["description"],
                "tags": config["tags"]
            })
        return endpoint_info
    except Exception as e:
        logger.error(f"Failed to get endpoint info: {str(e)}")
        return []

def validate_endpoint_config() -> bool:
    """
    Validate the endpoint configuration.
    
    Returns:
        bool: True if configuration is valid, False otherwise
    """
    try:
        for name, config in ENDPOINT_REGISTRY.items():
            if not isinstance(name, str) or not name:
                logger.error(f"Invalid endpoint name: {name}")
                return False
            if "path" not in config or not config["path"]:
                logger.error(f"Missing path for endpoint: {name}")
                return False
            if "methods" not in config or not config["methods"]:
                logger.error(f"Missing methods for endpoint: {name}")
                return False
            if not isinstance(config["methods"], list):
                logger.error(f"Invalid methods type for endpoint: {name}")
                return False
        return True
    except Exception as e:
        logger.error(f"Endpoint configuration validation failed: {str(e)}")
        return False

# Validate configuration on module load
if not validate_endpoint_config():
    logger.warning("Endpoint configuration validation failed")

__all__: List[str] = [
    "api_router",
    "register_endpoints",
    "get_health_status",
    "get_endpoint_info",
    "HealthCheckResponse",
    "SERVICE_VERSION",
    "ENDPOINT_REGISTRY"
]