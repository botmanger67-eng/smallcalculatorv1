"""
Calculator API endpoints for performing arithmetic operations.
Provides RESTful endpoints for basic calculator functionality.
"""

from typing import Dict, Union, Optional
from decimal import Decimal, InvalidOperation, DivisionByZero, ROUND_HALF_UP
from fastapi import APIRouter, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field, validator
import math
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/calculator",
    tags=["calculator"],
    responses={
        400: {"description": "Bad Request - Invalid input"},
        422: {"description": "Unprocessable Entity - Validation error"},
        500: {"description": "Internal Server Error"},
    },
)


class CalculationRequest(BaseModel):
    """Request model for calculator operations."""
    
    operand1: Union[int, float, str] = Field(
        ..., 
        description="First operand for the calculation",
        examples=[10, 5.5, "100.25"]
    )
    operand2: Union[int, float, str] = Field(
        ..., 
        description="Second operand for the calculation",
        examples=[20, 3.2, "50.75"]
    )
    precision: Optional[int] = Field(
        default=10,
        ge=0,
        le=50,
        description="Decimal precision for the result (0-50)"
    )

    @validator("operand1", "operand2", pre=True)
    def validate_operands(cls, value: Union[int, float, str]) -> Decimal:
        """Validate and convert operands to Decimal type."""
        try:
            if isinstance(value, (int, float)):
                return Decimal(str(value))
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    raise ValueError("Empty string is not allowed")
                return Decimal(value)
            raise ValueError(f"Unsupported type: {type(value)}")
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Invalid operand value: {value}. Error: {str(e)}")

    @validator("precision")
    def validate_precision(cls, value: Optional[int]) -> int:
        """Ensure precision has a default value if None."""
        return value if value is not None else 10


class CalculationResponse(BaseModel):
    """Response model for calculator operations."""
    
    result: Union[int, float, str] = Field(
        ..., 
        description="Result of the calculation",
        examples=[30, 8.7, "150.00"]
    )
    operation: str = Field(
        ..., 
        description="Type of operation performed",
        examples=["addition", "subtraction"]
    )
    operand1: str = Field(
        ..., 
        description="First operand as string",
        examples=["10", "5.5"]
    )
    operand2: str = Field(
        ..., 
        description="Second operand as string",
        examples=["20", "3.2"]
    )
    precision: int = Field(
        ..., 
        description="Precision used for the result",
        examples=[10, 2]
    )

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "result": 30,
                "operation": "addition",
                "operand1": "10",
                "operand2": "20",
                "precision": 10
            }
        }


class BatchCalculationRequest(BaseModel):
    """Request model for batch calculations."""
    
    operations: list[Dict[str, Union[str, int, float]]] = Field(
        ...,
        description="List of operations to perform",
        examples=[
            [{"operation": "add", "operand1": 10, "operand2": 20}],
            [{"operation": "multiply", "operand1": 5, "operand2": 3}]
        ]
    )
    precision: Optional[int] = Field(
        default=10,
        ge=0,
        le=50,
        description="Decimal precision for results"
    )

    @validator("operations")
    def validate_operations(cls, value: list) -> list:
        """Validate the operations list is not empty."""
        if not value:
            raise ValueError("Operations list cannot be empty")
        if len(value) > 100:
            raise ValueError("Maximum 100 operations allowed per batch")
        return value


class BatchCalculationResponse(BaseModel):
    """Response model for batch calculations."""
    
    results: list[Dict[str, Union[str, int, float]]] = Field(
        ...,
        description="List of calculation results",
        examples=[
            [{"operation": "addition", "result": 30}],
            [{"operation": "multiplication", "result": 15}]
        ]
    )
    total_operations: int = Field(
        ...,
        description="Total number of operations performed",
        examples=[1, 2]
    )
    precision: int = Field(
        ...,
        description="Precision used for results",
        examples=[10]
    )


