import html
import re
from typing import Any, Optional


def sanitize_string(value: Optional[str]) -> Optional[str]:
    """
    Sanitize a string by escaping HTML special characters to prevent XSS.
    Returns None if input is None.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    return html.escape(str(value), quote=True)


def sanitize_dict(data: dict[str, Any], fields: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Sanitize specific fields in a dictionary by escaping HTML special characters.
    If fields is None, sanitizes all string values.

    Args:
        data: Dictionary to sanitize
        fields: List of field names to sanitize. If None, sanitizes all strings.

    Returns:
        New dictionary with sanitized values
    """
    if not data:
        return data

    sanitized = {}
    for key, value in data.items():
        if fields is None or key in fields:
            if isinstance(value, str):
                sanitized[key] = sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = sanitize_dict(value, fields)
            elif isinstance(value, list):
                sanitized[key] = [
                    (
                        sanitize_dict(item, fields)
                        if isinstance(item, dict)
                        else sanitize_string(item) if isinstance(item, str) else item
                    )
                    for item in value
                ]
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value

    return sanitized


def validate_and_sanitize_input(value: str, max_length: int = 500) -> str:
    """
    Validate and sanitize user input by removing potentially harmful content.

    Args:
        value: Input string to validate
        max_length: Maximum allowed length

    Returns:
        Sanitized string

    Raises:
        ValueError: If input is invalid
    """
    if not value:
        return ""

    value = str(value).strip()

    if len(value) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length} characters")

    value = html.escape(value, quote=True)

    value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", value)

    return value
