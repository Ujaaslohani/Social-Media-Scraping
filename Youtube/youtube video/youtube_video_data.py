import os
import pandas as pd
from googleapiclient.discovery import build
from datetime import datetime, timedelta, date
import re
from tqdm import tqdm
from sqlalchemy import create_engine
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==============================================
# CONFIGURATION
# ==============================================
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"  # Set via environment variable
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))  # Number of parallel threads
BATCH_SIZE = 50  # YouTube API max per call

# API Keys from environment
API_KEYS = os.getenv("API_KEYS", "").split(",")

# Database configuration from environment
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# ==============================================
# LOGGING SETUP
# ==============================================
def setup_logging():
    """Configure detailed logging"""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler('youtube_data_collector.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==============================================
# DATABASE CONNECTION
# ==============================================
def setup_database():
    """Set up database connection with error handling"""
    try:
        engine = create_engine(
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}",
            pool_pre_ping=True,
            pool_recycle=3600
        )
        logger.info("Database connection established successfully")
        return engine
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise

# ==============================================
# HELPER FUNCTIONS
# ==============================================
def print_status(message):
    """Print status messages with timestamp"""
    logger.info(message)

def duration_to_string(duration):
    """Convert YouTube duration to seconds"""
    if not duration or not isinstance(duration, str):
        return 0
    duration = duration.replace('P', '').replace('T', '')
    seconds = 0
    time_components = {'D': 86400, 'H': 3600, 'M': 60, 'S': 1}
    
    current_value = ''
    for char in duration:
        if char.isdigit():
            current_value += char
        elif char in time_components:
            seconds += int(current_value) * time_components[char]
            current_value = ''
    return seconds