def _perform_calculation(
    operand1: Decimal,
    operand2: Decimal,
    operation: str,
    precision: int
) -> Decimal:
    """
    Perform the specified arithmetic operation.
    
    Args:
        operand1: First operand
        operand2: Second operand
        operation: Type of operation to perform
        precision: Decimal precision for the result
        
    Returns:
        Decimal result of the operation
        
    Raises:
        ValueError: If operation is invalid
        DivisionByZero: If division by zero is attempted
        OverflowError: If result is too large
    """
    operation_map = {
        "add": lambda a, b: a + b,
        "subtract": lambda a, b: a - b,
        "multiply": lambda a, b: a * b,
        "divide": lambda a, b: a / b,
        "power": lambda a, b: a ** b,
        "modulo": lambda a, b: a % b,
        "floor_divide": lambda a, b: a // b,
    }
    
    if operation not in operation_map:
        valid_ops = ", ".join(operation_map.keys())
        raise ValueError(
            f"Invalid operation: '{operation}'. Valid operations: {valid_ops}"
        )
    
    try:
        result = operation_map[operation](operand1, operand2)
    except DivisionByZero:
        raise DivisionByZero("Division by zero is not allowed")
    except OverflowError:
        raise OverflowError("Result exceeds maximum allowed value")
    
    # Apply precision rounding
    quantize_str = f"1.{'0' * precision}" if precision > 0 else "1"
    result = result.quantize(
        Decimal(quantize_str),
        rounding=ROUND_HALF_UP
    )
    
    return result


def _format_result(result: Decimal, precision: int) -> Union[int, float, str]:
    """
    Format the Decimal result to appropriate type.
    
    Args:
        result: Decimal result to format
        precision: Number of decimal places
        
    Returns:
        Formatted result as int, float, or string
    """
    if precision == 0:
        return int(result)
    
    # Convert to float for JSON serialization
    float_result = float(result)
    
    # Return as integer if no decimal places needed
    if float_result == int(float_result):
        return int(float_result)
    
    # Return as float with proper precision
    return round(float_result, precision)


@router.post(
    "/add",
    response_model=CalculationResponse,
    summary="Add two numbers",
    description="Performs addition of two operands and returns the result.",
)
async def add_numbers(
    request: CalculationRequest = Body(
        ...,
        examples=[
            {
                "operand1": 10,
                "operand2": 20,
                "precision": 10
            }
        ]
    )
) -> CalculationResponse:
    """
    Add two numbers together.
    
    Args:
        request: Calculation request containing operands and precision
        
    Returns:
        CalculationResponse with the sum result
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        result = _perform_calculation(
            request.operand1,
            request.operand2,
            "add",
            request.precision
        )
        
        return CalculationResponse(
            result=_format_result(result, request.precision),
            operation="addition",
            operand1=str(request.operand1),
            operand2=str(request.operand2),
            precision=request.precision
        )
    except Exception as e:
        logger.error(f"Addition failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Addition failed: {str(e)}"
        )


@router.post(
    "/subtract",
    response_model=CalculationResponse,
    summary="Subtract two numbers",
    description="Performs subtraction of two operands and returns the result.",
)
async def subtract_numbers(
    request: CalculationRequest = Body(
        ...,
        examples=[
            {
                "operand1": 20,
                "operand2": 10,
                "precision": 10
            }
        ]
    )
) -> CalculationResponse:
    """
    Subtract second operand from first operand.
    
    Args:
        request: Calculation request containing operands and precision
        
    Returns:
        CalculationResponse with the difference result
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        result = _perform_calculation(
            request.operand1,
            request.operand2,
            "subtract",
            request.precision
        )
        
        return CalculationResponse(
            result=_format_result(result, request.precision),
            operation="subtraction",
            operand1=str(request.operand1),
            operand2=str(request.operand2),
            precision=request.precision
        )
    except Exception as e:
        logger.error(f"Subtraction failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Subtraction failed: {str(e)}"
        )


