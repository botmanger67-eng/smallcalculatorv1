"""
Calculation Pydantic schemas for the application.

This module defines Pydantic models for calculation-related data structures,
including request/response schemas and database models.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.config import ConfigDict


class CalculationType(str, Enum):
    """Enumeration of supported calculation types."""
    
    ARITHMETIC = "arithmetic"
    STATISTICAL = "statistical"
    FINANCIAL = "financial"
    SCIENTIFIC = "scientific"
    CUSTOM = "custom"


class CalculationStatus(str, Enum):
    """Enumeration of calculation statuses."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CalculationBase(BaseModel):
    """Base schema for calculation data."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the calculation",
        examples=["Monthly Revenue Calculation", "Statistical Analysis"]
    )
    calculation_type: CalculationType = Field(
        ...,
        description="Type of calculation to perform",
        examples=[CalculationType.FINANCIAL]
    )
    parameters: Dict[str, Any] = Field(
        ...,
        description="Parameters for the calculation",
        examples=[{"base_amount": 1000, "interest_rate": 0.05, "periods": 12}]
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional description of the calculation"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorizing calculations",
        examples=[["finance", "monthly", "revenue"]]
    )

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that parameters dictionary is not empty."""
        if not value:
            raise ValueError("Parameters dictionary cannot be empty")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: List[str]) -> List[str]:
        """Validate and sanitize tags."""
        validated_tags = []
        for tag in value:
            sanitized_tag = tag.strip().lower()
            if not sanitized_tag:
                continue
            if len(sanitized_tag) > 50:
                raise ValueError(f"Tag '{tag}' exceeds maximum length of 50 characters")
            validated_tags.append(sanitized_tag)
        return validated_tags


class CalculationCreate(CalculationBase):
    """Schema for creating a new calculation."""
    
    user_id: str = Field(
        ...,
        description="ID of the user creating the calculation",
        examples=["usr_12345abcde"]
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Priority level for the calculation (0-100)",
        examples=[50]
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Scheduled time for the calculation execution"
    )

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        """Validate user ID format."""
        if not value.startswith("usr_"):
            raise ValueError("User ID must start with 'usr_'")
        if len(value) < 10:
            raise ValueError("User ID is too short")
        return value


class CalculationUpdate(BaseModel):
    """Schema for updating an existing calculation."""
    
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Updated name of the calculation"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated parameters for the calculation"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Updated description"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Updated tags"
    )
    priority: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Updated priority level"
    )
    status: Optional[CalculationStatus] = Field(
        None,
        description="Updated calculation status"
    )

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "CalculationUpdate":
        """Ensure at least one field is provided for update."""
        update_fields = {
            "name": self.name,
            "parameters": self.parameters,
            "description": self.description,
            "tags": self.tags,
            "priority": self.priority,
            "status": self.status
        }
        provided_fields = {k: v for k, v in update_fields.items() if v is not None}
        if not provided_fields:
            raise ValueError("At least one field must be provided for update")
        return self


class CalculationResult(BaseModel):
    """Schema for calculation results."""
    
    value: Union[Decimal, float, int, str, List[Any], Dict[str, Any]] = Field(
        ...,
        description="The calculated result value",
        examples=[1234.56, "success", [1, 2, 3]]
    )
    precision: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Number of decimal places for numeric results"
    )
    unit: Optional[str] = Field(
        None,
        max_length=50,
        description="Unit of measurement for the result",
        examples=["USD", "percentage", "count"]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata about the result"
    )

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: Any) -> Any:
        """Validate that the result value is not None."""
        if value is None:
            raise ValueError("Result value cannot be None")
        return value


class CalculationInDB(CalculationBase):
    """Schema for calculation as stored in database."""
    
    id: str = Field(
        ...,
        description="Unique identifier for the calculation",
        examples=["calc_12345abcde"]
    )
    user_id: str = Field(
        ...,
        description="ID of the user who owns this calculation"
    )
    status: CalculationStatus = Field(
        default=CalculationStatus.PENDING,
        description="Current status of the calculation"
    )
    result: Optional[CalculationResult] = Field(
        None,
        description="Calculation result if completed"
    )
    error_message: Optional[str] = Field(
        None,
        max_length=2000,
        description="Error message if calculation failed"
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Priority level of the calculation"
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Progress percentage of the calculation"
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the calculation was created"
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the calculation was last updated"
    )
    started_at: Optional[datetime] = Field(
        None,
        description="Timestamp when the calculation started processing"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Timestamp when the calculation completed"
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Scheduled execution time"
    )
    execution_time_ms: Optional[int] = Field(
        None,
        ge=0,
        description="Execution time in milliseconds"
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Version number for optimistic locking"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "calc_12345abcde",
                "user_id": "usr_67890fghij",
                "name": "Monthly Revenue Calculation",
                "calculation_type": "financial",
                "parameters": {
                    "base_amount": 1000,
                    "interest_rate": 0.05,
                    "periods": 12
                },
                "description": "Calculate monthly revenue with compound interest",
                "tags": ["finance", "monthly", "revenue"],
                "status": "completed",
                "result": {
                    "value": 1795.85,
                    "precision": 2,
                    "unit": "USD"
                },
                "error_message": None,
                "priority": 50,
                "progress": 100.0,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:05Z",
                "started_at": "2024-01-15T10:30:01Z",
                "completed_at": "2024-01-15T10:30:05Z",
                "scheduled_at": None,
                "execution_time_ms": 4000,
                "version": 1
            }
        }
    )


