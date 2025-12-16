"""
Input Validation and Sanitization Utilities for Semptify.

Provides reusable validators and sanitizers for common input patterns.
Helps prevent injection attacks and data corruption.
"""

import re
import html
from typing import Optional, Annotated
from pydantic import AfterValidator, BeforeValidator, Field


# =============================================================================
# String Sanitizers
# =============================================================================

def sanitize_html(value: str) -> str:
    """
    Escape HTML entities to prevent XSS.
    Use for any user-provided text that will be rendered in HTML.
    """
    if not value:
        return value
    return html.escape(value)


def strip_control_chars(value: str) -> str:
    """
    Remove control characters (except newlines/tabs).
    Prevents null byte injection and similar attacks.
    """
    if not value:
        return value
    # Keep: \t (9), \n (10), \r (13), and printable chars (32+)
    return ''.join(c for c in value if ord(c) >= 32 or c in '\t\n\r')


def normalize_whitespace(value: str) -> str:
    """
    Normalize multiple spaces to single space, strip leading/trailing.
    """
    if not value:
        return value
    return ' '.join(value.split())


def sanitize_filename(value: str) -> str:
    """
    Sanitize filename to prevent path traversal and special chars.
    """
    if not value:
        return value
    # Remove path separators and null bytes
    value = value.replace('/', '').replace('\\', '').replace('\x00', '')
    # Remove other potentially dangerous chars
    value = re.sub(r'[<>:"|?*]', '', value)
    # Limit length
    return value[:255]


def sanitize_path(value: str) -> str:
    """
    Sanitize file path - prevent traversal attacks.
    """
    if not value:
        return value
    # Remove null bytes
    value = value.replace('\x00', '')
    # Prevent path traversal
    while '..' in value:
        value = value.replace('..', '')
    # Normalize separators
    value = value.replace('\\', '/')
    # Remove leading slashes (make relative)
    return value.lstrip('/')


# =============================================================================
# Pydantic Validators (use with Annotated)
# =============================================================================

def validate_no_html(value: str) -> str:
    """Validator that escapes HTML."""
    return sanitize_html(value)


def validate_clean_string(value: str) -> str:
    """Validator that strips control chars and normalizes whitespace."""
    value = strip_control_chars(value)
    return normalize_whitespace(value)


def validate_safe_filename(value: str) -> str:
    """Validator for safe filenames."""
    return sanitize_filename(value)


def validate_safe_path(value: str) -> str:
    """Validator for safe file paths."""
    return sanitize_path(value)


# Annotated types for Pydantic models
SafeString = Annotated[str, AfterValidator(validate_clean_string)]
SafeHtml = Annotated[str, AfterValidator(validate_no_html)]
SafeFilename = Annotated[str, AfterValidator(validate_safe_filename)]
SafePath = Annotated[str, AfterValidator(validate_safe_path)]


# =============================================================================
# Common Field Validators
# =============================================================================

# Email pattern (basic validation, not comprehensive)
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def validate_email(value: str) -> str:
    """Validate email format."""
    value = value.strip().lower()
    if not EMAIL_PATTERN.match(value):
        raise ValueError('Invalid email format')
    return value


# Phone pattern (US format, flexible)
PHONE_PATTERN = re.compile(r'^[\d\s\-\(\)\+\.]+$')

def validate_phone(value: str) -> str:
    """Validate and normalize phone number."""
    if not value:
        return value
    # Remove all non-digit chars for storage
    digits = re.sub(r'\D', '', value)
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError('Phone number must be 10-15 digits')
    return digits


# UUID pattern
UUID_PATTERN = re.compile(r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$')

def validate_uuid(value: str) -> str:
    """Validate UUID format."""
    value = value.strip().lower()
    if not UUID_PATTERN.match(value):
        raise ValueError('Invalid UUID format')
    return value


# =============================================================================
# SQL Injection Prevention
# =============================================================================

# Characters that could be used for SQL injection
SQL_DANGEROUS_CHARS = re.compile(r"[';\"\\]|--|\b(OR|AND|DROP|DELETE|INSERT|UPDATE|SELECT|UNION)\b", re.IGNORECASE)

def check_sql_injection(value: str) -> bool:
    """
    Check if string contains potential SQL injection patterns.
    Returns True if potentially dangerous.
    
    Note: This is a secondary defense - always use parameterized queries!
    """
    if not value:
        return False
    return bool(SQL_DANGEROUS_CHARS.search(value))


def sanitize_for_search(value: str) -> str:
    """
    Sanitize string for use in search queries.
    Removes special SQL chars but allows normal text.
    """
    if not value:
        return value
    # Remove quotes and semicolons
    value = re.sub(r"[';\"\\]", '', value)
    # Remove SQL keywords when standalone
    value = re.sub(r'\b(DROP|DELETE|INSERT|UPDATE|UNION)\b', '', value, flags=re.IGNORECASE)
    return value.strip()


# =============================================================================
# Length Validators
# =============================================================================

def create_length_validator(min_len: int = 0, max_len: int = 10000):
    """
    Factory for length validators.
    
    Usage:
        ShortText = Annotated[str, AfterValidator(create_length_validator(1, 100))]
    """
    def validator(value: str) -> str:
        if len(value) < min_len:
            raise ValueError(f'Must be at least {min_len} characters')
        if len(value) > max_len:
            raise ValueError(f'Must be at most {max_len} characters')
        return value
    return validator


# Pre-built length types
ShortText = Annotated[str, AfterValidator(create_length_validator(1, 200))]
MediumText = Annotated[str, AfterValidator(create_length_validator(1, 2000))]
LongText = Annotated[str, AfterValidator(create_length_validator(1, 50000))]


# =============================================================================
# Request Body Size Limits
# =============================================================================

MAX_JSON_BODY_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FORM_BODY_SIZE = 50 * 1024 * 1024  # 50MB (for file uploads)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Sanitizers
    'sanitize_html',
    'strip_control_chars',
    'normalize_whitespace',
    'sanitize_filename',
    'sanitize_path',
    'sanitize_for_search',
    # Validators
    'validate_no_html',
    'validate_clean_string',
    'validate_safe_filename',
    'validate_safe_path',
    'validate_email',
    'validate_phone',
    'validate_uuid',
    'check_sql_injection',
    'create_length_validator',
    # Annotated types
    'SafeString',
    'SafeHtml',
    'SafeFilename',
    'SafePath',
    'ShortText',
    'MediumText',
    'LongText',
    # Constants
    'MAX_JSON_BODY_SIZE',
    'MAX_FORM_BODY_SIZE',
]