@router.post(
    "/multiply",
    response_model=CalculationResponse,
    summary="Multiply two numbers",
    description="Performs multiplication of two operands and returns the result.",
)
async def multiply_numbers(
    request: CalculationRequest = Body(
        ...,
        examples=[
            {
                "operand1": 5,
                "operand2": 3,
                "precision": 10
            }
        ]
    )
) -> CalculationResponse:
    """
    Multiply two numbers together.
    
    Args:
        request: Calculation request containing operands and precision
        
    Returns:
        CalculationResponse with the product result
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        result = _perform_calculation(
            request.operand1,
            request.operand2,
            "multiply",
            request.precision
        )
        
        return CalculationResponse(
            result=_format_result(result, request.precision),
            operation="multiplication",
            operand1=str(request.operand1),
            operand2=str(request.operand2),
            precision=request.precision
        )
    except Exception as e:
        logger.error(f"Multiplication failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Multiplication failed: {str(e)}"
        )


@router.post(
    "/divide",
    response_model=CalculationResponse,
    summary="Divide two numbers",
    description="Performs division of two operands and returns the result.",
)
async def divide_numbers(
    request: CalculationRequest = Body(
        ...,
        examples=[
            {
                "operand1": 10,
                "operand2": 3,
                "precision": 5
            }
        ]
    )
) -> CalculationResponse:
    """
    Divide first operand by second operand.
    
    Args:
        request: Calculation request containing operands and precision
        
    Returns:
        CalculationResponse with the quotient result
        
    Raises:
        HTTPException: If division by zero or calculation fails
    """
    try:
        result = _perform_calculation(
            request.operand1,
            request.operand2,
            "divide",
            request.precision
        )
        
        return CalculationResponse(
            result=_format_result(result, request.precision),
            operation="division",
            operand1=str(request.operand1),
            operand2=str(request.operand2),
            precision=request.precision
        )
    except DivisionByZero as e:
        logger.error(f"Division by zero: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="Division by zero is not allowed"
        )
    except Exception as e:
        logger.error(f"Division failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Division failed: {str(e)}"
        )


@router.post(
    "/power",
    response_model=CalculationResponse,
    summary="Calculate power",
    description="Raises first operand to the power of second operand.",
)
async def power_numbers(
    request: CalculationRequest = Body(
        ...,
        examples=[
            {
                "operand1": 2,
                "operand2": 10,
                "precision": 10
            }
        ]
    )
) -> CalculationResponse:
    """
    Calculate power of a number.
    
    Args:
        request: Calculation request containing operands and precision
        
    Returns:
        CalculationResponse with the power result
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        result = _perform_calculation(
            request.operand1,
            request.operand2,
            "power",
            request.precision
        )
        
        return CalculationResponse(
            result=_format_result(result, request.precision),
            operation="power",
            operand1=str(request.operand1),
            operand2=str(request.operand2),
            precision=request.precision
        )
    except OverflowError as e:
        logger.error(f"Power calculation overflow: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="Result exceeds maximum allowed value"
        )
    except Exception as e:
        logger.error(f"Power calculation failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Power calculation failed: {str(e)}"
        )


