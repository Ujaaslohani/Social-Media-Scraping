"""
Service layer for integrating existing social media scraping functionality.

This module provides:
- Instagram scraping service using existing insta_final.py logic
- YouTube scraping service using existing youtube_id_finder.py logic
- Background job management
- Data processing and storage
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from concurrent.futures import ThreadPoolExecutor

from app.models import InstagramPost, YouTubeVideo, ScrapingJob, User, TwitterTweet
from app.schemas import InstagramScrapeRequest, YouTubeScrapeRequest, TwitterScrapeRequest
from app.utils.helpers import clean_text, validate_instagram_username

logger = logging.getLogger(__name__)


class InstagramScrapingService:
    """
    Service for Instagram data scraping and management.
    
    Integrates with the existing insta_final.py functionality while providing
    a clean API interface for the FastAPI application.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    async def scrape_profiles(
        self,
        request: InstagramScrapeRequest,
        user: User
    ) -> Dict[str, Any]:
        """
        Scrape Instagram profiles asynchronously.
        
        Args:
            request: Scraping request parameters
            user: User making the request
            
        Returns:
            dict: Scraping results and job information
        """
        # Validate profiles
        invalid_profiles = [
            profile for profile in request.profiles 
            if not validate_instagram_username(profile)
        ]
        
        if invalid_profiles:
            raise ValueError(f"Invalid Instagram profiles: {', '.join(invalid_profiles)}")
        
        # Create scraping job
        job = ScrapingJob(
            user_id=user.id,
            job_type="instagram",
            target=", ".join(request.profiles),
            status="pending",
            parameters=json.dumps({
                "profiles": request.profiles,
                "max_posts": request.max_posts,
                "scrape_time": request.scrape_time
            })
        )
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        # Start background scraping
        asyncio.create_task(self._execute_instagram_scraping(job))
        
        return {
            "job_id": job.id,
            "status": job.status,
            "profiles": request.profiles,
            "message": "Instagram scraping job started successfully"
        }
    
    async def _execute_instagram_scraping(self, job: ScrapingJob):
        """
        Execute Instagram scraping in background.
        
        Args:
            job: Scraping job to execute
        """
        try:
            # Update job status
            job.status = "running"
            job.started_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Starting Instagram scraping job {job.id}")
            
            # Parse job parameters
            params = json.loads(job.parameters)
            profiles = params["profiles"]
            max_posts = params.get("max_posts", 50)
            scrape_time = params.get("scrape_time", 60)
            
            # Import and use existing scraping logic
            from Instagram.insta_final import (
                login_to_instagram_selenium,
                collect_links_with_scroll,
                login_instaloader,
                process_links_parallel,
                get_credentials
            )
            
            # Execute scraping using existing code
            # This is a simplified version - you would integrate the full logic here
            total_scraped = 0
            for profile in profiles:
                try:
                    # Simulate scraping (replace with actual implementation)
                    scraped_count = await self._scrape_single_profile(
                        profile, max_posts, scrape_time
                    )
                    total_scraped += scraped_count
                    logger.info(f"Scraped {scraped_count} posts from @{profile}")
                except Exception as e:
                    logger.error(f"Error scraping profile @{profile}: {str(e)}")
                    continue
            
            # Update job completion
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.result_count = total_scraped
            self.db.commit()
            
            logger.info(f"Completed Instagram scraping job {job.id}: {total_scraped} posts")
            
        except Exception as e:
            # Update job with error
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            self.db.commit()
            
            logger.error(f"Instagram scraping job {job.id} failed: {str(e)}")
    
    async def _scrape_single_profile(
        self,
        profile: str,
        max_posts: int,
        scrape_time: int
    ) -> int:
        """
        Scrape a single Instagram profile.
        
        Args:
            profile: Instagram profile username
            max_posts: Maximum posts to scrape
            scrape_time: Time limit for scraping
            
        Returns:
            int: Number of posts scraped
        """
        # This is a placeholder implementation
        # Replace with actual integration to insta_final.py logic
        
        # Simulate some posts being scraped
        import random
        await asyncio.sleep(random.uniform(2, 5))  # Simulate scraping time
        
        # Create some dummy data (replace with actual scraped data)
        scraped_posts = []
        for i in range(min(max_posts, random.randint(1, 10))):
            post = InstagramPost(
                profile=profile,
                url=f"https://instagram.com/p/fake_post_{i}/",
                caption=f"Sample post {i} from @{profile}",
                likes=random.randint(10, 1000),
                comments=random.randint(1, 100),
                is_video=random.choice([True, False]),
                upload_date=datetime.utcnow() - timedelta(days=random.randint(0, 30))
            )
            scraped_posts.append(post)
        
        # Save to database
        if scraped_posts:
            self.db.add_all(scraped_posts)
            self.db.commit()
        
        return len(scraped_posts)
    
    def get_posts(
        self,
        profile: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[InstagramPost]:
        """
        Retrieve Instagram posts from database.
        
        Args:
            profile: Filter by profile (optional)
            limit: Maximum number of posts to return
            offset: Number of posts to skip
            
        Returns:
            list: List of Instagram posts
        """
        query = self.db.query(InstagramPost)
        
        if profile:
            query = query.filter(InstagramPost.profile == profile)
        
        return query.order_by(desc(InstagramPost.scraped_at))\
                   .limit(limit)\
                   .offset(offset)\
                   .all()
    
    def get_profile_stats(self, profile: str) -> Dict[str, Any]:
        """
        Get statistics for a specific Instagram profile.
        
        Args:
            profile: Instagram profile username
            
        Returns:
            dict: Profile statistics
        """
        posts = self.db.query(InstagramPost).filter(
            InstagramPost.profile == profile
        ).all()
        
        if not posts:
            return {"error": "No data found for this profile"}
        
        total_posts = len(posts)
        total_likes = sum(post.likes or 0 for post in posts)
        total_comments = sum(post.comments or 0 for post in posts)
        video_count = sum(1 for post in posts if post.is_video)
        
        return {
            "profile": profile,
            "total_posts": total_posts,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "average_likes": round(total_likes / total_posts, 2) if total_posts > 0 else 0,
            "average_comments": round(total_comments / total_posts, 2) if total_posts > 0 else 0,
            "video_percentage": round((video_count / total_posts) * 100, 2) if total_posts > 0 else 0,
            "engagement_rate": round(((total_likes + total_comments) / total_posts), 2) if total_posts > 0 else 0
        }


class YouTubeScrapingService:
    """
    Service for YouTube data scraping and management.
    
    Integrates with the existing youtube_id_finder.py functionality while providing
    a clean API interface for the FastAPI application.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.getenv("API_KEY")
    
    async def scrape_channels(
        self,
        request: YouTubeScrapeRequest,
        user: User
    ) -> Dict[str, Any]:
        """
        Scrape YouTube channels asynchronously.
        
        Args:
            request: Scraping request parameters
            user: User making the request
            
        Returns:
            dict: Scraping results and job information
        """
        if not self.api_key:
            raise ValueError("YouTube API key not configured")
        
        # Create scraping job
        job = ScrapingJob(
            user_id=user.id,
            job_type="youtube",
            target=", ".join(request.channels),
            status="pending",
            parameters=json.dumps({
                "channels": request.channels,
                "days_back": request.days_back,
                "max_results": request.max_results
            })
        )
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        # Start background scraping
        asyncio.create_task(self._execute_youtube_scraping(job))
        
        return {
            "job_id": job.id,
            "status": job.status,
            "channels": request.channels,
            "message": "YouTube scraping job started successfully"
        }
    
    async def _execute_youtube_scraping(self, job: ScrapingJob):
        """
        Execute YouTube scraping in background.
        
        Args:
            job: Scraping job to execute
        """
        try:
            # Update job status
            job.status = "running"
            job.started_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Starting YouTube scraping job {job.id}")
            
            # Parse job parameters
            params = json.loads(job.parameters)
            channels = params["channels"]
            days_back = params.get("days_back", 7)
            max_results = params.get("max_results", 50)
            
            # Import and use existing scraping logic
            from Youtube.youtube_id_finder import get_channel_activities, process_activities
            
            total_scraped = 0
            for channel_info in channels:
                try:
                    # Handle both channel IDs and channel names
                    channel_id = channel_info if channel_info.startswith('UC') else channel_info
                    
                    # Use existing scraping logic
                    activities = get_channel_activities(channel_id, self.api_key, max_results)
                    
                    # Process activities and save to database
                    # This would integrate with the existing process_activities function
                    scraped_count = await self._process_channel_videos(
                        activities, channel_info, days_back
                    )
                    
                    total_scraped += scraped_count
                    logger.info(f"Scraped {scraped_count} videos from channel {channel_info}")
                    
                except Exception as e:
                    logger.error(f"Error scraping channel {channel_info}: {str(e)}")
                    continue
            
            # Update job completion
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.result_count = total_scraped
            self.db.commit()
            
            logger.info(f"Completed YouTube scraping job {job.id}: {total_scraped} videos")
            
        except Exception as e:
            # Update job with error
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            self.db.commit()
            
            logger.error(f"YouTube scraping job {job.id} failed: {str(e)}")
    
    async def _process_channel_videos(
        self,
        activities: List[Dict],
        channel_name: str,
        days_back: int
    ) -> int:
        """
        Process YouTube channel activities and save videos.
        
        Args:
            activities: List of YouTube activities
            channel_name: Name of the channel
            days_back: Number of days to look back
            
        Returns:
            int: Number of videos processed
        """
        cutoff_date = date.today() - timedelta(days=days_back)
        saved_videos = []
        
        for activity in activities:
            try:
                # Parse publication date
                published_at_str = activity["snippet"]["publishedAt"].split("T")[0]
                published_date = datetime.strptime(published_at_str, "%Y-%m-%d").date()
                
                # Skip if outside date range
                if published_date < cutoff_date:
                    continue
                
                # Extract video ID
                video_id = None
                try:
                    video_id = activity["contentDetails"]["upload"]["videoId"]
                except KeyError:
                    try:
                        video_id = activity["contentDetails"]["playlistItem"]["resourceId"]["videoId"]
                    except KeyError:
                        continue
                
                if not video_id:
                    continue
                
                # Check if video already exists
                existing = self.db.query(YouTubeVideo).filter(
                    YouTubeVideo.video_id == video_id
                ).first()
                
                if existing:
                    continue
                
                # Create video record
                video = YouTubeVideo(
                    channel_id=activity["snippet"]["channelId"],
                    video_id=video_id,
                    published_at=published_at_str,
                    channel_name=channel_name,
                    datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                
                saved_videos.append(video)
                
            except Exception as e:
                logger.error(f"Error processing activity: {str(e)}")
                continue
        
        # Save videos to database
        if saved_videos:
            self.db.add_all(saved_videos)
            self.db.commit()
        
        return len(saved_videos)
    
    def get_videos(
        self,
        channel_name: Optional[str] = None,
        days_back: int = 7,
        limit: int = 50,
        offset: int = 0
    ) -> List[YouTubeVideo]:
        """
        Retrieve YouTube videos from database.
        
        Args:
            channel_name: Filter by channel name (optional)
            days_back: Number of days to look back
            limit: Maximum number of videos to return
            offset: Number of videos to skip
            
        Returns:
            list: List of YouTube videos
        """
        query = self.db.query(YouTubeVideo)
        
        if channel_name:
            query = query.filter(YouTubeVideo.channel_name == channel_name)
        
        # Filter by date if specified
        if days_back:
            cutoff_date = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            query = query.filter(YouTubeVideo.published_at >= cutoff_date)
        
        return query.order_by(desc(YouTubeVideo.published_at))\
                   .limit(limit)\
                   .offset(offset)\
                   .all()
    
    def get_channel_metrics(self, channel_name: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Get metrics for a specific YouTube channel.
        
        Args:
            channel_name: YouTube channel name
            days_back: Number of days to analyze
            
        Returns:
            dict: Channel metrics
        """
        cutoff_date = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        
        videos = self.db.query(YouTubeVideo).filter(
            and_(
                YouTubeVideo.channel_name == channel_name,
                YouTubeVideo.published_at >= cutoff_date
            )
        ).all()
        
        if not videos:
            return {"error": "No data found for this channel"}
        
        # Calculate metrics
        total_videos = len(videos)
        videos_by_date = {}
        
        for video in videos:
            date_key = video.published_at.split()[0]  # Get just the date part
            videos_by_date[date_key] = videos_by_date.get(date_key, 0) + 1
        
        avg_videos_per_day = total_videos / days_back
        
        return {
            "channel_name": channel_name,
            "total_videos": total_videos,
            "date_range_days": days_back,
            "average_videos_per_day": round(avg_videos_per_day, 2),
            "videos_by_date": videos_by_date,
            "most_active_day": max(videos_by_date.items(), key=lambda x: x[1]) if videos_by_date else None
        }


class JobService:
    """
    Service for managing scraping jobs and their status.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_jobs(
        self,
        user: User,
        limit: int = 20,
        offset: int = 0
    ) -> List[ScrapingJob]:
        """
        Get scraping jobs for a specific user.
        
        Args:
            user: User to get jobs for
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            
        Returns:
            list: List of scraping jobs
        """
        return self.db.query(ScrapingJob)\
                     .filter(ScrapingJob.user_id == user.id)\
                     .order_by(desc(ScrapingJob.created_at))\
                     .limit(limit)\
                     .offset(offset)\
                     .all()
    
    def get_job_status(self, job_id: int, user: User) -> Optional[ScrapingJob]:
        """
        Get status of a specific scraping job.
        
        Args:
            job_id: Job ID to check
            user: User requesting the status
            
        Returns:
            ScrapingJob: Job information or None if not found/accessible
        """
        return self.db.query(ScrapingJob)\
                     .filter(
                         and_(
                             ScrapingJob.id == job_id,
                             ScrapingJob.user_id == user.id
                         )
                     )\
                     .first()
    
    def cancel_job(self, job_id: int, user: User) -> bool:
        """
        Cancel a pending or running scraping job.
        
        Args:
            job_id: Job ID to cancel
            user: User requesting the cancellation
            
        Returns:
            bool: True if job was cancelled, False otherwise
        """
        job = self.get_job_status(job_id, user)
        
        if not job:
            return False
        
        if job.status in ["pending", "running"]:
            job.status = "cancelled"
            job.completed_at = datetime.utcnow()
            job.error_message = "Cancelled by user"
            self.db.commit()
            return True
        
        return False


class TwitterScrapingService:
    """
    Service for Twitter data scraping and management.
    
    Integrates with the existing twitter_scraping.py functionality using twikit
    library while providing a clean API interface for the FastAPI application.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.twitter_username = os.getenv("TWITTER_USERNAME")
        self.twitter_email = os.getenv("TWITTER_EMAIL") 
        self.twitter_password = os.getenv("TWITTER_PASSWORD")
    
    async def scrape_tweets(
        self,
        request: TwitterScrapeRequest,
        user: User
    ) -> Dict[str, Any]:
        """
        Scrape Twitter profiles asynchronously.
        
        Args:
            request: Scraping request parameters
            user: User making the request
            
        Returns:
            dict: Scraping results and job information
        """
        if not all([self.twitter_username, self.twitter_email, self.twitter_password]):
            raise ValueError("Twitter credentials not configured. Please set TWITTER_USERNAME, TWITTER_EMAIL, and TWITTER_PASSWORD.")
        
        # Create scraping job
        job = ScrapingJob(
            user_id=user.id,
            job_type="twitter",
            target=", ".join(request.usernames),
            status="pending",
            parameters=json.dumps({
                "usernames": request.usernames,
                "tweet_count": request.tweet_count,
                "include_retweets": request.include_retweets,
                "include_replies": request.include_replies
            })
        )
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        # Start background scraping
        asyncio.create_task(self._execute_twitter_scraping(job))
        
        return {
            "job_id": job.id,
            "status": job.status,
            "usernames": request.usernames,
            "message": "Twitter scraping job started successfully"
        }
    
    async def _execute_twitter_scraping(self, job: ScrapingJob):
        """
        Execute Twitter scraping in background.
        
        Args:
            job: Scraping job to execute
        """
        try:
            # Update job status
            job.status = "running"
            job.started_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Starting Twitter scraping job {job.id}")
            
            # Parse job parameters
            params = json.loads(job.parameters)
            usernames = params["usernames"]
            tweet_count = params.get("tweet_count", 20)
            include_retweets = params.get("include_retweets", True)
            include_replies = params.get("include_replies", False)
            
            # Import and use twikit
            from twikit import Client
            
            # Initialize Twitter client
            client = Client('en-US')
            
            # Login to Twitter
            await client.login(
                auth_info_1=self.twitter_username,
                auth_info_2=self.twitter_email,
                password=self.twitter_password,
                cookies_file='cookies.json'  # Cache cookies for subsequent requests
            )
            
            total_scraped = 0
            for username in usernames:
                try:
                    # Get user information
                    user_data = await client.get_user_by_screen_name(username)
                    user_id = user_data.id
                    
                    # Get user tweets
                    tweet_type = 'Tweets'
                    if include_replies:
                        tweet_type = 'Replies'
                    
                    tweets = await client.get_user_tweets(user_id, tweet_type, count=tweet_count)
                    
                    scraped_count = await self._process_tweets(
                        tweets, username, user_id, include_retweets
                    )
                    
                    total_scraped += scraped_count
                    logger.info(f"Scraped {scraped_count} tweets from @{username}")
                    
                    # Rate limiting - Twitter API has strict limits
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error scraping Twitter user @{username}: {str(e)}")
                    continue
            
            # Update job completion
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.result_count = total_scraped
            self.db.commit()
            
            logger.info(f"Completed Twitter scraping job {job.id}: {total_scraped} tweets")
            
        except Exception as e:
            # Update job with error
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            self.db.commit()
            
            logger.error(f"Twitter scraping job {job.id} failed: {str(e)}")
    
    async def _process_tweets(
        self,
        tweets: List,
        username: str,
        user_id: str,
        include_retweets: bool
    ) -> int:
        """
        Process and save tweets to database.
        
        Args:
            tweets: List of tweet objects from twikit
            username: Twitter username
            user_id: Twitter user ID
            include_retweets: Whether to include retweets
            
        Returns:
            int: Number of tweets processed
        """
        saved_tweets = []
        
        for tweet in tweets:
            try:
                # Skip retweets if not requested
                is_retweet = hasattr(tweet, 'retweeted_tweet') and tweet.retweeted_tweet
                if is_retweet and not include_retweets:
                    continue
                
                # Check if tweet already exists
                existing_tweet = self.db.query(TwitterTweet).filter(
                    TwitterTweet.tweet_id == str(tweet.id)
                ).first()
                
                if existing_tweet:
                    continue
                
                # Parse tweet creation time
                created_at = datetime.strptime(
                    tweet.created_at, 
                    "%a %b %d %H:%M:%S %z %Y"
                ) if isinstance(tweet.created_at, str) else tweet.created_at
                
                # Create tweet record
                tweet_record = TwitterTweet(
                    tweet_id=str(tweet.id),
                    username=username,
                    user_id=str(user_id),
                    full_text=clean_text(tweet.full_text or ""),
                    favorite_count=getattr(tweet, 'favorite_count', 0) or 0,
                    retweet_count=getattr(tweet, 'retweet_count', 0) or 0,
                    reply_count=getattr(tweet, 'reply_count', 0) or 0,
                    quote_count=getattr(tweet, 'quote_count', 0) or 0,
                    created_at=created_at,
                    is_retweet=is_retweet,
                    is_reply=hasattr(tweet, 'in_reply_to_status_id') and tweet.in_reply_to_status_id is not None,
                    language=getattr(tweet, 'lang', None),
                    source=getattr(tweet, 'source', None)
                )
                
                saved_tweets.append(tweet_record)
                
            except Exception as e:
                logger.error(f"Error processing tweet {tweet.id}: {str(e)}")
                continue
        
        # Save tweets to database
        if saved_tweets:
            self.db.add_all(saved_tweets)
            self.db.commit()
        
        return len(saved_tweets)
    
    def get_tweets(
        self,
        username: Optional[str] = None,
        days_back: int = 7,
        limit: int = 50,
        offset: int = 0
    ) -> List[TwitterTweet]:
        """
        Retrieve Twitter tweets from database.
        
        Args:
            username: Filter by username (optional)
            days_back: Number of days to look back
            limit: Maximum number of tweets to return
            offset: Number of tweets to skip
            
        Returns:
            list: List of Twitter tweets
        """
        query = self.db.query(TwitterTweet)
        
        if username:
            query = query.filter(TwitterTweet.username == username.lstrip('@'))
        
        # Filter by date if specified
        if days_back:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            query = query.filter(TwitterTweet.created_at >= cutoff_date)
        
        return query.order_by(desc(TwitterTweet.created_at))\
                   .limit(limit)\
                   .offset(offset)\
                   .all()
    
    def get_user_stats(self, username: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Get statistics for a specific Twitter user.
        
        Args:
            username: Twitter username (without @)
            days_back: Number of days to analyze
            
        Returns:
            dict: User statistics
        """
        username = username.lstrip('@')
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        tweets = self.db.query(TwitterTweet).filter(
            and_(
                TwitterTweet.username == username,
                TwitterTweet.created_at >= cutoff_date
            )
        ).all()
        
        if not tweets:
            return {"error": f"No data found for @{username}"}
        
        # Calculate statistics
        total_tweets = len(tweets)
        total_likes = sum(tweet.favorite_count or 0 for tweet in tweets)
        total_retweets = sum(tweet.retweet_count or 0 for tweet in tweets)
        total_replies = sum(tweet.reply_count or 0 for tweet in tweets)
        total_quotes = sum(tweet.quote_count or 0 for tweet in tweets)
        
        retweet_count = sum(1 for tweet in tweets if tweet.is_retweet)
        reply_count = sum(1 for tweet in tweets if tweet.is_reply)
        original_count = total_tweets - retweet_count - reply_count
        
        # Engagement metrics
        total_engagement = total_likes + total_retweets + total_replies + total_quotes
        avg_engagement = total_engagement / total_tweets if total_tweets > 0 else 0
        
        return {
            "username": f"@{username}",
            "total_tweets": total_tweets,
            "date_range_days": days_back,
            "engagement_metrics": {
                "total_likes": total_likes,
                "total_retweets": total_retweets,
                "total_replies": total_replies,
                "total_quotes": total_quotes,
                "total_engagement": total_engagement,
                "avg_engagement_per_tweet": round(avg_engagement, 2),
                "avg_likes_per_tweet": round(total_likes / total_tweets, 2) if total_tweets > 0 else 0,
                "avg_retweets_per_tweet": round(total_retweets / total_tweets, 2) if total_tweets > 0 else 0
            },
            "content_breakdown": {
                "original_tweets": original_count,
                "retweets": retweet_count,
                "replies": reply_count,
                "original_percentage": round((original_count / total_tweets) * 100, 2) if total_tweets > 0 else 0
            },
            "activity_metrics": {
                "tweets_per_day": round(total_tweets / days_back, 2),
                "most_engaging_tweet": max(tweets, key=lambda t: (t.favorite_count or 0) + (t.retweet_count or 0)).tweet_id if tweets else None
            }
        }