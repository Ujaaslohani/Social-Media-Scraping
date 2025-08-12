import os
import requests
import json
import pandas as pd
from datetime import datetime, timedelta, date
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

API_KEY = os.getenv("API_KEY")
TARGET_TABLE = "daily_videos"

# Channel configuration - add/remove channels here
CHANNELS = [
    {"id": "UCt4t-jeY85JegMlZ-E5UWtA", "name": "Aaj Tak"},
    {"id": "UCmphdqZNmqL72WJ2uyiNw5w", "name": "ABPLIVE"},
    {"id": "UCRWFSbif-RFENbBrSiez1DA", "name": "ABP NEWS"},
    # Add more channels as needed
]

# Date configuration
TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def create_db_engine():
    """Create and return a SQLAlchemy database engine"""
    try:
        engine = create_engine(
            f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['dbname']}"
        )
        return engine
    except Exception as e:
        print(f"Error creating database engine: {e}")
        raise


def get_channel_activities(channel_id, api_key, max_results=50):
    """
    Fetch YouTube activities for a channel with pagination support
    
    Args:
        channel_id (str): YouTube channel ID
        api_key (str): YouTube API key
        max_results (int): Maximum results per page (default: 50)
    
    Returns:
        list: Combined list of activities from all pages
    """
    all_activities = []
    next_page_token = None
    
    while True:
        # Build API URL
        url = (
            f"https://www.googleapis.com/youtube/v3/activities"
            f"?key={api_key}"
            f"&channelId={channel_id}"
            f"&maxResults={max_results}"
            f"&part=id,snippet,contentDetails"
        )
        
        if next_page_token:
            url += f"&pageToken={next_page_token}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Add activities to our list
            all_activities.extend(data.get("items", []))
            
            # Check for next page
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
                
            # Respect API rate limits
            time.sleep(1)
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for channel {channel_id}: {e}")
            break
    
    return all_activities


def process_activities(activities, channel_name):
    """
    Process YouTube activities and extract video information
    
    Args:
        activities (list): List of activity objects from YouTube API
        channel_name (str): Name of the channel
    
    Returns:
        DataFrame: Processed video data
    """
    videos = []
    
    for activity in activities:
        try:
            # Extract publication date
            published_at = activity["snippet"]["publishedAt"].split("T")[0]
            
            # Skip if not in our date range
            if not (YESTERDAY <= published_at <= TODAY):
                continue
                
            # Extract video ID
            try:
                video_id = activity["contentDetails"]["upload"]["videoId"]
            except KeyError:
                try:
                    video_id = activity["contentDetails"]["playlistItem"]["resourceId"]["videoId"]
                except KeyError:
                    video_id = "Not Available"
            
            # Create video record
            video = {
                "channel_id": activity["snippet"]["channelId"],
                "video_id": video_id,
                "published_at": published_at,
                "channel_name": channel_name,
                "datetime": datetime.now().strftime("%y-%m-%d %H:%M:%S")
            }
            
            videos.append(video)
            
        except KeyError as e:
            print(f"Missing key in activity: {e}")
            continue
    
    return pd.DataFrame(videos)


def save_to_database(df, table_name, engine):
    """
    Save DataFrame to database table
    
    Args:
        df (DataFrame): Data to save
        table_name (str): Target table name
        engine: SQLAlchemy engine
    """
    if df.empty:
        print("No data to save")
        return
    
    try:
        # Clean video_id field
        df["video_id"] = df["video_id"].astype(str).replace("=", "")
        
        # Remove duplicates
        df = df.drop_duplicates(subset=["video_id"])
        
        # Save to database
        df.to_sql(
            table_name,
            engine,
            if_exists="append",
            index=False
        )
        print(f"Saved {len(df)} records to {table_name}")
        
    except SQLAlchemyError as e:
        print(f"Error saving to database: {e}")
        raise


def main():
    """Main function to orchestrate the YouTube data collection"""
    print("Starting YouTube data collection...")
    
    # Create database engine
    engine = create_db_engine()
    
    # Process all channels
    all_videos = pd.DataFrame()
    
    for channel in CHANNELS:
        print(f"Processing channel: {channel['name']} ({channel['id']})")
        
        # Get activities from YouTube API
        activities = get_channel_activities(channel["id"], API_KEY)
        
        # Process activities to extract video data
        channel_videos = process_activities(activities, channel["name"])
        
        # Add to our collection
        all_videos = pd.concat([all_videos, channel_videos], ignore_index=True)
    
    # Save to database
    save_to_database(all_videos, TARGET_TABLE, engine)
    
    # Clean up
    engine.dispose()
    print("Data collection completed successfully")


if __name__ == "__main__":
    main()