"""Standardized error types for ZAYVORA MATAB OS."""

from typing import Dict, Any, Optional

class AppError(Exception):
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details
        }

class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="NOT_FOUND", status_code=404, details=details)

class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400, details=details)

class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication required", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="UNAUTHORIZED", status_code=401, details=details)

class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="FORBIDDEN", status_code=403, details=details)

class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict or duplicate", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="CONFLICT", status_code=409, details=details)

class SafetyBlockedError(AppError):
    def __init__(self, message: str = "Prescription safety check failed with critical BLOCK state", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="SAFETY_BLOCKED", status_code=422, details=details)

class SafetyUnknownError(AppError):
    def __init__(self, message: str = "Critical safety data is missing; fail-closed policy requires clinical override", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="SAFETY_UNKNOWN_BLOCKED", status_code=422, details=details)
