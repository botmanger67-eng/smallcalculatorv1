"""Calculation SQLAlchemy model for storing calculation history."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.declarative import declarative_base
import enum

from src.config.database import Base


class CalculationStatus(enum.Enum):
    """Enumeration of possible calculation statuses."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Calculation(Base):
    """Represents a mathematical calculation with its result and metadata.

    This model stores the complete history of calculations performed by the system,
    including input parameters, results, timestamps, and status tracking.

    Attributes:
        id: Primary key identifier for the calculation.
        user_id: Foreign key referencing the user who performed the calculation.
        operation: The mathematical operation performed (e.g., 'add', 'subtract').
        operand_a: First operand in the calculation.
        operand_b: Second operand in the calculation.
        result: The computed result of the calculation.
        status: Current status of the calculation (pending, completed, failed, cancelled).
        error_message: Error details if the calculation failed.
        created_at: Timestamp when the calculation was created.
        completed_at: Timestamp when the calculation was completed or failed.
        duration_ms: Duration of the calculation in milliseconds.
    """

    __tablename__ = "calculations"

    id: int = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    operation: str = Column(String(50), nullable=False)
    operand_a: Decimal = Column(Numeric(20, 10), nullable=False)
    operand_b: Decimal = Column(Numeric(20, 10), nullable=False)
    result: Optional[Decimal] = Column(Numeric(20, 10), nullable=True)
    status: CalculationStatus = Column(
        SAEnum(CalculationStatus, name="calculation_status", create_constraint=True),
        nullable=False,
        default=CalculationStatus.PENDING,
        index=True
    )
    error_message: Optional[str] = Column(String(500), nullable=True)
    created_at: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Optional[datetime] = Column(DateTime, nullable=True)
    duration_ms: Optional[int] = Column(Integer, nullable=True)

    # Relationships
    user = relationship("User", back_populates="calculations")

    def __repr__(self) -> str:
        """Provide a string representation of the calculation instance.

        Returns:
            A string containing the calculation ID, operation, and status.
        """
        return (
            f"<Calculation(id={self.id}, "
            f"operation='{self.operation}', "
            f"status='{self.status.value}')>"
        )

    @validates("operation")
    def validate_operation(self, key: str, value: str) -> str:
        """Validate the operation field.

        Args:
            key: The field name being validated.
            value: The operation string to validate.

        Returns:
            The validated operation string.

        Raises:
            ValueError: If the operation is empty or contains invalid characters.
        """
        if not value or not value.strip():
            raise ValueError("Operation cannot be empty")
        if len(value) > 50:
            raise ValueError("Operation must be 50 characters or less")
        if not value.isalpha() and value not in {"+", "-", "*", "/", "%", "**", "//"}:
            raise ValueError(f"Invalid operation: {value}")
        return value.strip()

    @validates("operand_a", "operand_b")
    def validate_operand(self, key: str, value: Decimal) -> Decimal:
        """Validate operand values.

        Args:
            key: The field name being validated.
            value: The operand value to validate.

        Returns:
            The validated operand value.

        Raises:
            ValueError: If the operand is None or exceeds allowed precision.
        """
        if value is None:
            raise ValueError(f"{key} cannot be None")
        try:
            decimal_value = Decimal(str(value))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{key} must be a valid decimal number") from exc
        if abs(decimal_value) > Decimal("9999999999.9999999999"):
            raise ValueError(f"{key} exceeds maximum allowed value")
        return decimal_value

    @validates("error_message")
    def validate_error_message(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate the error message field.

        Args:
            key: The field name being validated.
            value: The error message to validate.

        Returns:
            The validated error message or None.

        Raises:
            ValueError: If the error message exceeds maximum length.
        """
        if value is not None and len(value) > 500:
            raise ValueError("Error message must be 500 characters or less")
        return value

    def mark_completed(self, result: Decimal, duration_ms: int) -> None:
        """Mark the calculation as completed with the given result.

        Args:
            result: The computed result of the calculation.
            duration_ms: Time taken to compute the result in milliseconds.

        Raises:
            ValueError: If the calculation is not in pending status.
        """
        if self.status != CalculationStatus.PENDING:
            raise ValueError(
                f"Cannot mark calculation {self.id} as completed: "
                f"current status is '{self.status.value}'"
            )
        self.result = Decimal(str(result))
        self.status = CalculationStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.duration_ms = duration_ms

    def mark_failed(self, error_message: str, duration_ms: int) -> None:
        """Mark the calculation as failed with an error message.

        Args:
            error_message: Description of the error that occurred.
            duration_ms: Time elapsed before failure in milliseconds.

        Raises:
            ValueError: If the calculation is not in pending status.
        """
        if self.status != CalculationStatus.PENDING:
            raise ValueError(
                f"Cannot mark calculation {self.id} as failed: "
                f"current status is '{self.status.value}'"
            )
        self.error_message = error_message[:500] if error_message else "Unknown error"
        self.status = CalculationStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.duration_ms = duration_ms

    def cancel(self) -> None:
        """Cancel a pending calculation.

        Raises:
            ValueError: If the calculation is not in pending status.
        """
        if self.status != CalculationStatus.PENDING:
            raise ValueError(
                f"Cannot cancel calculation {self.id}: "
                f"current status is '{self.status.value}'"
            )
        self.status = CalculationStatus.CANCELLED
        self.completed_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert the calculation instance to a dictionary representation.

        Returns:
            A dictionary containing all calculation fields with serialized values.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "operation": self.operation,
            "operand_a": float(self.operand_a) if self.operand_a is not None else None,
            "operand_b": float(self.operand_b) if self.operand_b is not None else None,
            "result": float(self.result) if self.result is not None else None,
            "status": self.status.value,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }