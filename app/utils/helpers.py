"""
Utility functions for the Social Media Scraping API.

This module provides:
- Rate limiting utilities
- Logging configuration
- Response helpers
- Validation utilities
"""

import time
import logging
import functools
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import hashlib


# =============================================================================
# Logging Configuration
# =============================================================================

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log')
        ]
    )
    
    # Set specific log levels for external libraries
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


# =============================================================================
# Rate Limiting
# =============================================================================

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom rate limit exceeded handler."""
    # Extract retry_after from the exception if available, otherwise use default
    retry_after = getattr(exc, 'retry_after', None)
    
    response_data = {
        "success": False,
        "error": "RateLimitExceeded",
        "message": f"Rate limit exceeded: {exc.detail}",
        "status_code": 429,
        "endpoint": str(request.url.path),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Only add retry_after if it exists
    if retry_after is not None:
        response_data["retry_after"] = retry_after
    else:
        response_data["hint"] = "Please wait a moment before making another request"
    
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=response_data
    )


# =============================================================================
# Response Helpers
# =============================================================================

def create_response(
    success: bool = True,
    message: str = "Operation successful",
    data: Any = None,
    errors: list = None,
    status_code: int = 200
) -> JSONResponse:
    """
    Create a standardized JSON response.
    
    Args:
        success: Whether the operation was successful
        message: Human-readable message
        data: Response data
        errors: List of errors
        status_code: HTTP status code
        
    Returns:
        JSONResponse: Standardized response
    """
    response_data = {
        "success": success,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if data is not None:
        response_data["data"] = data
        
    if errors:
        response_data["errors"] = errors
    
    return JSONResponse(
        content=response_data,
        status_code=status_code
    )


def error_response(
    message: str,
    error_type: str = "ValidationError",
    status_code: int = 400,
    details: dict = None
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        message: Error message
        error_type: Type of error
        status_code: HTTP status code
        details: Additional error details
        
    Returns:
        JSONResponse: Error response
    """
    response_data = {
        "success": False,
        "error": error_type,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if details:
        response_data["details"] = details
    
    return JSONResponse(
        content=response_data,
        status_code=status_code
    )


# =============================================================================
# Validation Utilities
# =============================================================================

def validate_instagram_username(username: str) -> bool:
    """
    Validate Instagram username format.
    
    Args:
        username: Instagram username to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not username:
        return False
        
    # Remove @ if present
    username = username.lstrip('@')
    
    # Check length (1-30 characters)
    if not (1 <= len(username) <= 30):
        return False
    
    # Check allowed characters (letters, numbers, periods, underscores)
    allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._')
    if not all(c in allowed_chars for c in username):
        return False
        
    # Cannot start or end with period
    if username.startswith('.') or username.endswith('.'):
        return False
        
    return True


def validate_youtube_channel_id(channel_id: str) -> bool:
    """
    Validate YouTube channel ID format.
    
    Args:
        channel_id: YouTube channel ID to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not channel_id:
        return False
        
    # Channel IDs typically start with 'UC' and are 24 characters long
    if channel_id.startswith('UC') and len(channel_id) == 24:
        return True
        
    # Handle URLs like youtube.com/c/channelname or youtube.com/@username
    if 'youtube.com' in channel_id:
        return True
        
    return False


# =============================================================================
# Security Utilities
# =============================================================================

def hash_string(input_string: str, salt: str = "") -> str:
    """
    Create a hash of a string for secure storage or comparison.
    
    Args:
        input_string: String to hash
        salt: Optional salt for additional security
        
    Returns:
        str: Hexadecimal hash
    """
    combined = input_string + salt
    return hashlib.sha256(combined.encode()).hexdigest()


def is_safe_filename(filename: str) -> bool:
    """
    Check if a filename is safe for use.
    
    Args:
        filename: Filename to validate
        
    Returns:
        bool: True if safe, False otherwise
    """
    dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
    return not any(char in filename for char in dangerous_chars)


# =============================================================================
# Performance Utilities
# =============================================================================

def timing_decorator(func):
    """
    Decorator to measure function execution time.
    
    Args:
        func: Function to measure
        
    Returns:
        Wrapped function with timing
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            logging.info(f"{func.__name__} executed in {execution_time:.2f}ms")
            return result
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logging.error(f"{func.__name__} failed after {execution_time:.2f}ms: {str(e)}")
            raise
    return wrapper


# =============================================================================
# Data Processing Utilities
# =============================================================================

def paginate_query(query, page: int, per_page: int):
    """
    Apply pagination to a SQLAlchemy query.
    
    Args:
        query: SQLAlchemy query object
        page: Page number (1-based)
        per_page: Items per page
        
    Returns:
        tuple: (items, total_count, has_next, has_prev)
    """
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    items = query.offset(offset).limit(per_page).all()
    
    # Calculate pagination info
    has_next = offset + per_page < total_count
    has_prev = page > 1
    total_pages = (total_count + per_page - 1) // per_page
    
    return {
        "items": items,
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev
    }


def clean_text(text: str) -> str:
    """
    Clean and sanitize text content.
    
    Args:
        text: Input text to clean
        
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""
        
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    # Remove or replace problematic characters
    text = text.replace('\x00', '')  # Remove null bytes
    
    return text.strip()


# =============================================================================
# Health Check Utilities
# =============================================================================

def check_service_health() -> Dict[str, Any]:
    """
    Check the overall health of the service.
    
    Returns:
        dict: Health status information
    """
    from app.database import test_connection
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "checks": {
            "database": test_connection(),
            "api": True,  # If we can execute this, API is running
        }
    }
    
    # Determine overall status
    if not all(health_status["checks"].values()):
        health_status["status"] = "unhealthy"
    
    return health_status