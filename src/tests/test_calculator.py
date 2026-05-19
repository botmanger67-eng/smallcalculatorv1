"""
Unit tests for the calculator API endpoint.

This module contains comprehensive tests for the calculator endpoint,
covering all arithmetic operations, error cases, and edge conditions.
"""

import pytest
from fastapi.testclient import TestClient
from typing import Dict, Any

from src.main import app
from src.models.calculator import OperationType


class TestCalculatorEndpoint:
    """
    Test suite for the calculator API endpoint.
    
    Tests cover:
    - Basic arithmetic operations (add, subtract, multiply, divide)
    - Input validation and error handling
    - Edge cases (division by zero, large numbers, precision)
    - Invalid operation types
    - Missing or malformed request bodies
    """

    @pytest.fixture(autouse=True)
    def setup_method(self) -> None:
        """Initialize test client before each test."""
        self.client: TestClient = TestClient(app)
        self.base_url: str = "/api/v1/calculator"

    def _make_calculation_request(
        self, operation: str, operand1: float, operand2: float
    ) -> Dict[str, Any]:
        """
        Helper method to make calculation requests.
        
        Args:
            operation: The arithmetic operation to perform
            operand1: First operand
            operand2: Second operand
            
        Returns:
            Response JSON as dictionary
        """
        payload: Dict[str, Any] = {
            "operation": operation,
            "operand1": operand1,
            "operand2": operand2
        }
        response = self.client.post(self.base_url, json=payload)
        return response.json()

    def test_addition_positive_numbers(self) -> None:
        """Test addition with positive numbers."""
        result = self._make_calculation_request("add", 5.0, 3.0)
        assert result["result"] == 8.0
        assert result["operation"] == "add"
        assert result["status"] == "success"

    def test_addition_negative_numbers(self) -> None:
        """Test addition with negative numbers."""
        result = self._make_calculation_request("add", -5.0, -3.0)
        assert result["result"] == -8.0
        assert result["status"] == "success"

    def test_addition_mixed_signs(self) -> None:
        """Test addition with mixed sign numbers."""
        result = self._make_calculation_request("add", -5.0, 3.0)
        assert result["result"] == -2.0
        assert result["status"] == "success"

    def test_subtraction_positive_numbers(self) -> None:
        """Test subtraction with positive numbers."""
        result = self._make_calculation_request("subtract", 10.0, 4.0)
        assert result["result"] == 6.0
        assert result["status"] == "success"

    def test_subtraction_negative_result(self) -> None:
        """Test subtraction resulting in negative number."""
        result = self._make_calculation_request("subtract", 4.0, 10.0)
        assert result["result"] == -6.0
        assert result["status"] == "success"

    def test_multiplication_positive_numbers(self) -> None:
        """Test multiplication with positive numbers."""
        result = self._make_calculation_request("multiply", 4.0, 5.0)
        assert result["result"] == 20.0
        assert result["status"] == "success"

    def test_multiplication_by_zero(self) -> None:
        """Test multiplication by zero."""
        result = self._make_calculation_request("multiply", 10.0, 0.0)
        assert result["result"] == 0.0
        assert result["status"] == "success"

    def test_multiplication_negative_numbers(self) -> None:
        """Test multiplication with negative numbers."""
        result = self._make_calculation_request("multiply", -4.0, 5.0)
        assert result["result"] == -20.0
        assert result["status"] == "success"

    def test_division_exact(self) -> None:
        """Test exact division."""
        result = self._make_calculation_request("divide", 10.0, 2.0)
        assert result["result"] == 5.0
        assert result["status"] == "success"

    def test_division_with_remainder(self) -> None:
        """Test division resulting in decimal."""
        result = self._make_calculation_request("divide", 10.0, 3.0)
        assert abs(result["result"] - 3.3333333333333335) < 1e-10
        assert result["status"] == "success"

    def test_division_by_zero(self) -> None:
        """Test division by zero error handling."""
        result = self._make_calculation_request("divide", 10.0, 0.0)
        assert "error" in result
        assert result["status"] == "error"
        assert "division by zero" in result["error"].lower()

    def test_division_negative_numbers(self) -> None:
        """Test division with negative numbers."""
        result = self._make_calculation_request("divide", -10.0, 2.0)
        assert result["result"] == -5.0
        assert result["status"] == "success"

    def test_invalid_operation(self) -> None:
        """Test invalid operation type."""
        result = self._make_calculation_request("power", 2.0, 3.0)
        assert "error" in result
        assert result["status"] == "error"

    def test_missing_operand(self) -> None:
        """Test request with missing operand."""
        payload: Dict[str, Any] = {
            "operation": "add",
            "operand1": 5.0
        }
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 422  # Validation error

    def test_invalid_operand_type(self) -> None:
        """Test request with non-numeric operand."""
        payload: Dict[str, Any] = {
            "operation": "add",
            "operand1": "abc",
            "operand2": 3.0
        }
        response = self.client.post(self.base_url, json=payload)
        assert response.status_code == 422  # Validation error

    def test_large_numbers(self) -> None:
        """Test calculation with very large numbers."""
        result = self._make_calculation_request(
            "multiply", 1e15, 1e15
        )
        assert result["result"] == 1e30
        assert result["status"] == "success"

    def test_floating_point_precision(self) -> None:
        """Test floating point precision handling."""
        result = self._make_calculation_request("add", 0.1, 0.2)
        assert abs(result["result"] - 0.3) < 1e-10
        assert result["status"] == "success"

    def test_empty_request_body(self) -> None:
        """Test request with empty body."""
        response = self.client.post(self.base_url, json={})
        assert response.status_code == 422  # Validation error

    def test_health_check(self) -> None:
        """Test health check endpoint."""
        response = self.client.get(f"{self.base_url}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_all_operations_successful(self) -> None:
        """Test all valid operations return success status."""
        operations = ["add", "subtract", "multiply", "divide"]
        for operation in operations:
            result = self._make_calculation_request(operation, 10.0, 2.0)
            assert result["status"] == "success", f"Failed for {operation}"

    def test_operation_case_insensitivity(self) -> None:
        """Test that operation names are case-insensitive."""
        result = self._make_calculation_request("ADD", 5.0, 3.0)
        assert result["result"] == 8.0
        assert result["status"] == "success"

    def test_negative_zero_handling(self) -> None:
        """Test handling of negative zero."""
        result = self._make_calculation_request("add", -0.0, 0.0)
        assert result["result"] == 0.0
        assert result["status"] == "success"

    def test_concurrent_requests(self) -> None:
        """Test handling of multiple concurrent requests."""
        import concurrent.futures
        
        def make_request() -> Dict[str, Any]:
            return self._make_calculation_request("add", 1.0, 1.0)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        for result in results:
            assert result["result"] == 2.0
            assert result["status"] == "success"

    def test_response_structure(self) -> None:
        """Test that response contains all required fields."""
        result = self._make_calculation_request("add", 5.0, 3.0)
        required_fields = ["result", "operation", "status", "timestamp"]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_error_response_structure(self) -> None:
        """Test that error response contains proper structure."""
        result = self._make_calculation_request("divide", 10.0, 0.0)
        assert "error" in result
        assert "status" in result
        assert result["status"] == "error"
        assert isinstance(result["error"], str)