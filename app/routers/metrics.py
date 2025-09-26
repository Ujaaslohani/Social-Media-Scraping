"""
Metrics router for social media analytics and data insights.

This module provides endpoints for:
- YouTube channel metrics and analytics
- Instagram profile statistics
- Data aggregation and insights
- Protected routes requiring authentication
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, ScrapingJob
from app.schemas import (
    MetricsResponse, APIResponse, YouTubeScrapeRequest,
    InstagramScrapeRequest, PaginationParams, PaginatedResponse,
    TwitterScrapeRequest
)
from app.auth.auth import get_current_active_user
from app.services import InstagramScrapingService, YouTubeScrapingService, JobService, TwitterScrapingService
from app.utils.helpers import create_response, limiter, paginate_query

# Create router with prefix and tags
router = APIRouter(prefix="/metrics", tags=["Metrics & Analytics"])


@router.get("/youtube", response_model=MetricsResponse)
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute per IP
async def get_youtube_metrics(
    request: Request,
    channel_name: Optional[str] = Query(None, description="Filter by specific channel name"),
    days_back: int = Query(30, ge=1, le=365, description="Number of days to analyze (1-365)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> MetricsResponse:
    """
    Get YouTube channel metrics and analytics data.
    
    **Authentication Required**: Bearer token in Authorization header.
    **Rate Limited**: 30 requests per minute per IP address.
    
    This endpoint integrates with your existing YouTube scraping data to provide
    comprehensive analytics about channel performance and video publishing patterns.
    
    **Query Parameters**:
    - channel_name: Filter results for specific channel (optional)
    - days_back: Number of days to analyze (default: 30, max: 365)
    
    **Returns**:
    - Comprehensive YouTube metrics including:
      - Total videos scraped
      - Channel activity patterns
      - Publishing frequency analysis
      - Top performing channels
    
    **Example**:
    ```
    GET /metrics/youtube?channel_name=Aaj%20Tak&days_back=7
    Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
    ```
    
    **Response**:
    ```json
    {
        "platform": "youtube",
        "total_posts": 150,
        "total_profiles": 5,
        "date_range": {
            "start_date": "2024-01-01",
            "end_date": "2024-01-30",
            "days": 30
        },
        "top_profiles": [
            {
                "channel_name": "Aaj Tak",
                "video_count": 45,
                "avg_videos_per_day": 1.5
            }
        ],
        "engagement_stats": {
            "total_channels_tracked": 5,
            "most_active_channel": "Aaj Tak",
            "publishing_patterns": {...}
        }
    }
    ```
    """
    youtube_service = YouTubeScrapingService(db)
    
    if channel_name:
        # Get metrics for specific channel
        channel_metrics = youtube_service.get_channel_metrics(channel_name, days_back)
        
        if "error" in channel_metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for channel: {channel_name}"
            )
        
        # Get recent videos for the channel
        recent_videos = youtube_service.get_videos(
            channel_name=channel_name,
            days_back=days_back,
            limit=100
        )
        
        return MetricsResponse(
            platform="youtube",
            total_posts=len(recent_videos),
            total_profiles=1,
            date_range={
                "channel": channel_name,
                "days_analyzed": days_back,
                "total_videos": channel_metrics["total_videos"]
            },
            top_profiles=[{
                "channel_name": channel_name,
                "video_count": channel_metrics["total_videos"],
                "avg_videos_per_day": channel_metrics["average_videos_per_day"],
                "videos_by_date": channel_metrics["videos_by_date"]
            }],
            engagement_stats={
                "channel_analysis": channel_metrics,
                "most_active_day": channel_metrics.get("most_active_day"),
                "publishing_consistency": "high" if channel_metrics["average_videos_per_day"] >= 1 else "low"
            }
        )
    
    else:
        # Get overall YouTube metrics across all channels
        all_videos = youtube_service.get_videos(days_back=days_back, limit=1000)
        
        # Aggregate metrics by channel
        channel_stats = {}
        for video in all_videos:
            channel = video.channel_name
            if channel not in channel_stats:
                channel_stats[channel] = {
                    "video_count": 0,
                    "videos": []
                }
            channel_stats[channel]["video_count"] += 1
            channel_stats[channel]["videos"].append(video)
        
        # Calculate top performing channels
        top_channels = sorted(
            [
                {
                    "channel_name": channel,
                    "video_count": stats["video_count"],
                    "avg_videos_per_day": round(stats["video_count"] / days_back, 2)
                }
                for channel, stats in channel_stats.items()
            ],
            key=lambda x: x["video_count"],
            reverse=True
        )[:10]  # Top 10 channels
        
        return MetricsResponse(
            platform="youtube",
            total_posts=len(all_videos),
            total_profiles=len(channel_stats),
            date_range={
                "days_analyzed": days_back,
                "total_channels": len(channel_stats),
                "date_range": f"Last {days_back} days"
            },
            top_profiles=top_channels,
            engagement_stats={
                "total_channels_tracked": len(channel_stats),
                "most_active_channel": top_channels[0]["channel_name"] if top_channels else None,
                "average_videos_per_channel": round(len(all_videos) / len(channel_stats), 2) if channel_stats else 0,
                "channel_breakdown": {
                    channel: stats["video_count"] 
                    for channel, stats in channel_stats.items()
                }
            }
        )


@router.get("/instagram", response_model=MetricsResponse)
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute per IP
async def get_instagram_metrics(
    request: Request,
    profile: Optional[str] = Query(None, description="Filter by specific Instagram profile"),
    days_back: int = Query(30, ge=1, le=365, description="Number of days to analyze (1-365)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> MetricsResponse:
    """
    Get Instagram profile metrics and analytics data.
    
    **Authentication Required**: Bearer token in Authorization header.
    **Rate Limited**: 30 requests per minute per IP address.
    
    This endpoint provides comprehensive analytics about Instagram profiles
    based on your scraped data, including engagement rates and posting patterns.
    
    **Query Parameters**:
    - profile: Filter results for specific Instagram profile (optional)
    - days_back: Number of days to analyze (default: 30, max: 365)
    
    **Returns**:
    - Comprehensive Instagram metrics including:
      - Total posts scraped
      - Engagement statistics (likes, comments)
      - Profile performance comparison
      - Content type analysis (photos vs videos)
    
    **Example**:
    ```
    GET /metrics/instagram?profile=example_profile&days_back=7
    Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
    ```
    """
    instagram_service = InstagramScrapingService(db)
    
    if profile:
        # Get metrics for specific profile
        profile_stats = instagram_service.get_profile_stats(profile)
        
        if "error" in profile_stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for profile: @{profile}"
            )
        
        # Get recent posts for the profile
        recent_posts = instagram_service.get_posts(profile=profile, limit=100)
        
        return MetricsResponse(
            platform="instagram",
            total_posts=profile_stats["total_posts"],
            total_profiles=1,
            date_range={
                "profile": f"@{profile}",
                "days_analyzed": days_back,
                "total_posts": profile_stats["total_posts"]
            },
            top_profiles=[{
                "profile_name": f"@{profile}",
                "post_count": profile_stats["total_posts"],
                "total_likes": profile_stats["total_likes"],
                "total_comments": profile_stats["total_comments"],
                "engagement_rate": profile_stats["engagement_rate"]
            }],
            engagement_stats={
                "profile_analysis": profile_stats,
                "average_likes_per_post": profile_stats["average_likes"],
                "average_comments_per_post": profile_stats["average_comments"],
                "video_content_percentage": profile_stats["video_percentage"]
            }
        )
    
    else:
        # Get overall Instagram metrics across all profiles
        all_posts = instagram_service.get_posts(limit=1000)
        
        # Aggregate metrics by profile
        profile_stats = {}
        for post in all_posts:
            profile_name = post.profile
            if profile_name not in profile_stats:
                profile_stats[profile_name] = {
                    "post_count": 0,
                    "total_likes": 0,
                    "total_comments": 0,
                    "video_count": 0
                }
            
            stats = profile_stats[profile_name]
            stats["post_count"] += 1
            stats["total_likes"] += post.likes or 0
            stats["total_comments"] += post.comments or 0
            if post.is_video:
                stats["video_count"] += 1
        
        # Calculate top performing profiles by engagement
        top_profiles = []
        for profile_name, stats in profile_stats.items():
            engagement_rate = (stats["total_likes"] + stats["total_comments"]) / stats["post_count"] if stats["post_count"] > 0 else 0
            top_profiles.append({
                "profile_name": f"@{profile_name}",
                "post_count": stats["post_count"],
                "total_likes": stats["total_likes"],
                "total_comments": stats["total_comments"],
                "engagement_rate": round(engagement_rate, 2)
            })
        
        top_profiles.sort(key=lambda x: x["engagement_rate"], reverse=True)
        top_profiles = top_profiles[:10]  # Top 10 profiles
        
        return MetricsResponse(
            platform="instagram",
            total_posts=len(all_posts),
            total_profiles=len(profile_stats),
            date_range={
                "days_analyzed": days_back,
                "total_profiles": len(profile_stats),
                "date_range": f"Last {days_back} days"
            },
            top_profiles=top_profiles,
            engagement_stats={
                "total_profiles_tracked": len(profile_stats),
                "highest_engagement_profile": top_profiles[0]["profile_name"] if top_profiles else None,
                "total_engagement": sum(p["total_likes"] + p["total_comments"] for p in top_profiles),
                "profile_breakdown": {
                    f"@{profile}": stats["post_count"] 
                    for profile, stats in profile_stats.items()
                }
            }
        )


@router.post("/scrape/youtube", response_model=APIResponse)
@limiter.limit("10/hour")  # Rate limit: 10 scraping jobs per hour per user
async def start_youtube_scraping(
    scrape_request: YouTubeScrapeRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start a YouTube channel scraping job.
    
    **Authentication Required**: Bearer token in Authorization header.
    **Rate Limited**: 10 scraping jobs per hour per IP address.
    
    This endpoint initiates background scraping of YouTube channels using your
    existing youtube_id_finder.py functionality. The job runs asynchronously
    and you can check its status using the job management endpoints.
    
    **Request Body**:
    - channels: List of YouTube channel IDs or names to scrape
    - days_back: Number of days to look back for videos (default: 7)
    - max_results: Maximum videos per channel (default: 50, max: 100)
    
    **Returns**:
    - Job information including job ID for status tracking
    - HTTP 202: Scraping job started successfully
    - HTTP 400: Invalid request parameters
    - HTTP 429: Rate limit exceeded
    
    **Example**:
    ```json
    {
        "channels": ["UCt4t-jeY85JegMlZ-E5UWtA", "UCmphdqZNmqL72WJ2uyiNw5w"],
        "days_back": 7,
        "max_results": 50
    }
    ```
    """
    youtube_service = YouTubeScrapingService(db)
    
    try:
        result = await youtube_service.scrape_channels(scrape_request, current_user)
        
        return create_response(
            success=True,
            message="YouTube scraping job started successfully",
            data=result,
            status_code=status.HTTP_202_ACCEPTED
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start YouTube scraping job"
        )


