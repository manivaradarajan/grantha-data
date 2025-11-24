"""JSON Schema validation for grantha files.

This module provides functions to validate grantha JSON files against the
canonical schemas defined in formats/schemas/.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from jsonschema import validators


def get_schema_path(schema_name: str) -> Path:
    """Get the absolute path to a schema file.

    Args:
        schema_name: Name of the schema file (e.g., 'grantha.schema.json')

    Returns:
        Path object pointing to the schema file
    """
    # Navigate from this file to the schemas directory
    # tools/lib/grantha_converter/schema_validator.py -> formats/schemas/
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent
    schema_path = project_root / 'formats' / 'schemas' / schema_name

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    return schema_path


def load_schema(schema_name: str) -> Dict[str, Any]:
    """Load a JSON schema file.

    Args:
        schema_name: Name of the schema file (e.g., 'grantha.schema.json')

    Returns:
        The parsed JSON schema as a dictionary
    """
    schema_path = get_schema_path(schema_name)
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_against_schema(data: Dict[str, Any], schema_name: str) -> Tuple[bool, List[str]]:
    """Validate a data dictionary against a schema.

    Args:
        data: The data to validate
        schema_name: Name of the schema file (e.g., 'grantha.schema.json')

    Returns:
        A tuple of (is_valid, error_messages)
        - is_valid: True if validation passed, False otherwise
        - error_messages: List of validation error messages (empty if valid)
    """
    try:
        schema = load_schema(schema_name)
        schema_path = get_schema_path(schema_name)
        schemas_dir = schema_path.parent

        # Create a custom resolver for handling $ref to other schema files
        from jsonschema import RefResolver
        resolver = RefResolver(
            base_uri=f"file://{schemas_dir}/",
            referrer=schema
        )

        # Create a validator that will collect all errors
        validator_class = validators.validator_for(schema)
        validator = validator_class(schema, resolver=resolver)

        errors = []
        for error in validator.iter_errors(data):
            # Format error message with path
            path = '.'.join(str(p) for p in error.path) if error.path else 'root'
            errors.append(f"{path}: {error.message}")

        if errors:
            return False, errors

        return True, []

    except FileNotFoundError as e:
        return False, [str(e)]
    except json.JSONDecodeError as e:
        return False, [f"Schema file is not valid JSON: {e}"]
    except Exception as e:
        return False, [f"Validation error: {e}"]


def validate_grantha_single(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a single-file grantha against grantha.schema.json.

    Args:
        data: The grantha data to validate

    Returns:
        A tuple of (is_valid, error_messages)
    """
    return validate_against_schema(data, 'grantha.schema.json')


def validate_grantha_part(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a grantha part against grantha-part.schema.json.

    Args:
        data: The grantha part data to validate

    Returns:
        A tuple of (is_valid, error_messages)
    """
    return validate_against_schema(data, 'grantha-part.schema.json')


def validate_grantha_envelope(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a grantha envelope against grantha-envelope.schema.json.

    Args:
        data: The envelope data to validate

    Returns:
        A tuple of (is_valid, error_messages)
    """
    return validate_against_schema(data, 'grantha-envelope.schema.json')
