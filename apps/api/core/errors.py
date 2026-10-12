"""Standardized error responses conforming to RFC 7807 Problem Details."""

import uuid
from typing import Dict, Any, Optional

class AppError(Exception):
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500,
                 details: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.request_id = request_id or str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "request_id": self.request_id,
            "details": self.details
        }

class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        super().__init__(message, code="NOT_FOUND", status_code=404, details=details, request_id=request_id)

class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400, details=details, request_id=request_id)

class AuthenticationError(AppError):
    def __init__(self, message: str = "Invalid credentials or unauthenticated", details: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        super().__init__(message, code="UNAUTHORIZED", status_code=401, details=details, request_id=request_id)

class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied: insufficient permissions or cross-tenant violation", details: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        super().__init__(message, code="FORBIDDEN", status_code=403, details=details, request_id=request_id)

class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict or duplicate", details: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        super().__init__(message, code="CONFLICT", status_code=409, details=details, request_id=request_id)

class RateLimitError(AppError):
    def __init__(self, message: str = "Too many requests. Please slow down.", details: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        super().__init__(message, code="RATE_LIMITED", status_code=429, details=details, request_id=request_id)

class SafetyBlockedError(AppError):
    def __init__(self, message: str = "Prescription blocked by clinical safety preflight engine.", details: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        super().__init__(message, code="SAFETY_BLOCKED", status_code=422, details=details, request_id=request_id)

