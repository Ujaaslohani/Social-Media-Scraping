"""
SQLAlchemy models for the Social Media Scraping API.

This module defines database models for:
- User authentication and management
- Instagram posts storage (extends existing table)
- YouTube videos storage (extends existing table)
- API usage tracking
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class User(Base):
    """
    User model for authentication and authorization.
    
    Attributes:
        id: Primary key, auto-incremented
        username: Unique username for login
        email: User's email address (unique)
        password_hash: Bcrypt hashed password
        full_name: User's full name
        is_active: Account status flag
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    
    # Relationship to track API usage
    api_logs = relationship("APILog", back_populates="user")
    

class InstagramPost(Base):
    """
    Instagram posts model (extends existing instagram_posts table).
    
    Note: This model matches the existing table structure from insta_final.py
    to ensure compatibility with existing data.
    """
    __tablename__ = "instagram_posts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    profile = Column(String(255), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    caption = Column(Text)
    upload_date = Column(DateTime)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    is_video = Column(Boolean, default=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)


class YouTubeVideo(Base):
    """
    YouTube videos model (extends existing daily_videos table).
    
    Note: This model matches the existing table structure from youtube_id_finder.py
    to ensure compatibility with existing data.
    """
    __tablename__ = "daily_videos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(String(255), nullable=False, index=True)
    video_id = Column(String(255), nullable=False, index=True)
    published_at = Column(String(20), nullable=False)  # Stored as string to match existing format
    channel_name = Column(String(255), nullable=False)
    datetime = Column(String(50), nullable=False)  # Stored as string to match existing format


class APILog(Base):
    """
    API usage logging model for tracking user activity and rate limiting.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        endpoint: API endpoint accessed
        method: HTTP method used
        ip_address: Client IP address
        user_agent: Client user agent
        response_status: HTTP response status code
        request_time: Timestamp of the request
        execution_time: Time taken to process request (in milliseconds)
    """
    __tablename__ = "api_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for unauthenticated requests
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    response_status = Column(Integer, nullable=False)
    request_time = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    execution_time = Column(Integer)  # Milliseconds
    
    # Relationship back to user
    user = relationship("User", back_populates="api_logs")


class TwitterTweet(Base):
    """
    Twitter tweets model for storing scraped Twitter data.
    
    This model stores tweet information scraped using the twikit library
    from the existing twitter_scraping.py functionality.
    """
    __tablename__ = "twitter_tweets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tweet_id = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    full_text = Column(Text, nullable=False)
    favorite_count = Column(Integer, default=0)  # Likes
    retweet_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    quote_count = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False)  # When tweet was posted
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When we scraped it
    
    # Additional metadata
    is_retweet = Column(Boolean, default=False)
    is_reply = Column(Boolean, default=False)
    language = Column(String(10))  # Tweet language code
    source = Column(String(255))   # Tweet source (e.g., "Twitter Web App")


class ScrapingJob(Base):
    """
    Model to track scraping job requests and their status.
    
    This enables async scraping operations and job status tracking.
    """
    __tablename__ = "scraping_jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_type = Column(String(50), nullable=False)  # 'instagram', 'youtube', 'twitter', etc.
    target = Column(String(255), nullable=False)   # Profile name, channel ID, etc.
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    parameters = Column(Text)  # JSON string of job parameters
    result_count = Column(Integer, default=0)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationship to user
    user = relationship("User")