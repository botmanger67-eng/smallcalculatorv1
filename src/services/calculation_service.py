"""
Calculation service module providing enterprise-grade business logic for mathematical operations.
Implements robust error handling, logging, and type safety.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Union, Optional, Dict, Any
import logging
from dataclasses import dataclass
from enum import Enum
import math

logger = logging.getLogger(__name__)


class CalculationError(Exception):
    """Base exception for calculation-related errors."""
    pass


class DivisionByZeroError(CalculationError):
    """Raised when attempting to divide by zero."""
    pass


class InvalidOperandError(CalculationError):
    """Raised when operands are invalid for the operation."""
    pass


class OverflowError(CalculationError):
    """Raised when calculation results exceed system limits."""
    pass


class OperationType(Enum):
    """Enumeration of supported calculation operations."""
    ADDITION = "addition"
    SUBTRACTION = "subtraction"
    MULTIPLICATION = "multiplication"
    DIVISION = "division"
    POWER = "power"
    SQUARE_ROOT = "square_root"
    MODULUS = "modulus"
    PERCENTAGE = "percentage"


@dataclass(frozen=True)
class CalculationResult:
    """Immutable data class representing a calculation result."""
    value: Decimal
    operation: OperationType
    operands: tuple
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "value": str(self.value),
            "operation": self.operation.value,
            "operands": [str(op) for op in self.operands],
            "success": self.success,
            "error_message": self.error_message
        }


class CalculationService:
    """
    Enterprise-grade calculation service with comprehensive business logic.
    Handles various mathematical operations with proper error handling and validation.
    """

    MAX_DECIMAL_PLACES = 10
    MAX_OPERAND_VALUE = Decimal("1e100")
    MIN_OPERAND_VALUE = Decimal("-1e100")

    def __init__(self, precision: int = MAX_DECIMAL_PLACES):
        """
        Initialize calculation service with specified precision.

        Args:
            precision: Number of decimal places for rounding (default: 10)

        Raises:
            ValueError: If precision is negative
        """
        if precision < 0:
            raise ValueError("Precision must be non-negative")
        self.precision = precision
        logger.info(f"CalculationService initialized with precision={precision}")

    def _validate_operand(self, operand: Union[int, float, str, Decimal]) -> Decimal:
        """
        Validate and convert operand to Decimal.

        Args:
            operand: Input operand to validate

        Returns:
            Decimal representation of operand

        Raises:
            InvalidOperandError: If operand is invalid or out of range
        """
        try:
            if isinstance(operand, Decimal):
                decimal_value = operand
            elif isinstance(operand, (int, float)):
                decimal_value = Decimal(str(operand))
            elif isinstance(operand, str):
                decimal_value = Decimal(operand)
            else:
                raise InvalidOperandError(f"Unsupported operand type: {type(operand)}")

            if not self.MIN_OPERAND_VALUE <= decimal_value <= self.MAX_OPERAND_VALUE:
                raise InvalidOperandError(
                    f"Operand {decimal_value} out of allowed range "
                    f"[{self.MIN_OPERAND_VALUE}, {self.MAX_OPERAND_VALUE}]"
                )

            return decimal_value

        except (InvalidOperation, ValueError) as e:
            raise InvalidOperandError(f"Invalid operand: {operand}") from e

    def _round_result(self, value: Decimal) -> Decimal:
        """
        Round decimal value to configured precision.

        Args:
            value: Decimal value to round

        Returns:
            Rounded Decimal value
        """
        return value.quantize(
            Decimal(10) ** -self.precision,
            rounding=ROUND_HALF_UP
        )

    def _check_overflow(self, value: Decimal) -> None:
        """
        Check if value exceeds system limits.

        Args:
            value: Decimal value to check

        Raises:
            OverflowError: If value exceeds limits
        """
        if abs(value) > self.MAX_OPERAND_VALUE:
            raise OverflowError(f"Result {value} exceeds maximum allowed value")

    def add(self, a: Union[int, float, str, Decimal], b: Union[int, float, str, Decimal]) -> CalculationResult:
        """
        Perform addition of two numbers.

        Args:
            a: First operand
            b: Second operand

        Returns:
            CalculationResult containing sum
        """
        try:
            operand_a = self._validate_operand(a)
            operand_b = self._validate_operand(b)
            result = operand_a + operand_b
            self._check_overflow(result)
            rounded_result = self._round_result(result)
            logger.debug(f"Addition: {operand_a} + {operand_b} = {rounded_result}")
            return CalculationResult(
                value=rounded_result,
                operation=OperationType.ADDITION,
                operands=(operand_a, operand_b)
            )
        except CalculationError as e:
            logger.error(f"Addition failed: {e}")
            return CalculationResult(
                value=Decimal("0"),
                operation=OperationType.ADDITION,
                operands=(a, b),
                success=False,
                error_message=str(e)
            )

    def subtract(self, a: Union[int, float, str, Decimal], b: Union[int, float, str, Decimal]) -> CalculationResult:
        """
        Perform subtraction of two numbers.

        Args:
            a: First operand (minuend)
            b: Second operand (subtrahend)

        Returns:
            CalculationResult containing difference
        """
        try:
            operand_a = self._validate_operand(a)
            operand_b = self._validate_operand(b)
            result = operand_a - operand_b
            self._check_overflow(result)
            rounded_result = self._round_result(result)
            logger.debug(f"Subtraction: {operand_a} - {operand_b} = {rounded_result}")
            return CalculationResult(
                value=rounded_result,
                operation=OperationType.SUBTRACTION,
                operands=(operand_a, operand_b)
            )
        except CalculationError as e:
            logger.error(f"Subtraction failed: {e}")
            return CalculationResult(
                value=Decimal("0"),
                operation=OperationType.SUBTRACTION,
                operands=(a, b),
                success=False,
                error_message=str(e)
            )

    def multiply(self, a: Union[int, float, str, Decimal], b: Union[int, float, str, Decimal]) -> CalculationResult:
        """
        Perform multiplication of two numbers.

        Args:
            a: First operand
            b: Second operand

        Returns:
            CalculationResult containing product
        """
        try:
            operand_a = self._validate_operand(a)
            operand_b = self._validate_operand(b)
            result = operand_a * operand_b
            self._check_overflow(result)
            rounded_result = self._round_result(result)
            logger.debug(f"Multiplication: {operand_a} * {operand_b} = {rounded_result}")
            return CalculationResult(
                value=rounded_result,
                operation=OperationType.MULTIPLICATION,
                operands=(operand_a, operand_b)
            )
        except CalculationError as e:
            logger.error(f"Multiplication failed: {e}")
            return CalculationResult(
                value=Decimal("0"),
                operation=OperationType.MULTIPLICATION,
                operands=(a, b),
                success=False,
                error_message=str(e)
            )

    def divide(self, a: Union[int, float, str, Decimal], b: Union[int, float, str, Decimal]) -> CalculationResult:
        """
        Perform division of two numbers.

        Args:
            a: Dividend
            b: Divisor

        Returns:
            CalculationResult containing quotient

        Raises:
            DivisionByZeroError: If divisor is zero
        """
        try:
            operand_a = self._validate_operand(a)
            operand_b = self._validate_operand(b)

            if operand_b == Decimal("0"):
                raise DivisionByZeroError("Division by zero is not allowed")

            result = operand_a / operand_b
            self._check_overflow(result)
            rounded_result = self._round_result(result)
            logger.debug(f"Division: {operand_a} / {operand_b} = {rounded_result}")
            return CalculationResult(
                value=rounded_result,
                operation=OperationType.DIVISION,
                operands=(operand_a, operand_b)
            )
        except CalculationError as e:
            logger.error(f"Division failed: {e}")
            return CalculationResult(
                value=Decimal("0"),
                operation=OperationType.DIVISION,
                operands=(a, b),
                success=False,
                error_message=str(e)
            )

    def power(self, base: Union[int, float, str, Decimal], exponent: Union[int, float, str, Decimal]) -> CalculationResult:
        """
        Calculate base raised to exponent power.

        Args:
            base: Base number
            exponent: Exponent value

        Returns:
            CalculationResult containing power result
        """
        try:
            operand_base = self._validate_operand(base)
            operand_exponent = self._validate_operand(exponent)

            if operand_exponent != int(operand_exponent):
                raise InvalidOperandError("Exponent must be an integer for power operation")

            result = operand_base ** int(operand_exponent)
            self._check_overflow(result)
            rounded_result = self._round_result(result)
            logger.debug(f"Power: {operand_base} ^ {operand_exponent} = {rounded_result}")
            return CalculationResult(
                value=rounded_result,
                operation=OperationType.POWER,
                operands=(operand_base, operand_exponent)
            )
        except CalculationError as e:
            logger.error(f"Power calculation failed: {e}")
            return CalculationResult(
                value=Decimal("0"),
                operation=OperationType.POWER,
                operands=(base, exponent),
                success=False,
                error_message=str(e)
            )

    def square_root(self, a: Union[int, float, str, Decimal]) -> CalculationResult:
        """
        Calculate square root of a number.

        Args:
            a: Number to find square root of

        Returns:
            CalculationResult containing square root
        """
        try:
            operand = self._validate_operand(a)

            if operand < Decimal("0"):
                raise InvalidOperandError("Cannot calculate square root of negative number")

            result = Decimal(str(math.sqrt(float(operand))))
            self._check_overflow(result)
            rounded_result = self._round_result(result)
            logger.debug(f"Square root: sqrt({operand}) = {rounded_result}")
            return CalculationResult(
                value=rounded_result,
                operation=OperationType.SQUARE_ROOT,
                operands=(operand,)
            )
        except CalculationError as e:
            logger.error(f"Square root calculation failed: {e}")
            return CalculationResult(
                value=Decimal("0"),
                operation=OperationType.SQUARE_ROOT,
                operands=(a,),
                success=False,
                error_message=str(e)
            )

    def modulus(self, a: Union[int, float, str, Decimal], b: Union[int, float, str, Decimal]) -> CalculationResult:
        """
        Calculate modulus (remainder) of division.

        Args:
            a: Dividend
            b: Divisor

        Returns:
            CalculationResult containing remainder
        """
        try:
            operand_a = self._validate_operand(a)
            operand_b = self._validate_operand(b)

            if operand_b == Decimal("0"):
                raise DivisionByZeroError("Modulus by zero is not allowed")

            result = operand_a % operand_b
            self._check_overflow(result)
            rounded_result = self._round_result(result)
            logger.debug(f"Modulus: {operand_a} % {operand_b} = {rounded_result}")
            return CalculationResult(
                value=rounded_result,
                operation=OperationType.MODULUS,
                operands=(operand_a, operand_b)
            )
        except CalculationError as e:
            logger.error(f"Modulus calculation failed: {e}")
            return CalculationResult(
                value=Decimal("0"),
                operation=OperationType.MODULUS,
                operands=(a, b),
                success=False,
                error_message=str(e)
            )

    def percentage(self, value: Union[int, float, str, Decimal], total: Union[int, float, str, Decimal]) -> CalculationResult:
        """
        Calculate percentage of value relative to total.

        Args:
            value: The part value
            total: The total value

        Returns:
            CalculationResult containing percentage
        """
        try:
            operand_value = self._validate_operand(value)
            operand_total = self._validate_operand(total)

            if operand_total == Decimal("0"):
                raise DivisionByZeroError("Total cannot be zero for percentage calculation")

            result = (operand_value / operand_total) * Decimal("100")
            self._check_overflow(result)
            rounded_result = self._round_result(result)
            logger.debug(f"Percentage: ({operand_value} / {operand_total}) * 100 = {rounded_result}%")
            return CalculationResult(
                value=rounded_result,
                operation=OperationType.PERCENTAGE,
                operands=(operand_value, operand_total)
            )
        except CalculationError as e:
            logger.error(f"Percentage calculation failed: {e}")
            return CalculationResult(
                value=Decimal("0"),
                operation=OperationType.PERCENTAGE,
                operands=(value, total),
                success=False,
                error_message=str(e)
            )

    def execute_operation(
        self,
        operation: OperationType,
        operands: tuple
    ) -> CalculationResult:
        """
        Execute a calculation operation dynamically.

        Args:
            operation: Type of operation to perform
            operands: Tuple of operands for the operation

        Returns:
            CalculationResult from the executed operation

        Raises:
            ValueError: If unsupported operation is requested
        """
        operation_map = {
            OperationType.ADDITION: self.add,
            OperationType.SUBTRACTION: self.subtract,
            OperationType.MULTIPLICATION: self.multiply,
            OperationType.DIVISION: self.divide,
            OperationType.POWER: self.power,
            OperationType.SQUARE_ROOT: self.square_root,
            OperationType.MODULUS: self.modulus,
            OperationType.PERCENTAGE: self.percentage,
        }

        if operation not in operation_map:
            raise ValueError(f"Unsupported operation: {operation}")

        func = operation_map[operation]
        return func(*operands)