def convert_to_IST(utc_time, fmt='%Y-%m-%dT%H:%M:%SZ'):
    """Convert UTC to IST timezone"""
    if not utc_time:
        return None
    try:
        return (datetime.strptime(utc_time, fmt) + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        logger.warning(f"Time conversion error: {str(e)}")
        return None

def get_date_range():
    """Calculate date range for the past 24 hours"""
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    logger.info(f"Using 24-hour range: {start_time} to {end_time}")
    return start_time, end_time

# ==============================================
# CORE PROCESSING FUNCTIONS
# ==============================================
def process_single_video(item):
    """Process individual video data with error handling"""
    try:
        snippet = item.get('snippet', {})
        stats = item.get('statistics', {})
        content = item.get('contentDetails', {})
        status = item.get('status', {})
        live = item.get('liveStreamingDetails', {})
        published_at = snippet.get('publishedAt')
        ist_published = convert_to_IST(published_at) if published_at else None
        
        doc = {
            'Sample_datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'Sample_date': datetime.now().strftime("%Y-%m-%d"),
            'Video_id': item.get('id'),
            'Title': re.sub('[\'\"]', '', snippet.get('title', ''))[:500],
            'Thumbnails': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
            'Channel_id': snippet.get('channelId'),
            'Channel_title': re.sub('[\'\"]', '', snippet.get('channelTitle', ''))[:200],
            'Description': re.sub('[\'\"]', '', snippet.get('description', ''))[:1000],
            'Tags': str(snippet.get('tags', []))[:500],
            'Audio_language': snippet.get('defaultAudioLanguage', ''),
            'Duration': duration_to_string(content.get('duration', 'PT0S')),
            'YT_duration': content.get('duration', ''),
            'Definition': content.get('definition', ''),
            'View_count': int(stats.get('viewCount', 0)),
            'Favorite_count': int(stats.get('favoriteCount', 0)),
            'Comment_count': int(stats.get('commentCount', 0)),
            'Like_count': int(stats.get('likeCount', 0)),
            'Dislike_count': int(stats.get('dislikeCount', 0)),
            'Privacy_status': status.get('privacyStatus', ''),
            'Upload_status': status.get('uploadStatus', ''),
            'Age_restricted': item.get('contentDetails', {}).get('contentRating', {}).get('ytRating', ''),
            'IST_published_at': ist_published,
            'Published_date_ist': ist_published.split()[0] if ist_published else None,
            'YT_published_at': published_at,
            'Type': 'Live then VOD' if live else 'VOD',
            'IST_scheduled_starttime': convert_to_IST(live.get('scheduledStartTime')) if live else None,
            'IST_actualstarttime': convert_to_IST(live.get('actualStartTime')) if live else None,
            'IST_actual_endtime': convert_to_IST(live.get('actualEndTime')) if live else None,
            'YT_scheduled_starttime': live.get('scheduledStartTime') if live else None,
            'YT_actualstarttime': live.get('actualStartTime') if live else None,
            'YT_actual_endtime': live.get('actualEndTime') if live else None
        }
        
        if DEBUG_MODE:
            print_status("\nDEBUG SAMPLE:")
            print_status({k: v for k, v in doc.items() if v is not None and v != ''})
        
        return doc
    except Exception as e:
        logger.error(f"Error processing video {item.get('id', 'unknown')}: {str(e)}")
        return None

def process_batch(batch, api_key):
    """Process a single batch of videos with error handling"""
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        response = youtube.videos().list(
            part="snippet,statistics,contentDetails,status,liveStreamingDetails",
            id=','.join(batch)
        ).execute()
        
        results = []
        for item in response.get('items', []):
            processed = process_single_video(item)
            if processed:
                results.append(processed)
        
        return results
    except Exception as e:
        logger.error(f"Error processing batch {batch[:3]}...: {str(e)}")
        return []

def process_videos_parallel(video_ids):
    """Process videos using parallel threads with error handling"""
    results = []
    batches = [video_ids[i:i+BATCH_SIZE] for i in range(0, len(video_ids), BATCH_SIZE)]
    
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for i, batch in enumerate(batches):
                api_key = API_KEYS[i % len(API_KEYS)]
                futures.append(executor.submit(process_batch, batch, api_key))
            
            for future in tqdm(as_completed(futures), total=len(futures), 
                             desc="Processing Videos", disable=DEBUG_MODE):
                try:
                    batch_result = future.result()
                    if batch_result:
                        results.extend(batch_result)
                except Exception as e:
                    logger.error(f"Error in batch processing: {str(e)}")
                    continue
        
        return pd.DataFrame(results)
    except Exception as e:
        logger.error(f"Error in parallel processing: {str(e)}")
        return pd.DataFrame()

# ==============================================
# DATA LOADING AND SAVING
# ==============================================
def load_video_ids():
    """Load video IDs from database for the past 24 hours"""
    try:
        start_time, end_time = get_date_range()
        
        query = f"""
        SELECT DISTINCT video_id 
        FROM Daliy_all_vid 
        WHERE datetime >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}' 
        AND datetime <= '{end_time.strftime('%Y-%m-%d %H:%M:%S')}'
        {'LIMIT 100' if DEBUG_MODE else ''}
        """
        
        print_status(f"Loading video IDs from {start_time} to {end_time}")
        video_ids = pd.read_sql(query, engine)['video_id'].tolist()
        print_status(f"Found {len(video_ids)} videos to process")
        return video_ids
    except Exception as e:
        logger.error(f"Error loading video IDs: {str(e)}")
        return []

def save_to_database(df):
    """Optimized database insertion with transaction management"""
    if df.empty:
        print_status("No data to save")
        return
    
    try:
        # Convert numeric columns
        int_cols = ['View_count', 'Favorite_count', 'Comment_count', 'Like_count', 'Dislike_count']
        df[int_cols] = df[int_cols].fillna(0).astype(int)
        
        # Insert in chunks with transaction management
        chunk_size = 1000
        total_rows = len(df)
        saved_rows = 0
        
        with engine.connect() as connection:
            with connection.begin() as transaction:
                try:
                    for i in tqdm(range(0, total_rows, chunk_size), 
                                desc="Saving to DB", disable=DEBUG_MODE):
                        chunk = df.iloc[i:i + chunk_size]
                        chunk.to_sql('Daliy_vod_inc', connection, if_exists='append', index=False)
                        saved_rows += len(chunk)
                        print_status(f"Saved chunk {i//chunk_size + 1}: {len(chunk)} records")
                    
                    transaction.commit()
                    print_status(f"Successfully saved {saved_rows} records to database")
                except Exception as e:
                    transaction.rollback()
                    logger.error(f"Error saving to database: {str(e)}")
                    logger.error("Transaction rolled back")
                    raise
    except Exception as e:
        logger.error(f"Database operation failed: {str(e)}")
        raise

# ==============================================
# MAIN EXECUTION
# ==============================================
def main():
    """Main function with comprehensive error handling"""
    start_time = datetime.now()
    print_status(f"\n{' DEBUG MODE' if DEBUG_MODE else ' PRODUCTION RUN'} started at {start_time}")
    
    global engine
    engine = None
    
    try:
        # 1. Setup Database
        engine = setup_database()
        
        # 2. Load Data
        video_ids = load_video_ids()
        if not video_ids:
            print_status("No videos to process. Exiting.")
            return
        
        # 3. Process Videos
        print_status("Processing videos...")
        results = process_videos_parallel(video_ids)
        
        if results.empty:
            print_status("No valid results after processing. Exiting.")
            return
        
        print_status(f"Processed {len(results)} videos")
        
        # 4. Save Results
        if not DEBUG_MODE:
            print_status("Saving to database...")
            save_to_database(results)
        else:
            print_status("\nDEBUG SAMPLE (first 3 records):")
            print(results[['Video_id', 'Title', 'Channel_title', 'View_count']].head(3))
        
    except Exception as e:
        logger.error(f"Fatal error in main execution: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        if engine:
            engine.dispose()
        elapsed = datetime.now() - start_time
        print_status(f"Total runtime: {elapsed}")

if __name__ == "__main__":
    main()