@router.post(
    "/modulo",
    response_model=CalculationResponse,
    summary="Calculate modulo",
    description="Returns the remainder of division of first operand by second operand.",
)
async def modulo_numbers(
    request: CalculationRequest = Body(
        ...,
        examples=[
            {
                "operand1": 10,
                "operand2": 3,
                "precision": 10
            }
        ]
    )
) -> CalculationResponse:
    """
    Calculate modulo (remainder) of division.
    
    Args:
        request: Calculation request containing operands and precision
        
    Returns:
        CalculationResponse with the modulo result
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        result = _perform_calculation(
            request.operand1,
            request.operand2,
            "modulo",
            request.precision
        )
        
        return CalculationResponse(
            result=_format_result(result, request.precision),
            operation="modulo",
            operand1=str(request.operand1),
            operand2=str(request.operand2),
            precision=request.precision
        )
    except DivisionByZero as e:
        logger.error(f"Modulo by zero: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="Modulo by zero is not allowed"
        )
    except Exception as e:
        logger.error(f"Modulo calculation failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Modulo calculation failed: {str(e)}"
        )


@router.post(
    "/floor-divide",
    response_model=CalculationResponse,
    summary="Floor divide two numbers",
    description="Performs floor division of two operands and returns the result.",
)
async def floor_divide_numbers(
    request: CalculationRequest = Body(
        ...,
        examples=[
            {
                "operand1": 10,
                "operand2": 3,
                "precision": 0
            }
        ]
    )
) -> CalculationResponse:
    """
    Perform floor division of first operand by second operand.
    
    Args:
        request: Calculation request containing operands and precision
        
    Returns:
        CalculationResponse with the floor division result
        
    Raises:
        HTTPException: If division by zero or calculation fails
    """
    try:
        result = _perform_calculation(
            request.operand1,
            request.operand2,
            "floor_divide",
            request.precision
        )
        
        return CalculationResponse(
            result=_format_result(result, request.precision),
            operation="floor_division",
            operand1=str(request.operand1),
            operand2=str(request.operand2),
            precision=request.precision
        )
    except DivisionByZero as e:
        logger.error(f"Floor division by zero: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="Floor division by zero is not allowed"
        )
    except Exception as e:
        logger.error(f"Floor division failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Floor division failed: {str(e)}"
        )


@router.post(
    "/batch",
    response_model=BatchCalculationResponse,
    summary="Perform batch calculations",
    description="Performs multiple calculations in a single request.",
)
async def batch_calculations(
    request: BatchCalculationRequest = Body(
        ...,
        examples=[
            {
                "operations": [
                    {"operation": "add", "operand1": 10, "operand2": 20},
                    {"operation": "multiply", "operand1": 5, "operand2": 3}
                ],
                "precision": 10
            }
        ]
    )
) -> BatchCalculationResponse:
    """
    Perform multiple calculations in a single request.
    
    Args:
        request: Batch calculation request containing list of operations
        
    Returns:
        BatchCalculationResponse with all results
        
    Raises:
        HTTPException: If any calculation fails
    """
    results = []
    
    for idx, operation_data in enumerate(request.operations):
        try:
            operation = operation_data.get("operation", "").lower()
            operand1 = operation_data.get("operand1")
            operand2 = operation_data.get("operand2")
            
            if not all([operation, operand1 is not None, operand2 is not None]):
                raise ValueError(
                    f"Operation {idx}: Missing required fields (operation, operand1, operand2)"
                )
            
            # Convert operands to Decimal
            try:
                dec_operand1 = Decimal(str(operand1))
                dec_operand2 = Decimal(str(operand2))
            except (InvalidOperation, ValueError) as e:
                raise ValueError(
                    f"Operation {idx}: Invalid operand values - {str(e)}"
                )
            
            result = _perform_calculation(
                dec_operand1,
                dec_operand2,
                operation,
                request.precision
            )
            
            results.append({
                "operation": operation,
                "result": _format_result(result, request.precision),
                "operand1": str(operand1),
                "operand2": str(operand2)
            })
            
        except DivisionByZero as e:
            logger.error(f"Batch operation {idx} division by zero: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Operation {idx}: Division by zero is not allowed"
            )
        except OverflowError as e:
            logger.error(f"Batch operation {idx} overflow: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Operation {idx}: Result exceeds maximum allowed value"
            )
        except ValueError as e:
            logger.error(f"Batch operation {idx} validation error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Batch operation {idx} failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Operation {idx}: Internal calculation error"
            )
    
    return BatchCalculationResponse(
        results=results,
        total_operations=len(results),
        precision=request.precision
    )


@router.get(
    "/health",
    response_model=Dict[str, str],
    summary="Health check",
    description="Returns the health status of the calculator service.",
)
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint for the calculator service.
    
    Returns:
        Dictionary with service status
    """
    return {
        "status": "healthy",
        "service": "calculator",
        "version": "1.0.0"
    }