@router.post("/scrape/instagram", response_model=APIResponse)
@limiter.limit("5/hour")  # Rate limit: 5 scraping jobs per hour per user  
async def start_instagram_scraping(
    scrape_request: InstagramScrapeRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start an Instagram profile scraping job.
    
    **Authentication Required**: Bearer token in Authorization header.
    **Rate Limited**: 5 scraping jobs per hour per IP address.
    
    This endpoint initiates background scraping of Instagram profiles using your
    existing insta_final.py functionality. The job runs asynchronously due to
    the complex nature of Instagram scraping (Selenium + Instaloader).
    
    **Request Body**:
    - profiles: List of Instagram usernames to scrape (without @)
    - max_posts: Maximum posts per profile (default: 50, max: 200)
    - scrape_time: Time limit for link collection in seconds (default: 60, max: 300)
    
    **Returns**:
    - Job information including job ID for status tracking
    - HTTP 202: Scraping job started successfully
    - HTTP 400: Invalid request parameters or profile names
    - HTTP 429: Rate limit exceeded
    
    **Example**:
    ```json
    {
        "profiles": ["instagram", "natgeo", "nasa"],
        "max_posts": 100,
        "scrape_time": 120
    }
    ```
    
    **Note**: Instagram scraping is more resource-intensive and has stricter
    rate limits due to the need for browser automation and API compliance.
    """
    instagram_service = InstagramScrapingService(db)
    
    try:
        result = await instagram_service.scrape_profiles(scrape_request, current_user)
        
        return create_response(
            success=True,
            message="Instagram scraping job started successfully",
            data=result,
            status_code=status.HTTP_202_ACCEPTED
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start Instagram scraping job"
        )


@router.get("/twitter", response_model=MetricsResponse)
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute per IP
async def get_twitter_metrics(
    request: Request,
    username: Optional[str] = Query(None, description="Filter by specific Twitter username"),
    days_back: int = Query(30, ge=1, le=365, description="Number of days to analyze (1-365)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> MetricsResponse:
    """
    Get Twitter user metrics and analytics data.
    
    **Authentication Required**: Bearer token in Authorization header.
    **Rate Limited**: 30 requests per minute per IP address.
    
    This endpoint integrates with your existing Twitter scraping data using twikit
    to provide comprehensive analytics about Twitter user performance and engagement.
    
    **Query Parameters**:
    - username: Filter results for specific Twitter user (optional, without @)
    - days_back: Number of days to analyze (default: 30, max: 365)
    
    **Returns**:
    - Comprehensive Twitter metrics including:
      - Total tweets scraped
      - Engagement statistics (likes, retweets, replies, quotes)
      - Content breakdown (original vs retweets vs replies)
      - Activity patterns and top performing tweets
    
    **Example**:
    ```
    GET /metrics/twitter?username=elonmusk&days_back=7
    Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
    ```
    
    **Response**:
    ```json
    {
        "platform": "twitter",
        "total_posts": 150,
        "total_profiles": 5,
        "date_range": {
            "start_date": "2024-01-01",
            "end_date": "2024-01-30",
            "days": 30
        },
        "top_profiles": [
            {
                "username": "@elonmusk",
                "tweet_count": 45,
                "total_engagement": 1500000,
                "avg_engagement_per_tweet": 33333
            }
        ],
        "engagement_stats": {
            "total_likes": 800000,
            "total_retweets": 400000,
            "total_replies": 200000,
            "total_quotes": 100000,
            "engagement_breakdown": {...}
        }
    }
    ```
    """
    twitter_service = TwitterScrapingService(db)
    
    if username:
        # Get metrics for specific user
        user_stats = twitter_service.get_user_stats(username, days_back)
        
        if "error" in user_stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for Twitter user: @{username}"
            )
        
        # Get recent tweets for the user
        recent_tweets = twitter_service.get_tweets(
            username=username,
            days_back=days_back,
            limit=1000
        )
        
        return MetricsResponse(
            platform="twitter",
            total_posts=len(recent_tweets),
            total_profiles=1,
            date_range={
                "username": user_stats["username"],
                "days_analyzed": days_back,
                "total_tweets": user_stats["total_tweets"]
            },
            top_profiles=[{
                "username": user_stats["username"],
                "tweet_count": user_stats["total_tweets"],
                "total_engagement": user_stats["engagement_metrics"]["total_engagement"],
                "avg_engagement_per_tweet": user_stats["engagement_metrics"]["avg_engagement_per_tweet"],
                "tweets_per_day": user_stats["activity_metrics"]["tweets_per_day"]
            }],
            engagement_stats={
                "user_analysis": user_stats["engagement_metrics"],
                "content_breakdown": user_stats["content_breakdown"],
                "activity_metrics": user_stats["activity_metrics"],
                "engagement_rate": "high" if user_stats["engagement_metrics"]["avg_engagement_per_tweet"] >= 100 else "moderate" if user_stats["engagement_metrics"]["avg_engagement_per_tweet"] >= 10 else "low"
            }
        )
    
    else:
        # Get overall Twitter metrics across all users
        all_tweets = twitter_service.get_tweets(days_back=days_back, limit=10000)
        
        # Aggregate metrics by user
        user_stats = {}
        for tweet in all_tweets:
            username = tweet.username
            if username not in user_stats:
                user_stats[username] = {
                    "tweet_count": 0,
                    "total_likes": 0,
                    "total_retweets": 0,
                    "total_replies": 0,
                    "total_quotes": 0,
                    "tweets": []
                }
            
            stats = user_stats[username]
            stats["tweet_count"] += 1
            stats["total_likes"] += tweet.favorite_count or 0
            stats["total_retweets"] += tweet.retweet_count or 0
            stats["total_replies"] += tweet.reply_count or 0
            stats["total_quotes"] += tweet.quote_count or 0
            stats["tweets"].append(tweet)
        
        # Calculate top performing users by total engagement
        top_users = []
        for username, stats in user_stats.items():
            total_engagement = stats["total_likes"] + stats["total_retweets"] + stats["total_replies"] + stats["total_quotes"]
            avg_engagement = total_engagement / stats["tweet_count"] if stats["tweet_count"] > 0 else 0
            
            top_users.append({
                "username": f"@{username}",
                "tweet_count": stats["tweet_count"],
                "total_engagement": total_engagement,
                "avg_engagement_per_tweet": round(avg_engagement, 2),
                "tweets_per_day": round(stats["tweet_count"] / days_back, 2)
            })
        
        top_users.sort(key=lambda x: x["total_engagement"], reverse=True)
        top_users = top_users[:10]  # Top 10 users
        
        # Calculate overall statistics
        total_engagement = sum(u["total_engagement"] for u in top_users)
        total_likes = sum(stats["total_likes"] for stats in user_stats.values())
        total_retweets = sum(stats["total_retweets"] for stats in user_stats.values())
        total_replies = sum(stats["total_replies"] for stats in user_stats.values())
        total_quotes = sum(stats["total_quotes"] for stats in user_stats.values())
        
        return MetricsResponse(
            platform="twitter",
            total_posts=len(all_tweets),
            total_profiles=len(user_stats),
            date_range={
                "days_analyzed": days_back,
                "total_users": len(user_stats),
                "date_range": f"Last {days_back} days"
            },
            top_profiles=top_users,
            engagement_stats={
                "total_users_tracked": len(user_stats),
                "highest_engagement_user": top_users[0]["username"] if top_users else None,
                "platform_totals": {
                    "total_likes": total_likes,
                    "total_retweets": total_retweets,
                    "total_replies": total_replies,
                    "total_quotes": total_quotes,
                    "total_engagement": total_engagement
                },
                "average_engagement_per_user": round(total_engagement / len(user_stats), 2) if user_stats else 0,
                "user_breakdown": {
                    f"@{username}": stats["tweet_count"] 
                    for username, stats in user_stats.items()
                }
            }
        )


@router.post("/scrape/twitter", response_model=APIResponse)
@limiter.limit("5/hour")  # Rate limit: 5 scraping jobs per hour per user
async def start_twitter_scraping(
    scrape_request: TwitterScrapeRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start a Twitter user scraping job.
    
    **Authentication Required**: Bearer token in Authorization header.
    **Rate Limited**: 5 scraping jobs per hour per IP address.
    
    This endpoint initiates background scraping of Twitter users using your
    existing twitter_scraping.py functionality with twikit library. The job runs
    asynchronously due to Twitter's API limitations and rate limiting requirements.
    
    **Request Body**:
    - usernames: List of Twitter usernames to scrape (without @ symbol)
    - tweet_count: Number of tweets per user (default: 20, max: 200)
    - include_retweets: Include retweets in results (default: true)
    - include_replies: Include reply tweets in results (default: false)
    
    **Returns**:
    - Job information including job ID for status tracking
    - HTTP 202: Scraping job started successfully
    - HTTP 400: Invalid request parameters or Twitter credentials not configured
    - HTTP 429: Rate limit exceeded
    
    **Example**:
    ```json
    {
        "usernames": ["elonmusk", "twitter", "openai"],
        "tweet_count": 50,
        "include_retweets": true,
        "include_replies": false
    }
    ```
    
    **Important Notes**:
    - Twitter scraping requires valid Twitter credentials in environment variables
    - Rate limiting is strict due to Twitter's API policies
    - Jobs may take several minutes to complete due to API rate limits
    - Cookies are cached for subsequent requests to avoid repeated logins
    
    **Environment Variables Required**:
    - TWITTER_USERNAME: Your Twitter username
    - TWITTER_EMAIL: Your Twitter email
    - TWITTER_PASSWORD: Your Twitter password
    """
    twitter_service = TwitterScrapingService(db)
    
    try:
        result = await twitter_service.scrape_tweets(scrape_request, current_user)
        
        return create_response(
            success=True,
            message="Twitter scraping job started successfully",
            data=result,
            status_code=status.HTTP_202_ACCEPTED
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start Twitter scraping job"
        )


@router.get("/jobs", response_model=PaginatedResponse)
async def get_user_jobs(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(20, ge=1, le=50, description="Items per page (1-50)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get user's scraping jobs with pagination.
    
    **Authentication Required**: Bearer token in Authorization header.
    
    **Query Parameters**:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20, max: 50)
    
    **Returns**:
    - Paginated list of user's scraping jobs
    - Job status, results, and execution details
    
    **Example**:
    ```
    GET /metrics/jobs?page=1&per_page=10
    Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
    ```
    """
    job_service = JobService(db)
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get user jobs
    jobs = job_service.get_user_jobs(current_user, limit=per_page, offset=offset)
    
    # Get total count for pagination
    from sqlalchemy import func
    total_jobs = db.query(func.count(ScrapingJob.id)).filter(
        ScrapingJob.user_id == current_user.id
    ).scalar()
    
    # Calculate pagination info
    total_pages = (total_jobs + per_page - 1) // per_page
    has_next = page < total_pages
    has_prev = page > 1
    
    return {
        "items": [
            {
                "id": job.id,
                "job_type": job.job_type,
                "target": job.target,
                "status": job.status,
                "result_count": job.result_count,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error_message": job.error_message
            }
            for job in jobs
        ],
        "total": total_jobs,
        "page": page,
        "per_page": per_page,
        "pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev
    }


@router.get("/jobs/{job_id}", response_model=APIResponse)
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed status of a specific scraping job.
    
    **Authentication Required**: Bearer token in Authorization header.
    
    **Path Parameters**:
    - job_id: ID of the scraping job to check
    
    **Returns**:
    - Detailed job information including status, results, and execution time
    - HTTP 200: Job found and details returned
    - HTTP 404: Job not found or not accessible by user
    
    **Example**:
    ```
    GET /metrics/jobs/123
    Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
    ```
    """
    job_service = JobService(db)
    
    job = job_service.get_job_status(job_id, current_user)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or access denied"
        )
    
    # Calculate execution time if applicable
    execution_time = None
    if job.started_at and job.completed_at:
        execution_time = (job.completed_at - job.started_at).total_seconds()
    
    return create_response(
        success=True,
        message="Job status retrieved successfully",
        data={
            "job_id": job.id,
            "job_type": job.job_type,
            "target": job.target,
            "status": job.status,
            "parameters": job.parameters,
            "result_count": job.result_count,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "execution_time_seconds": execution_time
        }
    )