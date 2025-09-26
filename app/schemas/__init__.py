"""
Pydantic schemas for request/response validation and serialization.

This module defines data models for:
- User authentication (login, register, user info)
- API responses and error handling
- Social media scraping requests/responses
"""

from typing import Optional, List, Union, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, validator, Field


# =============================================================================
# Authentication Schemas
# =============================================================================

class UserBase(BaseModel):
    """Base user schema with common fields."""
    username: str = Field(..., min_length=3, max_length=50, description="Username (3-50 characters)")
    email: EmailStr = Field(..., description="Valid email address")
    full_name: str = Field(..., min_length=1, max_length=100, description="Full name")


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="User password")


class UserResponse(UserBase):
    """Schema for user data in responses."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # Enable ORM mode for SQLAlchemy compatibility


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TokenData(BaseModel):
    """Schema for token payload data."""
    username: Optional[str] = None


# =============================================================================
# API Response Schemas
# =============================================================================

class APIResponse(BaseModel):
    """Generic API response schema."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message")
    data: Optional[Union[dict, list, str, int]] = Field(None, description="Response data")
    errors: Optional[List[str]] = Field(None, description="List of errors if any")


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    success: bool = Field(default=False)
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[dict] = Field(None, description="Additional error details")


# =============================================================================
# Social Media Scraping Schemas
# =============================================================================

class InstagramPostBase(BaseModel):
    """Base schema for Instagram posts."""
    profile: str = Field(..., description="Instagram profile username")
    url: str = Field(..., description="Post URL")
    caption: Optional[str] = Field(None, description="Post caption")
    likes: int = Field(default=0, description="Number of likes")
    comments: int = Field(default=0, description="Number of comments")
    is_video: bool = Field(default=False, description="Whether post is a video")


class InstagramPostResponse(InstagramPostBase):
    """Schema for Instagram post responses."""
    id: int
    upload_date: Optional[datetime]
    scraped_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class InstagramScrapeRequest(BaseModel):
    """Schema for Instagram scraping requests."""
    profiles: List[str] = Field(..., min_items=1, description="List of Instagram profiles to scrape")
    max_posts: Optional[int] = Field(50, ge=1, le=200, description="Maximum posts per profile (1-200)")
    scrape_time: Optional[int] = Field(60, ge=30, le=300, description="Scraping time in seconds (30-300)")
    
    @validator('profiles')
    def validate_profiles(cls, v):
        """Validate Instagram profile names."""
        for profile in v:
            if not profile.replace('_', '').replace('.', '').isalnum():
                raise ValueError(f'Invalid Instagram profile name: {profile}')
        return v


class YouTubeVideoBase(BaseModel):
    """Base schema for YouTube videos."""
    channel_id: str = Field(..., description="YouTube channel ID")
    video_id: str = Field(..., description="YouTube video ID")
    channel_name: str = Field(..., description="YouTube channel name")
    published_at: str = Field(..., description="Video publication date")


class YouTubeVideoResponse(YouTubeVideoBase):
    """Schema for YouTube video responses."""
    id: int
    datetime: str  # Keeping as string to match existing format
    
    class Config:
        from_attributes = True


class YouTubeScrapeRequest(BaseModel):
    """Schema for YouTube scraping requests."""
    channels: List[str] = Field(..., min_items=1, description="List of YouTube channel IDs or names")
    days_back: Optional[int] = Field(7, ge=1, le=30, description="Number of days to look back (1-30)")
    max_results: Optional[int] = Field(50, ge=1, le=100, description="Maximum results per channel (1-100)")


# =============================================================================
# Twitter Schemas
# =============================================================================

class TwitterTweetBase(BaseModel):
    """Base schema for Twitter tweets."""
    tweet_id: str = Field(..., description="Twitter tweet ID")
    username: str = Field(..., description="Twitter username")
    user_id: str = Field(..., description="Twitter user ID")
    full_text: str = Field(..., description="Tweet text content")
    favorite_count: int = Field(default=0, description="Number of likes")
    retweet_count: int = Field(default=0, description="Number of retweets")
    reply_count: int = Field(default=0, description="Number of replies")
    quote_count: int = Field(default=0, description="Number of quote tweets")


class TwitterTweetResponse(TwitterTweetBase):
    """Schema for Twitter tweet responses."""
    id: int
    created_at: datetime = Field(..., description="When tweet was posted")
    scraped_at: datetime = Field(..., description="When tweet was scraped")
    is_retweet: bool = Field(default=False, description="Whether tweet is a retweet")
    is_reply: bool = Field(default=False, description="Whether tweet is a reply")
    language: Optional[str] = Field(None, description="Tweet language code")
    source: Optional[str] = Field(None, description="Tweet source")
    
    class Config:
        from_attributes = True


class TwitterScrapeRequest(BaseModel):
    """Schema for Twitter scraping requests."""
    usernames: List[str] = Field(..., min_items=1, description="List of Twitter usernames to scrape")
    tweet_count: Optional[int] = Field(20, ge=1, le=200, description="Number of tweets per user (1-200)")
    include_retweets: Optional[bool] = Field(True, description="Include retweets in results")
    include_replies: Optional[bool] = Field(False, description="Include replies in results")
    
    @validator('usernames')
    def validate_usernames(cls, v):
        """Validate Twitter usernames."""
        for username in v:
            # Remove @ if present
            clean_username = username.lstrip('@')
            if not clean_username.replace('_', '').isalnum():
                raise ValueError(f'Invalid Twitter username: {username}')
            if len(clean_username) > 15:  # Twitter username max length
                raise ValueError(f'Twitter username too long: {username}')
        return [username.lstrip('@') for username in v]  # Remove @ symbols


# =============================================================================
# Job Management Schemas
# =============================================================================

class ScrapingJobBase(BaseModel):
    """Base schema for scraping jobs."""
    job_type: str = Field(..., description="Type of scraping job (instagram, youtube)")
    target: str = Field(..., description="Target profile/channel")
    parameters: Optional[dict] = Field(None, description="Job parameters")


class ScrapingJobCreate(ScrapingJobBase):
    """Schema for creating scraping jobs."""
    pass


class ScrapingJobResponse(ScrapingJobBase):
    """Schema for scraping job responses."""
    id: int
    user_id: int
    status: str = Field(..., description="Job status (pending, running, completed, failed)")
    result_count: int = Field(default=0, description="Number of results scraped")
    error_message: Optional[str] = Field(None, description="Error message if job failed")
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# =============================================================================
# Metrics and Analytics Schemas
# =============================================================================

class MetricsResponse(BaseModel):
    """Schema for metrics API responses."""
    platform: str = Field(..., description="Social media platform")
    total_posts: int = Field(..., description="Total posts scraped")
    total_profiles: int = Field(..., description="Total profiles tracked")
    date_range: dict = Field(..., description="Date range of data")
    top_profiles: List[dict] = Field(..., description="Top performing profiles")
    engagement_stats: dict = Field(..., description="Engagement statistics")


class HealthResponse(BaseModel):
    """Schema for health check responses."""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="API version")
    database: bool = Field(..., description="Database connectivity status")
    environment: str = Field(..., description="Environment (development, production)")


# =============================================================================
# Pagination Schemas
# =============================================================================

class PaginationParams(BaseModel):
    """Schema for pagination parameters."""
    page: int = Field(default=1, ge=1, description="Page number (starts from 1)")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page (1-100)")


class PaginatedResponse(BaseModel):
    """Schema for paginated responses."""
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")