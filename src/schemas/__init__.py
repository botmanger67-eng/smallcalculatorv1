"""
Schemas package initialization.

This module provides centralized access to all schema definitions used
for data validation, serialization, and API request/response handling.
"""

from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel, ValidationError

# Import all schema classes
from src.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    UserPasswordChange,
    UserProfile,
)
from src.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationMember,
    OrganizationSettings,
)
from src.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectMember,
    ProjectSettings,
)
from src.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskAssignment,
    TaskStatus,
    TaskPriority,
)
from src.schemas.common import (
    PaginatedResponse,
    ErrorResponse,
    SuccessResponse,
    ValidationErrorResponse,
    Metadata,
    SortOrder,
    FilterCriteria,
)

# Define public API
__all__: List[str] = [
    # User schemas
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "UserPasswordChange",
    "UserProfile",
    # Organization schemas
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationResponse",
    "OrganizationMember",
    "OrganizationSettings",
    # Project schemas
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "ProjectMember",
    "ProjectSettings",
    # Task schemas
    "TaskCreate",
    "TaskUpdate",
    "TaskResponse",
    "TaskAssignment",
    "TaskStatus",
    "TaskPriority",
    # Common schemas
    "PaginatedResponse",
    "ErrorResponse",
    "SuccessResponse",
    "ValidationErrorResponse",
    "Metadata",
    "SortOrder",
    "FilterCriteria",
    # Utility functions
    "validate_schema",
    "validate_list_schema",
    "get_schema_fields",
    "schema_to_dict",
]

# Schema registry for dynamic access
_schema_registry: Dict[str, Type[BaseModel]] = {
    "UserCreate": UserCreate,
    "UserUpdate": UserUpdate,
    "UserResponse": UserResponse,
    "UserLogin": UserLogin,
    "UserPasswordChange": UserPasswordChange,
    "UserProfile": UserProfile,
    "OrganizationCreate": OrganizationCreate,
    "OrganizationUpdate": OrganizationUpdate,
    "OrganizationResponse": OrganizationResponse,
    "OrganizationMember": OrganizationMember,
    "OrganizationSettings": OrganizationSettings,
    "ProjectCreate": ProjectCreate,
    "ProjectUpdate": ProjectUpdate,
    "ProjectResponse": ProjectResponse,
    "ProjectMember": ProjectMember,
    "ProjectSettings": ProjectSettings,
    "TaskCreate": TaskCreate,
    "TaskUpdate": TaskUpdate,
    "TaskResponse": TaskResponse,
    "TaskAssignment": TaskAssignment,
    "TaskStatus": TaskStatus,
    "TaskPriority": TaskPriority,
    "PaginatedResponse": PaginatedResponse,
    "ErrorResponse": ErrorResponse,
    "SuccessResponse": SuccessResponse,
    "ValidationErrorResponse": ValidationErrorResponse,
    "Metadata": Metadata,
    "SortOrder": SortOrder,
    "FilterCriteria": FilterCriteria,
}


def validate_schema(
    schema_class: Type[BaseModel],
    data: Union[Dict[str, Any], BaseModel],
    strict: bool = False,
) -> BaseModel:
    """
    Validate data against a Pydantic schema.

    Args:
        schema_class: The Pydantic model class to validate against.
        data: The data to validate (dictionary or model instance).
        strict: If True, raise on validation errors. If False, return partial data.

    Returns:
        Validated model instance.

    Raises:
        ValidationError: If validation fails and strict mode is enabled.
        TypeError: If schema_class is not a Pydantic model.
    """
    if not issubclass(schema_class, BaseModel):
        raise TypeError(f"Expected Pydantic BaseModel subclass, got {type(schema_class)}")

    try:
        if isinstance(data, BaseModel):
            return schema_class.model_validate(data.model_dump())
        return schema_class.model_validate(data)
    except ValidationError as e:
        if strict:
            raise
        # Return partial data with only valid fields
        valid_data: Dict[str, Any] = {}
        for field_name, field_info in schema_class.model_fields.items():
            if field_name in data:
                try:
                    valid_data[field_name] = field_info.validate(data[field_name])
                except (ValidationError, ValueError, TypeError):
                    continue
        return schema_class(**valid_data)


