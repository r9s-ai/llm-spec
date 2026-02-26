"""Response validation utilities.

The validator parses JSON from an httpx.Response and validates structure against Pydantic schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union, get_args, get_origin

import httpx
from pydantic import BaseModel, ValidationError

from llm_spec.json_types import JSONValue


@dataclass(frozen=True, slots=True)
class ValidationResult:
    is_valid: bool
    error_message: str | None
    missing_fields: list[str]
    expected_fields: list[str]


class ResponseValidator:
    """Validate responses using Pydantic."""

    @staticmethod
    def _extract_all_fields(
        schema_class: type[BaseModel],
        prefix: str = "",
        visited: set[type[BaseModel]] | None = None,
    ) -> list[str]:
        """Recursively extract all field paths from a Pydantic schema.

        Args:
            schema_class: Pydantic schema class
            prefix: current field path prefix
            visited: visited types set (prevents cycles)

        Returns:
            List of all field paths.
        """
        if visited is None:
            visited = set()

        # Prevent cyclic recursion
        if schema_class in visited:
            return []
        visited.add(schema_class)

        fields = []

        for field_name, field_info in schema_class.model_fields.items():
            # Build current field path
            field_path = f"{prefix}.{field_name}" if prefix else field_name
            fields.append(field_path)

            # Extract field type
            field_type = field_info.annotation
            origin = get_origin(field_type)

            # Handle Optional[T] / T | None -> extract T
            # In Python 3.10+, T | None creates types.UnionType
            if origin is Union or (
                origin is not None and str(origin) == "<class 'types.UnionType'>"
            ):
                # Filter out NoneType
                actual_types = [t for t in get_args(field_type) if t is not type(None)]
                if actual_types:
                    field_type = actual_types[0]
                    origin = get_origin(field_type)  # refresh origin

            # Handle list[T]
            if origin is list:
                inner_type = get_args(field_type)[0]
                if isinstance(inner_type, type) and issubclass(inner_type, BaseModel):
                    # Recurse into list element schema
                    nested_fields = ResponseValidator._extract_all_fields(
                        inner_type, field_path, visited.copy()
                    )
                    fields.extend(nested_fields)
                continue  # list element handled; skip BaseModel check below

            # Handle nested BaseModel
            if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                nested_fields = ResponseValidator._extract_all_fields(
                    field_type, field_path, visited.copy()
                )
                fields.extend(nested_fields)

        return fields

    @staticmethod
    def validate_json(data: JSONValue, schema_class: type[BaseModel]) -> ValidationResult:
        """Validate response data against a schema.

        Args:
            data: response data
            schema_class: Pydantic schema class

        Returns:
            (is_valid, error_message, missing_fields, expected_fields)
            - is_valid: validation passed
            - error_message: error message (if any)
            - missing_fields: missing field paths
            - expected_fields: expected field paths extracted from the schema
        """
        # Extract expected fields (including nested fields)
        expected_fields = ResponseValidator._extract_all_fields(schema_class)

        try:
            # Use Pydantic v2 validation so we can support both normal BaseModel and RootModel.
            # This allows validating text/plain responses against RootModel[str], etc.
            schema_class.model_validate(data)
            return ValidationResult(True, None, [], expected_fields)
        except ValidationError as e:
            # Extract missing fields
            missing_fields = []
            for error in e.errors():
                if error["type"] == "missing":
                    field_path = ".".join(str(loc) for loc in error["loc"])
                    missing_fields.append(field_path)

            error_message = str(e)
            return ValidationResult(False, error_message, missing_fields, expected_fields)

    @staticmethod
    def validate_response(
        response: httpx.Response, schema_class: type[BaseModel]
    ) -> ValidationResult:
        """Parse JSON from an httpx.Response and validate it."""
        try:
            data: JSONValue = response.json()
        except ValueError:
            # Non-JSON response (e.g. response_format=text) - validate against response.text if possible.
            text = response.text
            return ResponseValidator.validate_json(text, schema_class)

        return ResponseValidator.validate_json(data, schema_class)

    # Backward-compatible API (older call sites pass already-parsed dict)
    @staticmethod
    def validate(
        data: dict[str, Any], schema_class: type[BaseModel]
    ) -> tuple[bool, str | None, list[str], list[str]]:
        result = ResponseValidator.validate_json(data, schema_class)
        return result.is_valid, result.error_message, result.missing_fields, result.expected_fields