class CalculationResponse(CalculationInDB):
    """Schema for calculation API responses."""
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "calc_12345abcde",
                "user_id": "usr_67890fghij",
                "name": "Monthly Revenue Calculation",
                "calculation_type": "financial",
                "parameters": {
                    "base_amount": 1000,
                    "interest_rate": 0.05,
                    "periods": 12
                },
                "description": "Calculate monthly revenue with compound interest",
                "tags": ["finance", "monthly", "revenue"],
                "status": "completed",
                "result": {
                    "value": 1795.85,
                    "precision": 2,
                    "unit": "USD"
                },
                "error_message": None,
                "priority": 50,
                "progress": 100.0,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:05Z",
                "started_at": "2024-01-15T10:30:01Z",
                "completed_at": "2024-01-15T10:30:05Z",
                "scheduled_at": None,
                "execution_time_ms": 4000,
                "version": 1
            }
        }
    )


class CalculationList(BaseModel):
    """Schema for paginated calculation list responses."""
    
    items: List[CalculationResponse] = Field(
        ...,
        description="List of calculations"
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of calculations matching the query"
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number"
    )
    page_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page"
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages"
    )

    @model_validator(mode="after")
    def validate_pagination(self) -> "CalculationList":
        """Validate pagination consistency."""
        if self.total_pages != max(1, (self.total + self.page_size - 1) // self.page_size):
            raise ValueError("Total pages does not match calculated value")
        if self.page > self.total_pages and self.total > 0:
            raise ValueError("Page number exceeds total pages")
        return self


class CalculationError(BaseModel):
    """Schema for calculation error responses."""
    
    error_code: str = Field(
        ...,
        description="Error code identifier",
        examples=["CALCULATION_FAILED", "INVALID_PARAMETERS"]
    )
    error_message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Division by zero in calculation"]
    )
    error_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the error occurred"
    )
    calculation_id: Optional[str] = Field(
        None,
        description="ID of the calculation that caused the error"
    )


class CalculationBatchCreate(BaseModel):
    """Schema for batch creation of calculations."""
    
    calculations: List[CalculationCreate] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of calculations to create"
    )
    batch_id: Optional[str] = Field(
        None,
        description="Optional batch identifier for grouping"
    )

    @field_validator("calculations")
    @classmethod
    def validate_calculations(cls, value: List[CalculationCreate]) -> List[CalculationCreate]:
        """Validate batch calculation list."""
        if len(value) > 100:
            raise ValueError("Batch size cannot exceed 100 calculations")
        return value


class CalculationBatchResponse(BaseModel):
    """Schema for batch calculation operation responses."""
    
    batch_id: str = Field(
        ...,
        description="Unique batch identifier"
    )
    total_calculations: int = Field(
        ...,
        ge=0,
        description="Total number of calculations in the batch"
    )
    successful_calculations: int = Field(
        ...,
        ge=0,
        description="Number of successfully created calculations"
    )
    failed_calculations: int = Field(
        ...,
        ge=0,
        description="Number of failed calculations"
    )
    calculation_ids: List[str] = Field(
        default_factory=list,
        description="List of created calculation IDs"
    )
    errors: List[CalculationError] = Field(
        default_factory=list,
        description="List of errors for failed calculations"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the batch was processed"
    )

    @model_validator(mode="after")
    def validate_counts(self) -> "CalculationBatchResponse":
        """Validate that counts are consistent."""
        total = self.successful_calculations + self.failed_calculations
        if total != self.total_calculations:
            raise ValueError(
                f"Total calculations ({self.total_calculations}) does not match "
                f"sum of successful ({self.successful_calculations}) and "
                f"failed ({self.failed_calculations})"
            )
        if len(self.calculation_ids) != self.successful_calculations:
            raise ValueError(
                f"Number of calculation IDs ({len(self.calculation_ids)}) "
                f"does not match successful calculations ({self.successful_calculations})"
            )
        if len(self.errors) != self.failed_calculations:
            raise ValueError(
                f"Number of errors ({len(self.errors)}) "
                f"does not match failed calculations ({self.failed_calculations})"
            )
        return self