def validate_list_schema(
    schema_class: Type[BaseModel],
    data_list: List[Union[Dict[str, Any], BaseModel]],
    strict: bool = False,
) -> List[BaseModel]:
    """
    Validate a list of items against a Pydantic schema.

    Args:
        schema_class: The Pydantic model class to validate against.
        data_list: List of data items to validate.
        strict: If True, raise on validation errors. If False, skip invalid items.

    Returns:
        List of validated model instances.

    Raises:
        ValidationError: If validation fails and strict mode is enabled.
        TypeError: If schema_class is not a Pydantic model.
    """
    if not issubclass(schema_class, BaseModel):
        raise TypeError(f"Expected Pydantic BaseModel subclass, got {type(schema_class)}")

    validated_items: List[BaseModel] = []
    for item in data_list:
        try:
            validated_items.append(validate_schema(schema_class, item, strict=strict))
        except ValidationError:
            if strict:
                raise
            continue
    return validated_items


def get_schema_fields(schema_class: Type[BaseModel]) -> Dict[str, Any]:
    """
    Get the field definitions of a Pydantic schema.

    Args:
        schema_class: The Pydantic model class to inspect.

    Returns:
        Dictionary mapping field names to their type annotations.

    Raises:
        TypeError: If schema_class is not a Pydantic model.
    """
    if not issubclass(schema_class, BaseModel):
        raise TypeError(f"Expected Pydantic BaseModel subclass, got {type(schema_class)}")

    fields: Dict[str, Any] = {}
    for field_name, field_info in schema_class.model_fields.items():
        fields[field_name] = {
            "type": field_info.annotation,
            "required": field_info.is_required(),
            "default": field_info.default,
            "description": field_info.description,
        }
    return fields


def schema_to_dict(
    schema_instance: BaseModel,
    exclude_none: bool = False,
    exclude_unset: bool = False,
) -> Dict[str, Any]:
    """
    Convert a Pydantic schema instance to a dictionary.

    Args:
        schema_instance: The Pydantic model instance to convert.
        exclude_none: If True, exclude fields with None values.
        exclude_unset: If True, exclude fields that were not explicitly set.

    Returns:
        Dictionary representation of the schema.

    Raises:
        TypeError: If schema_instance is not a Pydantic model instance.
    """
    if not isinstance(schema_instance, BaseModel):
        raise TypeError(f"Expected Pydantic BaseModel instance, got {type(schema_instance)}")

    return schema_instance.model_dump(
        exclude_none=exclude_none,
        exclude_unset=exclude_unset,
    )


def get_schema_by_name(name: str) -> Optional[Type[BaseModel]]:
    """
    Retrieve a schema class by its name from the registry.

    Args:
        name: The name of the schema class to retrieve.

    Returns:
        The schema class if found, None otherwise.
    """
    return _schema_registry.get(name)


def list_available_schemas() -> List[str]:
    """
    Get a list of all registered schema names.

    Returns:
        Sorted list of schema class names.
    """
    return sorted(_schema_registry.keys())


# Version information
__version__: str = "1.0.0"
__schema_version__: str = "1.0.0"

# Initialize schema registry on import
def _initialize_registry() -> None:
    """Validate that all registered schemas are valid Pydantic models."""
    invalid_schemas: List[str] = []
    for name, schema_class in _schema_registry.items():
        if not issubclass(schema_class, BaseModel):
            invalid_schemas.append(name)
    if invalid_schemas:
        raise RuntimeError(
            f"Invalid schema classes registered: {', '.join(invalid_schemas)}"
        )


_initialize_registry()