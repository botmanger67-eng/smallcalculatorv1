"""
API v1 package initialization module.

This module initializes the API v1 package, setting up the Flask Blueprint
for version 1 of the API and registering all route handlers.
"""

from typing import List, Optional
from flask import Blueprint, Flask
from flask_restx import Api

# Import route modules
from src.api.v1.auth import auth_ns
from src.api.v1.users import users_ns
from src.api.v1.products import products_ns
from src.api.v1.orders import orders_ns
from src.api.v1.health import health_ns

# Blueprint configuration
API_V1_BLUEPRINT_NAME: str = "api_v1"
API_V1_BLUEPRINT_IMPORT_NAME: str = __name__
API_V1_URL_PREFIX: str = "/api/v1"
API_V1_TITLE: str = "API v1"
API_V1_VERSION: str = "1.0"
API_V1_DESCRIPTION: str = "Version 1 of the RESTful API"

# Namespace registration order
NAMESPACES: List = [
    health_ns,
    auth_ns,
    users_ns,
    products_ns,
    orders_ns,
]

# Create Flask Blueprint
api_v1_blueprint: Blueprint = Blueprint(
    API_V1_BLUEPRINT_NAME,
    API_V1_BLUEPRINT_IMPORT_NAME,
    url_prefix=API_V1_URL_PREFIX,
)

# Create Flask-RESTx API instance
api_v1: Api = Api(
    app=None,
    version=API_V1_VERSION,
    title=API_V1_TITLE,
    description=API_V1_DESCRIPTION,
    doc="/docs/",
    prefix=API_V1_URL_PREFIX,
    default="Default",
    default_label="Default namespace",
    validate=True,
    ordered=True,
)


def register_namespaces(api: Api, namespaces: List) -> None:
    """
    Register all API namespaces with the Flask-RESTx API instance.

    Args:
        api: Flask-RESTx API instance to register namespaces with
        namespaces: List of namespace objects to register

    Raises:
        ValueError: If api is None or namespaces is empty
        TypeError: If namespaces contains invalid namespace objects
    """
    if api is None:
        raise ValueError("API instance cannot be None")

    if not namespaces:
        raise ValueError("Namespaces list cannot be empty")

    for namespace in namespaces:
        if namespace is None:
            raise TypeError("Namespace cannot be None")

        try:
            api.add_namespace(namespace)
        except Exception as e:
            raise RuntimeError(
                f"Failed to register namespace '{namespace.name}': {str(e)}"
            ) from e


def init_app(app: Flask) -> None:
    """
    Initialize the API v1 with the Flask application.

    This function registers the API blueprint and all namespaces
    with the provided Flask application instance.

    Args:
        app: Flask application instance to initialize with

    Raises:
        ValueError: If app is None
        RuntimeError: If initialization fails
    """
    if app is None:
        raise ValueError("Flask application instance cannot be None")

    try:
        # Initialize API with blueprint
        api_v1.init_app(api_v1_blueprint)

        # Register all namespaces
        register_namespaces(api_v1, NAMESPACES)

        # Register blueprint with Flask application
        app.register_blueprint(api_v1_blueprint)

    except Exception as e:
        raise RuntimeError(
            f"Failed to initialize API v1: {str(e)}"
        ) from e


def get_api() -> Api:
    """
    Get the configured API v1 instance.

    Returns:
        Api: The Flask-RESTx API instance for version 1

    Raises:
        RuntimeError: If API instance is not properly initialized
    """
    if api_v1 is None:
        raise RuntimeError("API v1 instance is not initialized")

    return api_v1


def get_blueprint() -> Blueprint:
    """
    Get the API v1 Blueprint instance.

    Returns:
        Blueprint: The Flask Blueprint for version 1 of the API

    Raises:
        RuntimeError: If Blueprint instance is not properly initialized
    """
    if api_v1_blueprint is None:
        raise RuntimeError("API v1 Blueprint is not initialized")

    return api_v1_blueprint


__all__: List[str] = [
    "api_v1",
    "api_v1_blueprint",
    "init_app",
    "get_api",
    "get_blueprint",
    "register_namespaces",
    "API_V1_URL_PREFIX",
    "API_V1_VERSION",
]