"""Schema validator for comparing API responses against Pydantic models."""

from __future__ import annotations

import types
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from llm_spec.core.report import FieldResult, FieldStatus, ValidationReport


class SchemaValidator:
    """Validates API responses against Pydantic schema definitions."""

    def __init__(self, provider: str, endpoint: str) -> None:
        self.provider = provider
        self.endpoint = endpoint
        self._results: list[FieldResult] = []

    def validate(
        self,
        response: dict[str, Any],
        schema: type[BaseModel],
        request_params: dict[str, Any] | None = None,
    ) -> ValidationReport:
        """Validate a response dict against a Pydantic model schema.

        Args:
            response: The API response dict to validate
            schema: The Pydantic model to validate against
            request_params: Optional request parameters used to get this response

        Returns:
            ValidationReport with field-level results
        """
        self._results = []
        self._validate_object(response, schema, path="")

        valid_count = sum(1 for r in self._results if r.status == FieldStatus.VALID)
        # UNEXPECTED fields are acceptable (extra fields from API), only count real errors
        invalid_count = sum(
            1
            for r in self._results
            if r.status not in (FieldStatus.VALID, FieldStatus.UNEXPECTED)
        )

        return ValidationReport(
            provider=self.provider,
            endpoint=self.endpoint,
            success=invalid_count == 0,
            total_fields=len(self._results),
            valid_count=valid_count,
            invalid_count=invalid_count,
            fields=self._results,
            request_params=request_params,
            raw_response=response,
        )

    def _validate_object(
        self,
        data: dict[str, Any],
        schema: type[BaseModel],
        path: str,
    ) -> None:
        """Validate an object against a Pydantic model."""
        model_fields = schema.model_fields

        # Check defined fields
        for field_name, field_info in model_fields.items():
            field_path = f"{path}.{field_name}" if path else field_name
            self._validate_field(data, field_name, field_info, field_path)

        # Check for unexpected fields
        for key in data:
            if key not in model_fields:
                field_path = f"{path}.{key}" if path else key
                self._results.append(
                    FieldResult(
                        field=field_path,
                        status=FieldStatus.UNEXPECTED,
                        actual=type(data[key]).__name__,
                    )
                )

    def _validate_field(
        self,
        data: dict[str, Any],
        field_name: str,
        field_info: FieldInfo,
        path: str,
    ) -> None:
        """Validate a single field."""
        annotation = field_info.annotation
        is_required = field_info.is_required()

        if field_name not in data:
            if is_required:
                self._results.append(
                    FieldResult(
                        field=path,
                        status=FieldStatus.MISSING,
                        expected=self._type_name(annotation),
                    )
                )
            return

        value = data[field_name]
        self._validate_value(value, annotation, path)

    def _validate_value(self, value: Any, annotation: Any, path: str) -> None:
        """Validate a value against its type annotation."""
        origin = get_origin(annotation)
        args = get_args(annotation)

        # Handle None
        if value is None:
            if annotation is type(None):
                self._results.append(
                    FieldResult(
                        field=path, status=FieldStatus.VALID, expected="None", actual="null"
                    )
                )
            elif self._is_optional(annotation):
                self._results.append(
                    FieldResult(
                        field=path, status=FieldStatus.VALID, expected="None", actual="null"
                    )
                )
            else:
                self._results.append(
                    FieldResult(
                        field=path,
                        status=FieldStatus.INVALID_TYPE,
                        expected=self._type_name(annotation),
                        actual="null",
                    )
                )
            return

        # Handle Literal types - check value matches one of the allowed values
        if origin is Literal:
            allowed_values = args
            if value in allowed_values:
                self._results.append(
                    FieldResult(
                        field=path,
                        status=FieldStatus.VALID,
                        expected=self._type_name(annotation),
                        actual=repr(value),
                    )
                )
            else:
                self._results.append(
                    FieldResult(
                        field=path,
                        status=FieldStatus.INVALID_TYPE,
                        expected=self._type_name(annotation),
                        actual=repr(value),
                    )
                )
            return

        # Handle Union types (including Optional, e.g., str | None)
        if origin is types.UnionType or origin is Union:
            non_none_args = [arg for arg in args if arg is not type(None)]

            # If value is not None and we have non-None types to check
            for arg in non_none_args:
                if self._check_type(value, arg):
                    # Found a matching type, validate against it
                    self._validate_value(value, arg, path)
                    return

            # No matching type found
            self._results.append(
                FieldResult(
                    field=path,
                    status=FieldStatus.INVALID_TYPE,
                    expected=self._type_name(annotation),
                    actual=type(value).__name__,
                )
            )
            return

        # Handle list
        if origin is list:
            if not isinstance(value, list):
                self._results.append(
                    FieldResult(
                        field=path,
                        status=FieldStatus.INVALID_TYPE,
                        expected="list",
                        actual=type(value).__name__,
                    )
                )
                return
            self._results.append(
                FieldResult(
                    field=path,
                    status=FieldStatus.VALID,
                    expected="list",
                    actual=f"list[{len(value)}]",
                )
            )
            if args:
                item_type = args[0]
                for i, item in enumerate(value):
                    self._validate_value(item, item_type, f"{path}[{i}]")
            return

        # Handle dict
        if origin is dict:
            if not isinstance(value, dict):
                self._results.append(
                    FieldResult(
                        field=path,
                        status=FieldStatus.INVALID_TYPE,
                        expected="dict",
                        actual=type(value).__name__,
                    )
                )
                return
            self._results.append(
                FieldResult(
                    field=path, status=FieldStatus.VALID, expected="dict", actual="dict"
                )
            )
            return

        # Handle Pydantic models (nested objects)
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if not isinstance(value, dict):
                self._results.append(
                    FieldResult(
                        field=path,
                        status=FieldStatus.INVALID_TYPE,
                        expected="object",
                        actual=type(value).__name__,
                    )
                )
                return
            self._validate_object(value, annotation, path)
            return

        # Handle basic types
        expected_type = self._get_python_type(annotation)
        if expected_type and isinstance(value, expected_type):
            self._results.append(
                FieldResult(
                    field=path,
                    status=FieldStatus.VALID,
                    expected=self._type_name(annotation),
                    actual=self._format_actual_value(value),
                )
            )
        else:
            self._results.append(
                FieldResult(
                    field=path,
                    status=FieldStatus.INVALID_TYPE,
                    expected=self._type_name(annotation),
                    actual=type(value).__name__,
                )
            )

    def _is_optional(self, annotation: Any) -> bool:
        """Check if a type annotation is Optional (includes None in Union)."""
        origin = get_origin(annotation)
        if origin is types.UnionType or origin is Union:
            return type(None) in get_args(annotation)
        return False

    def _check_type(self, value: Any, annotation: Any) -> bool:
        """Check if value matches the annotation type."""
        origin = get_origin(annotation)

        # Handle Literal - check if value is one of the allowed values
        if origin is Literal:
            return value in get_args(annotation)

        # Handle dict origin
        if origin is dict:
            return isinstance(value, dict)

        # Handle list origin
        if origin is list:
            return isinstance(value, list)

        py_type = self._get_python_type(annotation)
        if py_type:
            return isinstance(value, py_type)

        # Handle Pydantic models - try to match by discriminator field (usually 'type')
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if not isinstance(value, dict):
                return False

            # Try to match using a discriminator field (commonly 'type')
            model_fields = annotation.model_fields
            if "type" in model_fields:
                type_field = model_fields["type"]
                type_annotation = type_field.annotation
                type_origin = get_origin(type_annotation)

                # Check if 'type' field is a Literal
                if type_origin is Literal:
                    expected_values = get_args(type_annotation)
                    actual_value = value.get("type")
                    return actual_value in expected_values

            # Fallback: any dict could potentially match
            return True

        return False

    def _get_python_type(self, annotation: Any) -> type | tuple[type, ...] | None:
        """Convert type annotation to Python type for isinstance check."""
        if annotation is str:
            return str
        if annotation is int:
            return int
        if annotation is float:
            return (int, float)  # int is also valid for float
        if annotation is bool:
            return bool
        if annotation is list:
            return list
        if annotation is dict:
            return dict
        return None

    def _format_actual_value(self, value: Any) -> str:
        """Format actual value for display in reports.

        For basic types, show the type name. For strings, show truncated value.
        """
        if isinstance(value, str):
            # Truncate long strings
            if len(value) > 50:
                return f'str: "{value[:47]}..."'
            return f'str: "{value}"'
        elif isinstance(value, bool):
            return f"bool: {value}"
        elif isinstance(value, int):
            return f"int: {value}"
        elif isinstance(value, float):
            return f"float: {value}"
        else:
            return type(value).__name__

    def _type_name(self, annotation: Any) -> str:
        """Get a readable name for a type annotation."""
        origin = get_origin(annotation)
        args = get_args(annotation)

        # Handle Literal types
        if origin is Literal:
            values = ", ".join(repr(v) for v in args)
            return f"Literal[{values}]"

        # Handle Union types (including X | None)
        if origin is types.UnionType or origin is Union:
            type_names = [self._type_name(a) for a in args if a is not type(None)]
            if type(None) in args:
                if len(type_names) == 1:
                    return f"{type_names[0]} | None"
                return f"({' | '.join(type_names)}) | None"
            return " | ".join(type_names)

        if origin is list:
            if args:
                return f"list[{self._type_name(args[0])}]"
            return "list"

        if origin is dict:
            if args:
                return f"dict[{self._type_name(args[0])}, {self._type_name(args[1])}]"
            return "dict"

        if isinstance(annotation, type):
            return annotation.__name__

        return str(annotation)
