"""
Authentication router for user registration, login, and profile management.

This module provides endpoints for:
- User registration with validation
- User login with JWT token generation  
- Protected user profile access
- Password management
"""

from datetime import timedelta
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserResponse, Token, APIResponse
from app.auth.auth import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.utils.helpers import create_response, error_response, limiter

# Create router with prefix and tags
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # Rate limit: 5 registrations per minute per IP
async def register_user(
    user_request: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Register a new user account.
    
    **Rate Limited**: 5 requests per minute per IP address.
    
    **Request Body**:
    - username: Username (3-50 characters, alphanumeric + underscore/period)
    - email: Valid email address (must be unique)
    - password: Password (minimum 8 chars, must contain uppercase, lowercase, digit)
    - full_name: User's full name (required)
    
    **Returns**:
    - Success message with user ID
    - HTTP 201: User created successfully
    - HTTP 400: Validation errors or user already exists
    - HTTP 429: Rate limit exceeded
    
    **Example**:
    ```json
    {
        "username": "john_doe",
        "email": "john@example.com", 
        "password": "SecurePass123",
        "full_name": "John Doe"
    }
    ```
    """
    # Check if username already exists
    existing_username = db.query(User).filter(User.username == user_request.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_request.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_request.password)
    new_user = User(
        username=user_request.username,
        email=user_request.email,
        password_hash=hashed_password,
        full_name=user_request.full_name,
        is_active=True
    )
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return create_response(
            success=True,
            message="User registered successfully",
            data={
                "user_id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "full_name": new_user.full_name
            },
            status_code=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")  # Rate limit: 10 login attempts per minute per IP
async def login_user(
    user_request: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
) -> Token:
    """
    Authenticate user and return JWT access token.
    
    **Rate Limited**: 10 requests per minute per IP address.
    
    **Request Body**:
    - username: Username or email address
    - password: User's password
    
    **Returns**:
    - JWT access token with expiration info
    - HTTP 200: Login successful
    - HTTP 401: Invalid credentials or inactive user
    - HTTP 429: Rate limit exceeded
    
    **Example**:
    ```json
    {
        "username": "john_doe",
        "password": "SecurePass123"
    }
    ```
    
    **Response**:
    ```json
    {
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "token_type": "bearer",
        "expires_in": 1800
    }
    ```
    """
    # Authenticate user
    user = authenticate_user(db, user_request.username, user_request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Get current authenticated user's profile information.
    
    **Authentication Required**: Bearer token in Authorization header.
    
    **Returns**:
    - User profile information (excluding password)
    - HTTP 200: Profile retrieved successfully
    - HTTP 401: Invalid or expired token
    - HTTP 403: User account inactive
    
    **Headers**:
    ```
    Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
    ```
    
    **Response**:
    ```json
    {
        "id": 1,
        "username": "john_doe",
        "email": "john@example.com",
        "is_active": true,
        "is_admin": false,
        "created_at": "2024-01-15T10:30:00",
        "updated_at": "2024-01-15T10:30:00"
    }
    ```
    """
    return UserResponse.from_orm(current_user)


@router.put("/profile", response_model=APIResponse)
@limiter.limit("5/minute")  # Rate limit: 5 profile updates per minute per user
async def update_profile(
    request: Request,
    email: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update current user's profile information.
    
    **Authentication Required**: Bearer token in Authorization header.
    **Rate Limited**: 5 requests per minute per IP address.
    
    **Query Parameters**:
    - email: New email address (must be unique)
    
    **Returns**:
    - Success message with updated profile info
    - HTTP 200: Profile updated successfully
    - HTTP 400: Email already in use or validation error
    - HTTP 401: Invalid or expired token
    - HTTP 429: Rate limit exceeded
    
    **Example**:
    ```
    PUT /auth/profile?email=newemail@example.com
    Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
    ```
    """
    # Check if new email is already in use by another user
    existing_email = db.query(User).filter(
        User.email == email,
        User.id != current_user.id
    ).first()
    
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already in use"
        )
    
    try:
        # Update user email
        current_user.email = email
        db.commit()
        db.refresh(current_user)
        
        return create_response(
            success=True,
            message="Profile updated successfully",
            data={
                "user_id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "updated_at": current_user.updated_at.isoformat()
            }
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.post("/change-password", response_model=APIResponse)
@limiter.limit("3/minute")  # Rate limit: 3 password changes per minute per user
async def change_password(
    request: Request,
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Change current user's password.
    
    **Authentication Required**: Bearer token in Authorization header.
    **Rate Limited**: 3 requests per minute per IP address.
    
    **Form Data**:
    - current_password: User's current password
    - new_password: New password (minimum 8 chars, must contain uppercase, lowercase, digit)
    
    **Returns**:
    - Success message
    - HTTP 200: Password changed successfully
    - HTTP 400: Invalid current password or weak new password
    - HTTP 401: Invalid or expired token
    - HTTP 429: Rate limit exceeded
    
    **Example**:
    ```
    POST /auth/change-password
    Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
    Content-Type: application/x-www-form-urlencoded
    
    current_password=OldPass123&new_password=NewSecurePass456
    ```
    """
    from app.auth.auth import verify_password
    
    # Verify current password
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Validate new password (same validation as registration)
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long"
        )
    
    if not any(c.isupper() for c in new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must contain at least one uppercase letter"
        )
    
    if not any(c.islower() for c in new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must contain at least one lowercase letter"
        )
    
    if not any(c.isdigit() for c in new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must contain at least one digit"
        )
    
    try:
        # Update password
        current_user.password_hash = get_password_hash(new_password)
        db.commit()
        
        return create_response(
            success=True,
            message="Password changed successfully"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )