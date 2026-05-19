"""
Models package initialization.

This module provides the base model class and utilities for all data models
used throughout the application. It serves as the central registry for model
definitions and ensures consistent model instantiation and validation.
"""

from __future__ import annotations

import logging
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    final,
)

from pydantic import BaseModel, ValidationError, Field, ConfigDict
from pydantic.alias_generators import to_camel

logger = logging.getLogger(__name__)

# Type variable for model subclasses
T = TypeVar("T", bound="BaseModel")

# Type alias for model registry
ModelRegistry = Dict[str, Type["BaseModel"]]

# Global model registry
_model_registry: ModelRegistry = {}


class ModelError(Exception):
    """Base exception for model-related errors."""

    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        """
        Initialize ModelError.

        Args:
            message: Error description
            original_error: Original exception that caused this error
        """
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class ModelValidationError(ModelError):
    """Exception raised when model validation fails."""

    def __init__(self, message: str, errors: List[Dict[str, Any]]) -> None:
        """
        Initialize ModelValidationError.

        Args:
            message: Error description
            errors: List of validation error details
        """
        self.errors = errors
        super().__init__(message)


class ModelNotFoundError(ModelError):
    """Exception raised when a model type is not found in registry."""

    def __init__(self, model_name: str) -> None:
        """
        Initialize ModelNotFoundError.

        Args:
            model_name: Name of the model that was not found
        """
        self.model_name = model_name
        super().__init__(f"Model '{model_name}' not found in registry")


class ModelInstantiationError(ModelError):
    """Exception raised when model instantiation fails."""

    def __init__(self, model_name: str, message: str, original_error: Optional[Exception] = None) -> None:
        """
        Initialize ModelInstantiationError.

        Args:
            model_name: Name of the model that failed to instantiate
            message: Error description
            original_error: Original exception that caused this error
        """
        self.model_name = model_name
        super().__init__(f"Failed to instantiate model '{model_name}': {message}", original_error)


class BaseModel(BaseModel):
    """
    Base model class for all application models.

    Provides common functionality including:
    - CamelCase field serialization
    - Model registration
    - Consistent validation
    - Error handling utilities

    Attributes:
        model_config: Pydantic model configuration
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=False,
        str_strip_whitespace=True,
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        Automatically register model subclasses.

        Args:
            **kwargs: Additional keyword arguments for subclass creation
        """
        super().__init_subclass__(**kwargs)
        if cls.__name__ != "BaseModel":
            cls.register_model()

    @classmethod
    def register_model(cls) -> None:
        """
        Register the model class in the global registry.

        Raises:
            ModelError: If registration fails
        """
        try:
            model_name = cls.__name__
            if model_name in _model_registry:
                logger.warning(f"Model '{model_name}' already registered. Overwriting.")
            _model_registry[model_name] = cls
            logger.debug(f"Registered model: {model_name}")
        except Exception as e:
            raise ModelError(f"Failed to register model '{cls.__name__}': {str(e)}", e)

    @classmethod
    def get_registered_model(cls, model_name: str) -> Type["BaseModel"]:
        """
        Get a registered model class by name.

        Args:
            model_name: Name of the model to retrieve

        Returns:
            The registered model class

        Raises:
            ModelNotFoundError: If model is not registered
        """
        if model_name not in _model_registry:
            raise ModelNotFoundError(model_name)
        return _model_registry[model_name]

    @classmethod
    def create_instance(cls: Type[T], **data: Any) -> T:
        """
        Create a model instance with validation.

        Args:
            **data: Model field data

        Returns:
            Validated model instance

        Raises:
            ModelValidationError: If validation fails
            ModelInstantiationError: If instantiation fails
        """
        try:
            instance = cls(**data)
            return instance
        except ValidationError as e:
            errors = [
                {
                    "field": err.get("loc", []),
                    "message": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
                for err in e.errors()
            ]
            raise ModelValidationError(
                f"Validation failed for model '{cls.__name__}'",
                errors,
            ) from e
        except Exception as e:
            raise ModelInstantiationError(
                cls.__name__,
                str(e),
                e,
            )

    @classmethod
    def create_instance_safe(cls: Type[T], **data: Any) -> Optional[T]:
        """
        Safely create a model instance, returning None on failure.

        Args:
            **data: Model field data

        Returns:
            Validated model instance or None if creation fails
        """
        try:
            return cls.create_instance(**data)
        except (ModelValidationError, ModelInstantiationError) as e:
            logger.error(f"Failed to create instance of '{cls.__name__}': {e}")
            return None

    def to_dict(self, by_alias: bool = True, exclude_none: bool = True) -> Dict[str, Any]:
        """
        Convert model to dictionary.

        Args:
            by_alias: Whether to use field aliases
            exclude_none: Whether to exclude None values

        Returns:
            Dictionary representation of the model
        """
        return self.model_dump(by_alias=by_alias, exclude_none=exclude_none)

    def to_json(self, by_alias: bool = True, exclude_none: bool = True) -> str:
        """
        Convert model to JSON string.

        Args:
            by_alias: Whether to use field aliases
            exclude_none: Whether to exclude None values

        Returns:
            JSON string representation of the model
        """
        return self.model_dump_json(by_alias=by_alias, exclude_none=exclude_none)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
        Create model instance from dictionary.

        Args:
            data: Dictionary containing model data

        Returns:
            Validated model instance

        Raises:
            ModelValidationError: If validation fails
        """
        return cls.create_instance(**data)

    def update(self, **data: Any) -> None:
        """
        Update model fields with validation.

        Args:
            **data: Field data to update

        Raises:
            ModelValidationError: If validation fails
        """
        try:
            for field, value in data.items():
                setattr(self, field, value)
        except ValidationError as e:
            errors = [
                {
                    "field": err.get("loc", []),
                    "message": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
                for err in e.errors()
            ]
            raise ModelValidationError(
                f"Validation failed during update for model '{self.__class__.__name__}'",
                errors,
            ) from e


def get_registered_models() -> ModelRegistry:
    """
    Get all registered models.

    Returns:
        Dictionary of registered model names to model classes
    """
    return dict(_model_registry)


def clear_model_registry() -> None:
    """Clear all registered models from the registry."""
    _model_registry.clear()
    logger.debug("Model registry cleared")


def get_model_count() -> int:
    """
    Get the number of registered models.

    Returns:
        Count of registered models
    """
    return len(_model_registry)


__all__ = [
    "BaseModel",
    "ModelError",
    "ModelValidationError",
    "ModelNotFoundError",
    "ModelInstantiationError",
    "get_registered_models",
    "clear_model_registry",
    "get_model_count",
]